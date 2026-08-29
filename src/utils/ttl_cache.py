"""进程内 TTL 缓存助手（key + fn + ttl + 显式失效）。

统一此前散落在 web_app.py（策略列表 5 分钟）、src/services/market.py（行情速览
5 分钟）、src/factor/daily_recommend.py（每日推荐 1 小时）的手写
"dict + 时间戳" 样板。语义与原实现一致：

- 命中：条目存在且 ``now - 写入时刻 < ttl``，直接返回缓存值；
- 未命中/过期：执行 ``fn()`` 并写回（fn 抛异常时不写缓存，原样上抛）；
- 显式失效：``invalidate(key)`` / ``clear()``；``set(key, value)`` 强制写回。

仅进程内单机语义。"谁写谁失效"：写路径所在 module 在变更成功后自行
invalidate；跨进程/持久化缓存请走 src.data 缓存层，勿混用。
"""
import threading
import time
from typing import Any, Callable, Dict, Optional, Tuple

# 条目结构：(写入时刻, 缓存值)
_Entry = Tuple[float, Any]


def _now() -> float:
    """时间源（独立函数便于单测 monkeypatch 假时钟）。"""
    return time.time()


class TTLCache:
    """进程内 TTL 缓存。

    线程安全：读写加锁，``fn`` 执行不在锁内（并发未命中允许重复加载，
    与原手写实现一致，不串行长耗时 fn）。

    :param default_ttl: 默认存活秒数；``get_or_set`` 未显式传 ttl 时使用
    """

    def __init__(self, default_ttl: Optional[float] = None):
        self._store: Dict[Any, _Entry] = {}
        self._lock = threading.Lock()
        self._default_ttl = default_ttl

    def get_or_set(self, key, fn: Callable[[], Any], ttl: Optional[float] = None) -> Any:
        """命中返回缓存值，否则执行 fn 并写回。

        :param key: 缓存键（任意可哈希对象，通常为 str）
        :param fn: 惰性加载函数（无参）
        :param ttl: 存活秒数；缺省用构造时的 default_ttl
        :raises TypeError: ttl 未提供且构造时也未设置 default_ttl
        """
        if ttl is None:
            ttl = self._default_ttl
        if ttl is None:
            raise TypeError("get_or_set 需要显式 ttl 或构造时设置 default_ttl")
        with self._lock:
            hit = self._store.get(key)
            if hit is not None and _now() - hit[0] < ttl:
                return hit[1]
        value = fn()
        with self._lock:
            self._store[key] = (_now(), value)
        return value

    def set(self, key, value: Any) -> None:
        """强制写入（以当前时刻为写入时间，供刷新路径复用）。"""
        with self._lock:
            self._store[key] = (_now(), value)

    def invalidate(self, key) -> None:
        """显式失效单个 key（不存在时静默）。"""
        with self._lock:
            self._store.pop(key, None)

    def clear(self) -> None:
        """清空全部条目。"""
        with self._lock:
            self._store.clear()
