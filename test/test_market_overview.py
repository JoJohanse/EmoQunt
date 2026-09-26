# coding=utf-8
"""market.get_market_overview 并行聚合单测（Round3）。

用 stub 分量验证首屏聚合契约：
- 指数固定预设全量返回 + watch 自选逐只行情
- 单分量失败各自降级（行情 error 占位 / 宽度板块 None），不整体失败
- 返回结构 {indices, watch, breadth, sectors, generated_at}

不依赖网络。运行：pytest test/test_market_overview.py -v
"""
import os
import sys

import pytest

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from src.services import market


def _quote_stub(code, market_, kind=""):
    return {"code": code, "market": market_, "kind": kind, "name": code,
            "close": 1.0, "chg_pct": 0.5, "closes": [1.0, 1.1]}


@pytest.fixture
def _stubs(monkeypatch):
    """替换三个分量取数函数：行情正常、宽度抛错、板块正常。"""
    monkeypatch.setattr(market, "_overview_quote", _quote_stub)
    monkeypatch.setattr(market, "get_market_breadth",
                        lambda: (_ for _ in ()).throw(RuntimeError("breadth down")))
    monkeypatch.setattr(market, "get_sector_board", lambda: {"sectors": []})


class TestOverviewContract:
    def test_indices_and_watch_returned(self, _stubs):
        out = market.get_market_overview(watch=[{"code": "AAPL", "market": "us"}])
        assert len(out["indices"]) == len(market.OVERVIEW_INDEXES)
        assert all(i["close"] == 1.0 for i in out["indices"])
        assert len(out["watch"]) == 1 and out["watch"][0]["code"] == "AAPL"
        assert "generated_at" in out

    def test_component_failure_degrades_not_crashes(self, _stubs):
        """宽度分量抛错 → breadth=None，整体不失败。"""
        out = market.get_market_overview()
        assert out["breadth"] is None
        assert out["sectors"] == {"sectors": []}
        assert len(out["indices"]) == len(market.OVERVIEW_INDEXES)

    def test_quote_failure_yields_error_placeholder(self, monkeypatch):
        """行情分量抛错 → error 占位条目（name 回填 code）。"""
        def _boom(code, market_, kind=""):
            raise RuntimeError("quote down")
        monkeypatch.setattr(market, "_overview_quote", _boom)
        monkeypatch.setattr(market, "get_market_breadth", lambda: {"up": 1})
        monkeypatch.setattr(market, "get_sector_board", lambda: {"sectors": []})
        out = market.get_market_overview()
        assert len(out["indices"]) == len(market.OVERVIEW_INDEXES)
        assert all(i.get("error") for i in out["indices"])

    def test_empty_and_blank_watch_skipped(self, _stubs):
        out = market.get_market_overview(watch=[{"code": ""}, None, {"code": "  "}])
        assert out["watch"] == []

    def test_watch_capped_at_ten(self, _stubs):
        watch = [{"code": f"00{i:04d}", "market": "zh_a"} for i in range(15)]
        out = market.get_market_overview(watch=watch)
        assert len(out["watch"]) == 10


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
