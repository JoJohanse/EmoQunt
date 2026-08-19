"""本地数据缓存层：PostgreSQL 持久化 + Redis 热缓存。

本模块是 data_manager.py 的旁路缓存，**任何故障都静默降级**到 None/无操作，
主流程 (CSV + 网络回退链) 照常工作。连接参数从环境变量读取（见 .env.example）。

缓存读取顺序（data_manager 接入）：
    Redis（热，TTL）→ PostgreSQL（全历史）→ 本地 CSV → 网络回退链
    网络成功后 → 回填 PostgreSQL(upsert) + Redis

数据以统一中文列名契约存储（src/data/columns.py）：时间/开盘/最高/最低/收盘/
成交量/成交额/换手率/流通股数。`时间` 在 PG 中是 DATE 列 `trade_date`，
在 DataFrame 中为普通列。单位已归一化（baostock/tushare 源差异已在 _fetch_* 内修正）。

启用开关：QDT_DB_CACHE_ENABLED / QDT_REDIS_CACHE_ENABLED（默认 true）。

持久化加固：
- PG 轻度连接池化：可选 psycopg_pool.ConnectionPool(min_size=1,max_size=5,open=False)，
  未安装则回退单连接；提供幂等 init_pool()/close_pool() 供 lifespan 统一开关。
- Redis 支持 REDIS_PASSWORD 可选密码。
- TTL 分层：当日 300s / 历史 7d ±10% jitter。

CLI：
    python -m src.data.db init        # 手动建表/索引（幂等）
    python -m src.data.db healthcheck # 打印连通性
"""
from __future__ import annotations

import logging
import random
import time
from contextlib import contextmanager
from io import BytesIO
from typing import Optional

import pandas as pd

from src.utils.env import get_env, get_env_bool, get_env_int

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 开关与配置
# ---------------------------------------------------------------------------
DB_CACHE_ENABLED = get_env_bool("QDT_DB_CACHE_ENABLED", default=True)
REDIS_CACHE_ENABLED = get_env_bool("QDT_REDIS_CACHE_ENABLED", default=True)
# TTL：若 QDT_REDIS_TTL_SECONDS 被显式配置则作为固定 TTL，否则按分层动态（当日 300s / 历史 7d±jitter）
_redis_ttl_env_raw = get_env("QDT_REDIS_TTL_SECONDS", "")
REDIS_TTL_SECONDS = get_env_int("QDT_REDIS_TTL_SECONDS", default=86400)

# TTL 分层常量
_TTL_TODAY = 300
_TTL_HISTORY = 604800  # 7d

# 单例连接（懒加载，首次调用才连，避免 import 副作用）
_pg_pool = None  # psycopg 连接 或 psycopg_pool.ConnectionPool
_pg_is_pool = False
_redis_client = None
_init_done = False

# 连接失败后的"熔断"标记：避免每次 get/save 都重试缓慢的 TCP 连接
# （DB 没启动时每次 connect_timeout 等待会拖垮高频调用）。
# 失败后 _UNAVAILABLE_UNTIL 之前直接返回 None，过后再试一次。
_pg_unavailable_until = 0.0
_redis_unavailable_until = 0.0
_UNAVAILABLE_RETRY_SECONDS = 30.0


def _pg_dsn() -> str:
    """构造 PostgreSQL DSN（参数从环境变量读取）。"""
    user = get_env("POSTGRES_USER", "emoqunt")
    pwd = get_env("POSTGRES_PASSWORD", "emoqunt_local")
    db = get_env("POSTGRES_DB", "emoqunt")
    host = get_env("POSTGRES_HOST", "127.0.0.1")
    port = get_env("POSTGRES_PORT", "5432")
    return f"host={host} port={port} dbname={db} user={user} password={pwd}"


