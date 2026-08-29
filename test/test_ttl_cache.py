# coding=utf-8
"""TTL 缓存助手 (src/utils/ttl_cache.py) 纯逻辑单元测试。

覆盖：
- get_or_set：未命中加载写回、命中不重复执行、TTL 过期重载、
  default_ttl 回退、缺 ttl 报 TypeError、fn 抛异常不污染缓存
- 显式失效：invalidate / clear / set 强制写回
- 假时钟：monkeypatch src.utils.ttl_cache._now

运行：pytest test/test_ttl_cache.py -v
"""
import os
import sys

import pytest

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import src.utils.ttl_cache as ttl_cache


class FakeClock:
    """可手动推进的假时钟，替换 ttl_cache._now。"""

    def __init__(self, start=1000.0):
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


@pytest.fixture
def clock(monkeypatch):
    c = FakeClock()
    monkeypatch.setattr(ttl_cache, "_now", c)
    return c


def _counting_fn(calls, value="v1"):
    def fn():
        calls.append(1)
        return value
    return fn


class TestGetOrSet:
    """get_or_set 命中/加载语义。"""

    def test_miss_loads_and_hit_does_not_reload(self, clock):
        cache = ttl_cache.TTLCache()
        calls = []
        fn = _counting_fn(calls)

        assert cache.get_or_set("k", fn, ttl=60) == "v1"
        assert cache.get_or_set("k", fn, ttl=60) == "v1"
        assert len(calls) == 1

    def test_expires_after_ttl(self, clock):
        cache = ttl_cache.TTLCache()
        calls = []
        fn = _counting_fn(calls)

        cache.get_or_set("k", fn, ttl=60)
        clock.advance(59)
        cache.get_or_set("k", fn, ttl=60)  # 仍在 TTL 内，命中
        clock.advance(2)  # 累计 61s > 60s，过期
        cache.get_or_set("k", fn, ttl=60)

        assert len(calls) == 2

    def test_default_ttl_from_constructor(self, clock):
        cache = ttl_cache.TTLCache(default_ttl=10)
        calls = []
        fn = _counting_fn(calls)

        cache.get_or_set("k", fn)
        cache.get_or_set("k", fn)  # 命中
        clock.advance(11)
        cache.get_or_set("k", fn)  # 过期重载

        assert len(calls) == 2

    def test_explicit_ttl_overrides_default(self, clock):
        cache = ttl_cache.TTLCache(default_ttl=10)
        calls = []
        fn = _counting_fn(calls)

        cache.get_or_set("k", fn, ttl=100)
        clock.advance(50)
        cache.get_or_set("k", fn, ttl=100)  # 显式 ttl 未过期，命中

        assert len(calls) == 1

    def test_missing_ttl_raises_type_error(self, clock):
        cache = ttl_cache.TTLCache()
        with pytest.raises(TypeError):
            cache.get_or_set("k", lambda: "v")

    def test_fn_exception_not_cached(self, clock):
        cache = ttl_cache.TTLCache()
        state = {"fail": True}

        def fn():
            if state["fail"]:
                raise RuntimeError("boom")
            return "ok"

        with pytest.raises(RuntimeError):
            cache.get_or_set("k", fn, ttl=60)
        state["fail"] = False
        # 异常未写缓存：恢复后应重新执行 fn
        assert cache.get_or_set("k", fn, ttl=60) == "ok"

    def test_keys_are_independent(self, clock):
        cache = ttl_cache.TTLCache()
        calls = []
        fn = _counting_fn(calls)

        cache.get_or_set("a", fn, ttl=60)
        cache.get_or_set("b", fn, ttl=60)

        assert len(calls) == 2


class TestInvalidation:
    """显式失效语义。"""

    def test_invalidate_forces_reload(self, clock):
        cache = ttl_cache.TTLCache()
        calls = []

        cache.get_or_set("k", _counting_fn(calls, "old"), ttl=60)
        cache.invalidate("k")
        assert cache.get_or_set("k", _counting_fn(calls, "new"), ttl=60) == "new"
        assert len(calls) == 2

    def test_invalidate_missing_key_is_silent(self, clock):
        cache = ttl_cache.TTLCache()
        cache.invalidate("no-such-key")  # 不应抛异常

    def test_clear_drops_all_entries(self, clock):
        cache = ttl_cache.TTLCache()
        calls = []
        fn = _counting_fn(calls)

        cache.get_or_set("a", fn, ttl=60)
        cache.get_or_set("b", fn, ttl=60)
        cache.clear()
        cache.get_or_set("a", fn, ttl=60)
        cache.get_or_set("b", fn, ttl=60)

        assert len(calls) == 4

    def test_set_forces_value_and_resets_timestamp(self, clock):
        cache = ttl_cache.TTLCache()
        calls = []
        fn = _counting_fn(calls, "loaded")

        cache.get_or_set("k", fn, ttl=60)
        cache.set("k", "forced")
        clock.advance(59)  # 接近过期但未过期
        assert cache.get_or_set("k", fn, ttl=60) == "forced"
        clock.advance(2)  # set 时刻起 61s，过期重载
        cache.get_or_set("k", fn, ttl=60)

        assert len(calls) == 2
