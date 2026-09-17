"""行情本地持久化缓存（SQLite，可丢弃数据）+ SWR 刷新语义。

为什么独立于 src/store/db.py：行情缓存是**可再生数据**（丢了重拉即可），
业务库是策略/运行的唯一真相——两者生命周期不同，故障域也不同。
库文件 ``data/market_cache.db``（WAL + 每线程连接，模式与 store 一致），
可用 ``QDT_MARKET_CACHE_DB`` 覆盖（测试隔离）。

SWR（stale-while-revalidate）读取语义，服务层用 ``lookup`` 三态：
- 命中且新鲜（age <= max_age）→ ``(payload, True)``  直接返回，毫秒级；
- 命中但过期 → ``(payload, False)``   先返回旧值，调用方用 ``refresh_async``
  后台重拉落库（去重：同 key 在途时不再起线程）；
- 未命中 → ``(None, False)``          调用方同步拉取后 ``put`` 落库。

效果：行情/宽度这类"多源链慢请求"只在每个 TTL 窗口真实出网一次，
且**服务重启后缓存仍在**——首页首次加载也是毫秒级（数据最多旧 max_age 秒，
日线场景无感知）。
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
from typing import Any, Callable, Optional, Tuple

from src.utils.env import get_env

_SCHEMA = """
CREATE TABLE IF NOT EXISTS json_cache (
    cache_key TEXT PRIMARY KEY,
    payload_json TEXT NOT NULL,
    fetched_at REAL NOT NULL
);
"""

_inflight_lock = threading.Lock()
_inflight: set = set()
_local = threading.local()
_init_lock = threading.Lock()
_initialized = False


def _db_path() -> str:
    override = get_env("QDT_MARKET_CACHE_DB", "")
    if override:
        return override
    from src.utils.paths import get_data_dir

    return str(get_data_dir() / "market_cache.db")


def _connect() -> sqlite3.Connection:
    path = _db_path()
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    conn = sqlite3.connect(path, timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def _conn() -> sqlite3.Connection:
    conn = getattr(_local, "conn", None)
    if conn is None:
        conn = _connect()
        _local.conn = conn
    return conn


def _ensure_init() -> None:
    global _initialized
    if not _initialized:
        with _init_lock:
            if not _initialized:
                _conn().executescript(_SCHEMA)
                _conn().commit()
                _initialized = True


def reset_for_tests() -> None:
    """测试隔离：关闭线程连接并复位初始化标记（生产勿用）。"""
    global _initialized
    conn = getattr(_local, "conn", None)
    if conn is not None:
        try:
            conn.close()
        except Exception:
            pass
    _local.conn = None
    with _init_lock:
        _initialized = False


def lookup(key: str, max_age: float) -> Tuple[Optional[Any], bool]:
    """三态读取：见模块 docstring。

    :return: (payload, is_fresh)。payload=None 表示未命中；
             is_fresh=True 表示可直接使用（age <= max_age）。
    """
    _ensure_init()
    try:
        row = _conn().execute(
            "SELECT payload_json, fetched_at FROM json_cache WHERE cache_key = ?", (key,)
        ).fetchone()
    except sqlite3.Error:
        return None, False
    if row is None:
        return None, False
    try:
        payload = json.loads(row[0])
    except (ValueError, TypeError):
        return None, False
    return payload, (time.time() - float(row[1])) <= max_age


def put(key: str, payload: Any) -> None:
    """UPSERT 落库（fetched_at=now）。失败静默（缓存可丢弃，不影响主流程）。"""
    _ensure_init()
    try:
        _conn().execute(
            "INSERT INTO json_cache (cache_key, payload_json, fetched_at) VALUES (?, ?, ?) "
            "ON CONFLICT(cache_key) DO UPDATE SET payload_json=excluded.payload_json, "
            "fetched_at=excluded.fetched_at",
            (key, json.dumps(payload, ensure_ascii=False), time.time()),
        )
        _conn().commit()
    except Exception:
        pass


def refresh_async(key: str, work: Callable[[], Any]) -> None:
    """后台刷新：daemon 线程跑 work() 并 put(key, 结果)；同 key 在途时忽略。

    work 内部异常静默（保留旧缓存继续服务），记 debug 日志。
    """
    with _inflight_lock:
        if key in _inflight:
            return
        _inflight.add(key)

    def _run() -> None:
        try:
            payload = work()
            if payload is not None:
                put(key, payload)
        except Exception:
            import logging

            logging.getLogger(__name__).debug("行情缓存后台刷新失败 key=%s", key, exc_info=True)
        finally:
            with _inflight_lock:
                _inflight.discard(key)

    threading.Thread(target=_run, daemon=True, name="qdt-quote-refresh").start()