def _ensure_pg_initialized() -> None:
    """尝试初始化 PG 连接池（可选 psycopg_pool），未安装或失败则静默回退。

    幂等：已初始化或熔断期内直接返回。仅在 pool 可用时创建 pool，
    否则交由 _get_pg 懒创建单连接。
    """
    global _pg_pool, _pg_is_pool, _pg_unavailable_until
    if not DB_CACHE_ENABLED:
        return
    if _pg_pool is not None or _pg_is_pool:
        return
    if time.monotonic() < _pg_unavailable_until:
        return
    pool = None
    try:
        from psycopg_pool import ConnectionPool  # type: ignore

        pool = ConnectionPool(
            _pg_dsn(), min_size=1, max_size=5, open=False, timeout=3,
            kwargs={"autocommit": True, "connect_timeout": 3},
        )
        pool.open(wait=True, timeout=3)
        # 建表（幂等）
        with pool.connection() as conn:
            _ensure_schema(conn)
        _pg_pool = pool
        _pg_is_pool = True
        logger.info("PostgreSQL 连接池已初始化 (psycopg_pool)")
        return
    except ImportError:
        # 未安装 psycopg_pool，回退单连接
        if pool is not None:
            try:
                pool.close()
            except Exception:
                pass
        return
    except Exception as e:
        logger.warning(f"PostgreSQL 连接池初始化失败，回退单连接: {e}")
        if pool is not None:
            try:
                pool.close()
            except Exception:
                pass
        # 池初始化失败也进入短熔断，避免高频重试池创建
        _pg_unavailable_until = time.monotonic() + _UNAVAILABLE_RETRY_SECONDS
        return


@contextmanager
def _pg_conn():
    """提供 PG 连接的上下文管理器，兼容 pool 与单连接两种模式。

    - pool 模式：with pool.connection() as conn:
    - 单连接模式：yield 单例连接（不关闭）
    失败时 yield None。
    """
    if not DB_CACHE_ENABLED:
        yield None
        return
    # 懒初始化池（优先）
    if _pg_pool is None and not _pg_is_pool and time.monotonic() >= _pg_unavailable_until:
        try:
            _ensure_pg_initialized()
        except Exception:
            pass
    if _pg_is_pool and _pg_pool is not None:
        try:
            with _pg_pool.connection() as conn:  # type: ignore[attr-defined]
                yield conn
            return
        except Exception as e:
            logger.debug(f"PG pool 获取连接失败: {e}")
            yield None
            return
    # 单连接模式
    conn = _get_pg()
    yield conn


def _get_pg():
    """获取 psycopg 连接单例；不可用返回 None。

    连接失败后做"熔断"：30 秒内不再重试，避免 DB 未启动时每次调用都
    等待 connect_timeout（默认 ~21s on Windows）拖垮高频路径。
    pool 模式下此函数不创建连接，返回 None 由 _pg_conn 处理。
    """
    global _pg_pool, _pg_unavailable_until, _pg_is_pool
    if not DB_CACHE_ENABLED:
        return None
    if _pg_is_pool and _pg_pool is not None:
        return None
    if _pg_pool is not None:
        return _pg_pool
    if time.monotonic() < _pg_unavailable_until:
        return None  # 熔断期内直接跳过
    try:
        import psycopg
        # autocommit=True：缓存层不需要事务，每条语句独立提交
        # connect_timeout=3：DB 未启动时快速失败（而非 ~21s）
        _pg_pool = psycopg.connect(_pg_dsn(), autocommit=True, connect_timeout=3)
        _ensure_schema(_pg_pool)
        logger.info("PostgreSQL 缓存层已连接")
    except Exception as e:
        logger.warning(f"PostgreSQL 连接失败，缓存层降级到 CSV/网络（30s 内不再重试）: {e}")
        _pg_pool = None
        _pg_unavailable_until = time.monotonic() + _UNAVAILABLE_RETRY_SECONDS
    return _pg_pool


