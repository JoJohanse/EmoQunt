"""数据源健康心跳：进程内记录各数据源最近 N 次取数成败。

供 `/api/data/source-health` 暴露给首页"数据源心跳条"（Uptime Kuma beat bar 模式），
帮助用户理解"为何某股无数据"、排查 akshare/网络抖动。
仅内存态：无外部依赖、进程重启即清零；只在真实发起取数时打点（未启用的源无记录）。
"""
import threading
import time
from collections import deque
from typing import Dict, List

_BEATS_PER_SOURCE = 7

_lock = threading.Lock()
_beats: Dict[str, deque] = {}


def record(source: str, ok: bool) -> None:
    """记录一次取数结果。source 如 'tushare'/'yfinance'/'sina'/'eastmoney'/'baostock'。"""
    with _lock:
        beats = _beats.setdefault(source, deque(maxlen=_BEATS_PER_SOURCE))
        beats.append({"ok": bool(ok), "ts": int(time.time())})


def snapshot() -> Dict[str, List[dict]]:
    """返回全部数据源的心跳记录（旧→新），无记录的源不出现在结果中。"""
    with _lock:
        return {name: list(beats) for name, beats in _beats.items()}
