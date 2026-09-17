"""行情本地持久化缓存测试（quote_cache + kline/market 接线）。

SWR 三态（新鲜/过期/未命中）、UPSERT、kline tail 模式缓存命中与
区间模式绕过、market breadth 文件缓存。库文件经 QDT_MARKET_CACHE_DB 隔离。
"""
import os
import sys
import tempfile
import time

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_TMPDIR = tempfile.mkdtemp(prefix="emoqunt_quotecache_test_")

from src.data import quote_cache as qc  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def _isolated_db():
    os.environ["QDT_MARKET_CACHE_DB"] = os.path.join(_TMPDIR, "market_cache.db")
    qc.reset_for_tests()
    yield
    qc.reset_for_tests()


class TestQuoteCache:
    def test_miss_then_put_fresh(self):
        payload, fresh = qc.lookup("k|a", max_age=60)
        assert payload is None and fresh is False
        qc.put("k|a", {"v": 1})
        payload, fresh = qc.lookup("k|a", max_age=60)
        assert payload == {"v": 1} and fresh is True

    def test_stale_when_expired(self):
        qc.put("k|b", {"v": 2})
        # 时间倒流：把 fetched_at 改到 10 分钟前
        conn = qc._conn()
        conn.execute("UPDATE json_cache SET fetched_at = fetched_at - 600 WHERE cache_key = 'k|b'")
        conn.commit()
        payload, fresh = qc.lookup("k|b", max_age=60)
        assert payload == {"v": 2} and fresh is False

    def test_upsert_overwrites(self):
        qc.put("k|c", {"v": 1})
        qc.put("k|c", {"v": 2})
        payload, fresh = qc.lookup("k|c", max_age=60)
        assert payload == {"v": 2} and fresh is True

    def test_refresh_async_persists_result(self):
        qc.put("k|d", {"v": "old"})
        qc.refresh_async("k|d", lambda: {"v": "new"})
        deadline = time.time() + 5
        while time.time() < deadline:
            payload, _ = qc.lookup("k|d", max_age=60)
            if payload == {"v": "new"}:
                return
            time.sleep(0.05)
        raise AssertionError("后台刷新未落库")

    def test_refresh_async_keeps_old_on_error(self):
        qc.put("k|e", {"v": "old"})
        def _boom():
            raise RuntimeError("x")
        qc.refresh_async("k|e", _boom)
        time.sleep(0.3)
        payload, _ = qc.lookup("k|e", max_age=60)
        assert payload == {"v": "old"}


class TestKlineCacheWiring:
    def _patch_fetch(self, monkeypatch, counter):
        """替换 _fetch_and_shape：计数调用并返回形状固定的假结果。"""
        from src.services import kline as ksvc

        def fake_fetch(stock_code, market, days, period, adjust, kind, is_index,
                       start_date, end_date, range_mode):
            counter["n"] += 1
            return {
                "code": stock_code, "market": market, "name": "X",
                "dates": ["2024-01-02", "2024-01-03"],
                "ohlcv": [[1.0, 1.0, 1.0, 1.0], [1.0, 1.0, 1.0, 1.0]],
                "volumes": [100, 100], "period": period, "adjust": adjust,
                "kind": "index" if is_index else "",
            }
        monkeypatch.setattr(ksvc, "_fetch_and_shape", fake_fetch)

    def test_second_call_hits_cache(self, monkeypatch):
        counter = {"n": 0}
        self._patch_fetch(monkeypatch, counter)
        from src.services.kline import get_kline

        r1 = get_kline("000001", market="zh_a", days=30, kind="index")
        r2 = get_kline("000001", market="zh_a", days=30, kind="index")
        assert counter["n"] == 1  # 第二次命中缓存
        assert r1 == r2

    def test_different_keys_do_not_collide(self, monkeypatch):
        counter = {"n": 0}
        self._patch_fetch(monkeypatch, counter)
        from src.services.kline import get_kline

        # 独占代码（600100/600200），避免与其它测试的缓存键残留串扰
        get_kline("600100", market="zh_a", days=30)
        get_kline("600200", market="zh_a", days=30)
        assert counter["n"] == 2

    def test_range_mode_bypasses_cache(self, monkeypatch):
        counter = {"n": 0}
        self._patch_fetch(monkeypatch, counter)
        from src.services.kline import get_kline

        get_kline("000001", market="zh_a", days=30, start_date="2024-01-01", end_date="2024-02-01")
        get_kline("000001", market="zh_a", days=30, start_date="2024-01-01", end_date="2024-02-01")
        assert counter["n"] == 2  # 区间模式（回测买卖点对齐）不走缓存

    def test_stale_returns_old_and_refreshes(self, monkeypatch):
        counter = {"n": 0}
        self._patch_fetch(monkeypatch, counter)
        from src.services.kline import get_kline
        from src.data import quote_cache as qc

        get_kline("600000", market="zh_a", days=30)
        assert counter["n"] == 1
        # 人为过期
        conn = qc._conn()
        conn.execute("UPDATE json_cache SET fetched_at = fetched_at - 600 WHERE cache_key LIKE 'kline|zh_a|stock|600000|%'")
        conn.commit()
        r = get_kline("600000", market="zh_a", days=30)  # 立即返回旧值（不阻塞等刷新）
        assert r["code"] == "600000"
        deadline = time.time() + 5  # 后台刷新异步完成
        while time.time() < deadline and counter["n"] < 2:
            time.sleep(0.05)
        assert counter["n"] == 2


class TestMarketCache:
    def test_breadth_cached_across_calls(self, monkeypatch):
        from src.services import market as msvc

        calls = {"n": 0}
        def fake_fetch():
            calls["n"] += 1
            return {"up": 1, "down": 2, "updated_at": "t"}
        monkeypatch.setattr(msvc, "_fetch_market_breadth", fake_fetch)
        os.environ["QDT_MARKET_CACHE_DB"] = os.path.join(_TMPDIR, "market_cache.db")
        qc.reset_for_tests()
        r1 = msvc.get_market_breadth()
        r2 = msvc.get_market_breadth()
        assert calls["n"] == 1 and r1 == r2