def _get_redis():
    """获取 Redis 客户端单例；不可用返回 None。

    同 _get_pg 的熔断策略：失败后 30s 内不再重试。
    支持 REDIS_PASSWORD 可选密码。
    """
    global _redis_client, _redis_unavailable_until
    if not REDIS_CACHE_ENABLED:
        return None
    if _redis_client is not None:
        return _redis_client
    if time.monotonic() < _redis_unavailable_until:
        return None
    try:
        import redis
        host = get_env("REDIS_HOST", "127.0.0.1")
        port = int(get_env("REDIS_PORT", "6379"))
        pwd = get_env("REDIS_PASSWORD", "")
        if pwd is not None and str(pwd).strip() == "":
            pwd = None
        _redis_client = redis.Redis(
            host=host, port=port, password=pwd, socket_connect_timeout=2,
            socket_timeout=2, decode_responses=False,
        )
        _redis_client.ping()
        logger.info("Redis 缓存层已连接")
    except Exception as e:
        logger.warning(f"Redis 连接失败，热缓存降级（30s 内不再重试）: {e}")
        _redis_client = None
        _redis_unavailable_until = time.monotonic() + _UNAVAILABLE_RETRY_SECONDS
    return _redis_client


def init_pool() -> None:
    """幂等初始化 PG 与 Redis 连接（供 web_app lifespan 调用）。失败静默降级。"""
    if DB_CACHE_ENABLED:
        try:
            _ensure_pg_initialized()
            if not _pg_is_pool:
                _get_pg()
        except Exception as e:
            logger.debug(f"init_pool PG 失败: {e}")
    if REDIS_CACHE_ENABLED:
        try:
            _get_redis()
        except Exception as e:
            logger.debug(f"init_pool Redis 失败: {e}")


def close_pool() -> None:
    """幂等关闭 PG 与 Redis 连接并重置熔断标记。"""
    global _pg_pool, _pg_is_pool, _pg_unavailable_until, _init_done
    global _redis_client, _redis_unavailable_until
    # PG
    try:
        if _pg_pool is not None:
            try:
                _pg_pool.close()
            except Exception:
                pass
    except Exception as e:
        logger.debug(f"PG close 失败: {e}")
    finally:
        _pg_pool = None
        _pg_is_pool = False
        _pg_unavailable_until = 0.0
        _init_done = False
    # Redis
    try:
        if _redis_client is not None:
            try:
                _redis_client.close()
            except Exception:
                pass
    except Exception as e:
        logger.debug(f"Redis close 失败: {e}")
    finally:
        _redis_client = None
        _redis_unavailable_until = 0.0


# ---------------------------------------------------------------------------
# 建表（幂等）
# ---------------------------------------------------------------------------
_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS stock_daily (
    code        VARCHAR(16)  NOT NULL,
    trade_date  DATE         NOT NULL,
    open        DOUBLE PRECISION,
    high        DOUBLE PRECISION,
    low         DOUBLE PRECISION,
    close       DOUBLE PRECISION,
    volume      DOUBLE PRECISION,
    amount      DOUBLE PRECISION,
    turnover    DOUBLE PRECISION,
    outstanding_share DOUBLE PRECISION,
    market      VARCHAR(8)  NOT NULL DEFAULT 'zh_a',
    adjust      VARCHAR(4)  NOT NULL DEFAULT 'nfq',
    is_index    BOOLEAN     NOT NULL DEFAULT FALSE,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (code, trade_date, adjust)
);
CREATE INDEX IF NOT EXISTS idx_stock_daily_code_adj_date
    ON stock_daily (code, adjust, trade_date);
"""

# Upsert：冲突时整体更新（含 updated_at）。PG 15+ 支持 alias
_UPSERT_SQL = """
INSERT INTO stock_daily
    (code, trade_date, open, high, low, close, volume, amount,
     turnover, outstanding_share, market, adjust, is_index, updated_at)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now())
ON CONFLICT (code, trade_date, adjust) DO UPDATE SET
    open = EXCLUDED.open,
    high = EXCLUDED.high,
    low = EXCLUDED.low,
    close = EXCLUDED.close,
    volume = EXCLUDED.volume,
    amount = EXCLUDED.amount,
    turnover = EXCLUDED.turnover,
    outstanding_share = EXCLUDED.outstanding_share,
    market = EXCLUDED.market,
    is_index = EXCLUDED.is_index,
    updated_at = now();
"""


def _ensure_schema(conn) -> None:
    """首次连接时建表/索引（幂等）。"""
    global _init_done
    if _init_done:
        return
    try:
        with conn.cursor() as cur:
            cur.execute(_CREATE_TABLE_SQL)
        _init_done = True
    except Exception as e:
        logger.warning(f"建表失败（后续查询仍可能工作）: {e}")


# ---------------------------------------------------------------------------
# 序列化（Redis 存 parquet bytes —— 紧凑、快、保留 dtypes）
# ---------------------------------------------------------------------------
# 中文列名 ↔ PG 列名映射（中文是内部契约，PG 用英文小写蛇形）
_ZH_TO_PG = {
    '时间': 'trade_date', '开盘': 'open', '最高': 'high', '最低': 'low',
    '收盘': 'close', '成交量': 'volume', '成交额': 'amount',
    '换手率': 'turnover', '流通股数': 'outstanding_share',
}
_PG_TO_ZH = {v: k for k, v in _ZH_TO_PG.items()}
# PG SELECT 列顺序（与 _PG_TO_ZH 配合重构 DataFrame）
_PG_COLUMNS = ['trade_date', 'open', 'high', 'low', 'close',
               'volume', 'amount', 'turnover', 'outstanding_share']


def _df_to_bytes(df: pd.DataFrame) -> bytes:
    buf = BytesIO()
    df.to_parquet(buf)
    return buf.getvalue()


def _df_from_bytes(data: bytes) -> pd.DataFrame:
    return pd.read_parquet(BytesIO(data))


def _redis_key(code: str, market: str, adjust: str, start: str, end: str) -> str:
    return f"stock:{market}:{adjust}:{code}:{start or '_'}:{end or '_'}"

def _redis_latest_key(code: str, market: str, adjust: str) -> str:
    """按 code 全量的 latest 键，替代空窗口键，避免陈旧窗口误命中。"""
    return f"stock:{market}:{adjust}:{code}:latest"


def _redis_ttl_for(dates_max) -> int:
    """根据数据最大日期动态计算 Redis TTL。

    - 若 QDT_REDIS_TTL_SECONDS 被显式配置则固定返回该值（便于运维覆盖）
    - 否则：若 end 日期是今天 → 300s（当日数据易变）
      否则 → 7d ±10% jitter（历史数据稳定，长 TTL + 抖动防雪崩）
    """
    if _redis_ttl_env_raw and _redis_ttl_env_raw.strip():
        return REDIS_TTL_SECONDS
    try:
        d = pd.to_datetime(dates_max)
        today = pd.Timestamp.now().normalize()
        if d.normalize().date() == today.date():
            return _TTL_TODAY
        base = _TTL_HISTORY
        jitter = random.uniform(0.9, 1.1)
        return int(base * jitter)
    except Exception:
        return _TTL_HISTORY


# ---------------------------------------------------------------------------
# 日期规范化（接受 'YYYYMMDD' / 'YYYY-MM-DD'）
# ---------------------------------------------------------------------------
def _to_pg_date(s: Optional[str]) -> Optional[str]:
    """转 'YYYY-MM-DD'；空/非法返回 None。"""
    if not s:
        return None
    try:
        return pd.to_datetime(str(s)).strftime('%Y-%m-%d')
    except Exception:
        return None


def _normalize_df(df: pd.DataFrame) -> pd.DataFrame:
    """确保 DataFrame 有中文列名契约 + 时间为日期类型。

    data_manager 的网络回退链已产出中文列名，但 DB 写入要兼容任何输入。
    """
    if df is None or df.empty:
        return df
    df = df.copy()
    # 若是英文小写列（如直接传入 _fetch_us_stock_yf 的输出），转中文
    from src.data.columns import EN_TO_ZH
    rename = {k: v for k, v in EN_TO_ZH.items() if k in df.columns}
    if rename:
        df = df.rename(columns=rename)
    if '时间' in df.columns:
        df['时间'] = pd.to_datetime(df['时间']).dt.strftime('%Y-%m-%d')
    return df


# ---------------------------------------------------------------------------
# 公共 API
# ---------------------------------------------------------------------------
def get_cached_range(
    code: str,
    market: str,
    adjust: str,
    start: str,
    end: str,
    is_index: bool = False,
) -> Optional[pd.DataFrame]:
    """查询缓存：Redis 优先，PG 次之。

    :param code: 股票/指数代码（A股裸 6 位如 '600938'；美股大写 ticker 如 'AAPL'；
                 指数如 '000300'/'SP500'）
    :param market: 'zh_a' / 'us'
    :param adjust: 'nfq' / 'qfq' / 'hfq'
    :param start: 'YYYYMMDD' 或 'YYYY-MM-DD'
    :param end: 同上
    :param is_index: 是否指数（影响 PG 的 is_index 列，不影响查询逻辑）
    :return: 中文列名 DataFrame（覆盖 [start,end] 范围且非空），否则 None。
    """
    if not (DB_CACHE_ENABLED or REDIS_CACHE_ENABLED):
        return None

    code = str(code)
    start_pg = _to_pg_date(start)
    end_pg = _to_pg_date(end)

    # ① Redis（精确窗口键 → latest 键兜底）
    r = _get_redis()
    if r is not None:
        try:
            key = _redis_key(code, market, adjust, start, end)
            raw = r.get(key)
            if raw:
                df = _df_from_bytes(raw)
                if df is not None and not df.empty:
                    logger.debug(f"Redis 命中 {code} ({market}/{adjust})")
                    return df
            # 精确窗口未命中时，若 latest 键存在且覆盖请求范围则复用（避免浪费）
            latest_raw = r.get(_redis_latest_key(code, market, adjust))
            if latest_raw:
                df = _df_from_bytes(latest_raw)
                if df is not None and not df.empty and '时间' in df.columns:
                    need_start = pd.to_datetime(start_pg) if start_pg else None
                    need_end = pd.to_datetime(end_pg) if end_pg else None
                    try:
                        dates = pd.to_datetime(df['时间'])
                        cov_start = dates.min()
                        cov_end = dates.max()
                        if (need_start is None or cov_start <= need_start) and (need_end is None or cov_end >= need_end):
                            logger.debug(f"Redis latest 命中 {code} ({market}/{adjust})")
                            # 按请求范围裁剪后返回（保证契约）
                            m = pd.Series([True] * len(df))
                            if need_start is not None:
                                m &= dates >= need_start
                            if need_end is not None:
                                m &= dates <= need_end
                            return df[m].reset_index(drop=True)
                    except Exception:
                        pass
        except Exception as e:
            logger.debug(f"Redis 读取失败，回退 PG: {e}")

    # ② PostgreSQL 范围查询（兼容 pool / 单连接）
    with _pg_conn() as conn:
        if conn is None:
            return None
        try:
            cols = ', '.join(_PG_COLUMNS)
            # 动态拼 WHERE：避免 `(%s IS NULL OR ...)` 模式 —— psycopg 对裸 %s 无法推断
            # DATE 类型做 NULL 比较，会抛 IndeterminateDatatype。在 Python 端判空更稳。
            clauses = ["code = %s", "adjust = %s"]
            params = [code, adjust]
            if start_pg:
                clauses.append("trade_date >= %s")
                params.append(start_pg)
            if end_pg:
                clauses.append("trade_date <= %s")
                params.append(end_pg)
            sql = f"SELECT {cols} FROM stock_daily WHERE {' AND '.join(clauses)} ORDER BY trade_date ASC;"
            with conn.cursor() as cur:
                cur.execute(sql, params)
                rows = cur.fetchall()
            if not rows:
                return None
            df = pd.DataFrame(rows, columns=_PG_COLUMNS)
            # 转中文列名 + 日期类型，与 data_manager 输出契约一致
            df = df.rename(columns=_PG_TO_ZH)
            if '时间' in df.columns:
                df['时间'] = pd.to_datetime(df['时间'])
            for col in ('开盘', '最高', '最低', '收盘', '成交量', '成交额'):
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            logger.debug(f"PostgreSQL 命中 {code} ({market}/{adjust}): {len(df)} 行")
            return df
        except Exception as e:
            logger.debug(f"PG 读取失败: {e}")
            return None


def save_daily(
    df: pd.DataFrame,
    code: str,
    market: str,
    adjust: str,
    is_index: bool = False,
) -> None:
    """upsert DataFrame 到 PG + 回填 Redis。失败静默。

    :param df: 中文列名（或英文小写）DataFrame，需含 '时间' 列
    :param code/market/adjust/is_index: 见 get_cached_range
    """
    if not (DB_CACHE_ENABLED or REDIS_CACHE_ENABLED):
        return
    if df is None or df.empty:
        return

    code = str(code)
    df = _normalize_df(df)
    if df.empty or '时间' not in df.columns:
        return

    # 准备行数据（按 _ZH_TO_PG 取列，缺失列给 None）
    rows = []
    for _, r in df.iterrows():
        rows.append((
            code,
            r['时间'] if pd.notna(r.get('时间')) else None,
            r.get('开盘'), r.get('最高'), r.get('最低'), r.get('收盘'),
            r.get('成交量'), r.get('成交额'), r.get('换手率'), r.get('流通股数'),
            market, adjust, bool(is_index),
        ))
    rows = [row for row in rows if row[1] is not None]  # 丢弃无日期行
    if not rows:
        return

    # ② PG upsert（兼容 pool / 单连接）
    with _pg_conn() as conn:
        if conn is not None:
            try:
                with conn.cursor() as cur:
                    cur.executemany(_UPSERT_SQL, rows)
                logger.debug(f"PG 写入 {code} ({market}/{adjust}): {len(rows)} 行")
            except Exception as e:
                logger.warning(f"PG 写入失败（不影响主流程）: {e}")

    # ① Redis 回填（用整段 df 的起止日期作 key，TTL 分层）
    r = _get_redis()
    if r is not None:
        try:
            dates = pd.to_datetime(df['时间'], errors='coerce').dropna()
            if not dates.empty:
                start_s = dates.min().strftime('%Y%m%d')
                end_s = dates.max().strftime('%Y%m%d')
                ttl = _redis_ttl_for(dates.max())
                key = _redis_key(code, market, adjust, start_s, end_s)
                r.setex(key, ttl, _df_to_bytes(df))
                # 也存一个按 code 全量的 latest 键，便于无参查询命中（替代空窗口键）
                latest_key = _redis_latest_key(code, market, adjust)
                r.setex(latest_key, ttl, _df_to_bytes(df))
        except Exception as e:
            logger.debug(f"Redis 回填失败: {e}")


def get_latest_date(
    code: str,
    market: str,
    adjust: str,
) -> Optional[str]:
    """PG 中该 code+adjust 的最大 trade_date（'YYYY-MM-DD'），无则 None。

    用于增量更新判断：若最新日期已是今天/昨天，可跳过网络拉取。
    """
    if not DB_CACHE_ENABLED:
        return None
    with _pg_conn() as conn:
        if conn is None:
            return None
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT MAX(trade_date) FROM stock_daily WHERE code=%s AND adjust=%s;",
                    (str(code), adjust),
                )
                row = cur.fetchone()
            if row and row[0]:
                return str(row[0])
        except Exception as e:
            logger.debug(f"PG get_latest_date 失败: {e}")
        return None


def healthcheck() -> dict:
    """返回 {'postgres': bool, 'redis': bool}，供 /api/health 用。"""
    result = {'postgres': False, 'redis': False}
    if DB_CACHE_ENABLED:
        with _pg_conn() as conn:
            if conn is not None:
                try:
                    with conn.cursor() as cur:
                        cur.execute("SELECT 1;")
                        cur.fetchone()
                    result['postgres'] = True
                except Exception:
                    result['postgres'] = False
    if REDIS_CACHE_ENABLED:
        r = _get_redis()
        if r is not None:
            try:
                r.ping()
                result['redis'] = True
            except Exception:
                result['redis'] = False
    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
if __name__ == '__main__':
    import sys
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'healthcheck'
    if cmd == 'init':
        # 显式初始化并建表
        init_pool()
        # 若为 pool 模式，_ensure_schema 已在 _ensure_pg_initialized 内执行
        # 单连接模式下 _get_pg 已触发建表
        with _pg_conn() as c:
            if c is not None:
                print("schema 已就绪（CREATE TABLE IF NOT EXISTS）")
            else:
                print("PG 不可用"); sys.exit(1)
    elif cmd == 'healthcheck':
        print(healthcheck())
    else:
        print(f"未知命令: {cmd}（支持: init, healthcheck）"); sys.exit(1)
