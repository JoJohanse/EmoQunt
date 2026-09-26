"""行情速览服务：行业板块行情 + 市场宽度（涨跌家数），供首页看板卡片。

数据源与降级策略：
- 板块行情：akshare ``stock_board_industry_summary_ths``（同花顺行业一览，含
  板块涨跌幅/成交额/上涨下跌家数/领涨股，90 个行业一次拉全）。
- 市场宽度：同花顺各行业上涨/下跌家数求和得到全市场涨跌家数；涨停/跌停家数
  用东财涨停/跌停股池（``stock_zt_pool_em`` / ``stock_zt_pool_dtgc_em``）按最近
  交易日统计，失败时置 None 不阻塞整体。
- 东财行情快照（spot_em）与乐咕活跃度接口在部分网络环境不可达，故不作为依赖。

进程内 TTL 缓存 5 分钟（src.utils.ttl_cache 助手），避免首页多次刷新
反复打数据源。板块 DataFrame 本身也做短 TTL 缓存，避免冷缓存时 breadth 与
sectors 并行请求各打一次 THS 全量爬取。

本地持久化（quote_cache，SWR）：breadth/sectors 结果落 data/market_cache.db，
服务重启后首页首屏不再等 THS 全量爬——新鲜（<=5 分钟）直接回，过期先回
旧值 + 后台刷新，未命中才同步爬。
"""
import concurrent.futures
import logging
import threading
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from src.data import quote_cache
from src.utils.ttl_cache import TTLCache

logger = logging.getLogger(__name__)

_CACHE_TTL = 300  # 秒
_CACHE = TTLCache()


def _to_num(value, default: float = 0.0):
    """akshare 各源数值列可能混入字符串/'-'，统一安全转 float。

    传 Series 返回 Series（向量化），传标量返回标量。
    """
    import pandas as pd
    if hasattr(value, "map"):  # pd.Series
        return pd.to_numeric(value, errors="coerce").fillna(default)
    try:
        f = float(value)
        return f if f == f else default  # 过滤 NaN
    except (TypeError, ValueError):
        return default


def _call_with_timeout(fn, timeout: float, *args, **kwargs):
    """在独立 daemon 线程中执行 fn，超过 timeout 秒则放弃并返回 None。

    akshare 底层 requests.get 未设置 timeout，网络异常时可能无限挂起；
    用该包装避免占满 FastAPI 共享线程池。旧实现用 ThreadPoolExecutor 上下文
    管理器，退出时 shutdown(wait=True) 会等挂死线程跑完——超时形同虚设；
    改为 daemon 线程 + join(timeout) 非阻塞模式：超时后本函数立刻返回 None，
    挂死的网络调用留在后台线程自然消亡（Python 线程不可强杀，属已知权衡）。
    """
    outcome: Dict[str, Any] = {}

    def _runner():
        try:
            outcome["value"] = fn(*args, **kwargs)
        except BaseException as e:  # noqa: BLE001 - 异常带回主线程统一处理
            outcome["err"] = e

    t = threading.Thread(target=_runner, daemon=True, name=f"qdt-timeout-{getattr(fn, '__name__', 'call')}")
    t.start()
    t.join(timeout)
    if t.is_alive():
        logger.warning("akshare 调用超时(%ss)已跳过: %s", timeout, getattr(fn, "__name__", fn))
        return None
    if "err" in outcome:
        raise outcome["err"]
    return outcome.get("value")


def _pool_size(fetcher, start: datetime, timeout: float = 5.0) -> Optional[int]:
    """按日期从新到旧尝试拉取涨/跌停股池，返回家数；全部失败返回 None。

    lookback 仅 3 天（够覆盖周末/节假日），单次调用 5s 硬超时，避免线程池饥饿。
    fetcher 为 None（akshare 未导出该函数）时直接返回 None。
    """
    if fetcher is None:
        return None
    d = start
    for _ in range(3):
        try:
            df = _call_with_timeout(fetcher, timeout, date=d.strftime('%Y%m%d'))
            if df is not None and len(df) > 0:
                return int(len(df))
        except Exception as e:
            logger.debug(f"股池查询失败 {d:%Y%m%d}: {e}")
        d -= timedelta(days=1)
    return None


def _load_sector_df():
    """同花顺行业一览爬取（带 20s 硬超时——akshare 底层无 timeout，防挂死占线程）。"""
    import akshare as ak

    df = _call_with_timeout(ak.stock_board_industry_summary_ths, 20.0)
    if df is None:
        raise RuntimeError("同花顺行业一览爬取超时(20s)")
    return df


def _get_sector_df_cached():
    """带 TTL 的板块 DataFrame 单例，供两个对外函数共享，避免冷缓存双爬。"""
    return _CACHE.get_or_set("_ths_df", _load_sector_df, ttl=_CACHE_TTL)


def _fetch_sector_board() -> Dict[str, Any]:
    df = _get_sector_df_cached()
    sectors: List[Dict[str, Any]] = []
    for _, r in df.iterrows():
        sectors.append({
            "name": str(r.get("板块", "")),
            "chg_pct": round(_to_num(r.get("涨跌幅")), 2),
            "turnover": round(_to_num(r.get("总成交额")), 2),
            "net_inflow": round(_to_num(r.get("净流入")), 2),
            "up_count": int(_to_num(r.get("上涨家数"))),
            "down_count": int(_to_num(r.get("下跌家数"))),
            "leader": str(r.get("领涨股", "") or ""),
            "leader_chg": round(_to_num(r.get("领涨股-涨跌幅")), 2),
        })
    sectors.sort(key=lambda s: s["chg_pct"], reverse=True)
    return {
        "sectors": sectors,
        "updated_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    }


def get_sector_board() -> Dict[str, Any]:
    """行业板块行情列表（按涨跌幅降序），供首页热力图/排行榜。

    本地持久化 SWR：新鲜直接回缓存；过期回旧值 + 后台刷新；未命中同步爬。
    """
    try:
        cached, fresh = quote_cache.lookup("sector_board", _CACHE_TTL)
        if cached is not None:
            if not fresh:
                quote_cache.refresh_async("sector_board", _fetch_sector_board)
            return cached
        result = _fetch_sector_board()
        quote_cache.put("sector_board", result)
        return result
    except Exception as e:
        logger.error(f"获取行业板块行情失败: {e}", exc_info=True)
        raise


def _fetch_market_breadth() -> Dict[str, Any]:
    df = _get_sector_df_cached()
    up = int(_to_num(df["上涨家数"]).sum())
    down = int(_to_num(df["下跌家数"]).sum())
    chg = df["涨跌幅"].apply(_to_num)
    rising_sectors = int((chg > 0).sum())

    # 股池函数可能随 akshare 版本更名，缺失时不影响主流程
    try:
        import akshare as ak
        zt_fn = getattr(ak, "stock_zt_pool_em", None)
        dt_fn = getattr(ak, "stock_zt_pool_dtgc_em", None)
    except Exception:
        zt_fn = dt_fn = None
    now = datetime.now()
    limit_up = _pool_size(zt_fn, now)
    limit_down = _pool_size(dt_fn, now)

    top = df.loc[chg.idxmax()]
    return {
        "up": up,
        "down": down,
        "limit_up": limit_up,
        "limit_down": limit_down,
        "rising_sectors": rising_sectors,
        "total_sectors": int(len(df)),
        "top_sector": {
            "name": str(top.get("板块", "")),
            "chg_pct": round(_to_num(top.get("涨跌幅")), 2),
        },
        "updated_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    }


def get_market_breadth() -> Dict[str, Any]:
    """市场宽度概览：全市场涨跌家数 + 涨停/跌停家数 + 板块涨跌分布。

    涨跌家数为同花顺 90 个行业的上涨/下跌家数之和（近似全市场）；
    涨停/跌停来自东财股池，网络不可达时为 null，不阻塞主流程。
    本地持久化 SWR 同 get_sector_board。
    """
    try:
        cached, fresh = quote_cache.lookup("market_breadth", _CACHE_TTL)
        if cached is not None:
            if not fresh:
                quote_cache.refresh_async("market_breadth", _fetch_market_breadth)
            return cached
        result = _fetch_market_breadth()
        quote_cache.put("market_breadth", result)
        return result
    except Exception as e:
        logger.error(f"获取市场宽度失败: {e}", exc_info=True)
        raise

# ---------------------------------------------------------------------------
# 首页首屏聚合（W1：单请求替代 N+1；各分量各自走 SWR 缓存，本函数不做整体缓存——
# 启动预热直接调用本函数即可把全部底层缓存填热）
# ---------------------------------------------------------------------------
# 首页指数速览预设（与前端 HomeView 的 INDEX_PRESETS 同步维护；kind=index 防 000001 二义）
OVERVIEW_INDEXES = [
    ("000001", "zh_a", "index"),
    ("000300", "zh_a", "index"),
    ("399001", "zh_a", "index"),
    ("SP500", "us", "index"),
    ("NASDAQ", "us", "index"),
]


def _overview_quote(code: str, market: str, kind: str = "") -> Dict[str, Any]:
    """单个标的的首屏行情摘要（复用 kline 服务的 SWR 缓存；失败返回 error 占位）。"""
    from src.services.kline import get_kline

    try:
        d = get_kline(code, market, days=30, kind=kind)
        closes = [float(row[1]) for row in d.get("ohlcv", []) if row and row[1] is not None]
        close = closes[-1] if closes else 0.0
        prev = closes[-2] if len(closes) > 1 else close
        chg_pct = (close / prev - 1) * 100 if prev else 0.0
        return {
            "code": code, "market": market, "kind": kind,
            "name": d.get("name") or code,
            "close": round(close, 4), "chg_pct": round(chg_pct, 4),
            "closes": closes,
        }
    except Exception as e:
        logger.warning("overview 行情失败: %s %s: %s", code, market, e)
        return {"code": code, "market": market, "kind": kind, "name": code,
                "close": None, "chg_pct": None, "closes": [], "error": str(e)}


def get_market_overview(watch: Optional[List[Dict[str, str]]] = None) -> Dict[str, Any]:
    """首页首屏聚合：指数速览 + 自选行情 + 市场宽度 + 板块，一次请求全拿。

    Round3 并行化：各分量取数互不依赖（各自走 SWR 缓存），冷缓存时串行延迟
    为各 fetch 之和，改为 ThreadPoolExecutor 并发——最慢分量决定整体延迟。
    任意分量失败各自降级（error 占位/None），不整体失败。

    :param watch: 自选标的 [{code, market}]（kind=index 条目不必传——指数走固定预设），最多 10 个
    :return: {indices, watch, breadth, sectors, generated_at}；分量失败各自置 None/占位，不整体失败
    """

    def _safe_quote(code: str, market: str, kind: str = "") -> Dict[str, Any]:
        try:
            return _overview_quote(code, market, kind)
        except Exception as e:  # 防御性兜底（_overview_quote 内部已捕获）
            logger.warning("overview 行情异常: %s %s: %s", code, market, e)
            return {"code": code, "market": market, "kind": kind, "name": code,
                    "close": None, "chg_pct": None, "closes": [], "error": str(e)}

    def _dispatch(kind: str, args: tuple) -> Any:
        """单分量执行器：行情失败回 error 占位；宽度/板块失败回 None（沿用旧降级语义）。"""
        try:
            if kind == "breadth":
                return get_market_breadth()
            if kind == "sectors":
                return get_sector_board()
            return _safe_quote(*args)
        except Exception as e:
            logger.warning("overview 分量 %s 失败: %s", kind, e)
            return None

    jobs: List[Tuple[str, tuple]] = [
        *(("index", (c, m, k)) for c, m, k in OVERVIEW_INDEXES),
        *(("watch", (str((item or {}).get("code", "")).strip(),
                     str((item or {}).get("market") or "zh_a")))
          for item in (watch or [])[:10] if str((item or {}).get("code", "")).strip()),
        ("breadth", ()),
        ("sectors", ()),
    ]

    results: Dict[Tuple[str, str], Any] = {}
    workers = max(1, min(8, len(jobs)))
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers, thread_name_prefix="qdt-overview") as pool:
        future_map = {pool.submit(_dispatch, kind, args): (kind, args) for kind, args in jobs}
        for fut in concurrent.futures.as_completed(future_map):
            kind, args = future_map[fut]
            key = (kind, args[0] if args else kind)
            try:
                results[key] = fut.result()
            except Exception as e:  # 双保险：_dispatch 已兜底，这里防意外穿透
                logger.warning("overview 分量 %s 意外失败: %s", kind, e)
                results[key] = None

    indices = [results.get(("index", c)) or _safe_quote(c, m, k) for c, m, k in OVERVIEW_INDEXES]
    watch_quotes: List[Dict[str, Any]] = []
    for item in (watch or [])[:10]:
        code = str((item or {}).get("code", "")).strip()
        if not code:
            continue
        watch_quotes.append(results.get(("watch", code))
                            or _safe_quote(code, str((item or {}).get("market") or "zh_a")))
    breadth = results.get(("breadth", "breadth"))
    sectors = results.get(("sectors", "sectors"))
    return {
        "indices": indices, "watch": watch_quotes,
        "breadth": breadth, "sectors": sectors,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }
