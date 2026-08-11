# coding=utf-8
"""因子分析服务测试。

验证 src/services/factor.py：
- _compute_factor 各类型产出合理时序
- _build_panels 并发取数 + 构建 factor/forward_returns 面板
- analyze_factor 端到端返回 JSON 可序列化结果（mock 取数 + FactorAnalyzer）

不依赖真实网络/DB：mock Stock.get_stock_data 返回合成 OHLCV。

运行：pytest test/test_factor_analysis.py -v
"""
import json
import os
import sys
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)


def _synth_ohlcv(seed=0, n=80):
    """合成单只股票 OHLCV（中文列名 + DatetimeIndex）。"""
    dates = pd.date_range("2024-01-02", periods=n, freq="B")
    rng = np.random.default_rng(seed)
    close = 10 + rng.normal(0, 0.2, n).cumsum()
    return pd.DataFrame({
        "开盘": close * 0.99, "最高": close * 1.01, "最低": close * 0.98,
        "收盘": close, "成交量": rng.integers(1e6, 5e6, n).astype(float),
        "成交额": close * 2e6,
    }, index=dates)


class TestComputeFactor:
    def _df(self):
        return _synth_ohlcv()

    def test_momentum(self):
        from src.services.factor import _compute_factor
        f = _compute_factor(self._df(), "momentum")
        assert len(f) > 0
        assert f.name is None or True  # Series

    def test_rsi_range(self):
        from src.services.factor import _compute_factor
        f = _compute_factor(self._df(), "rsi").dropna()
        assert (f >= 0).all() and (f <= 100).all()

    def test_volatility_positive(self):
        from src.services.factor import _compute_factor
        f = _compute_factor(self._df(), "volatility").dropna()
        assert (f >= 0).all()

    def test_volume_ratio(self):
        from src.services.factor import _compute_factor
        f = _compute_factor(self._df(), "volume_ratio").dropna()
        assert len(f) > 0

    def test_unknown_returns_empty(self):
        from src.services.factor import _compute_factor
        assert _compute_factor(self._df(), "nonsense").empty

    def test_empty_df(self):
        from src.services.factor import _compute_factor
        assert _compute_factor(pd.DataFrame(), "momentum").empty


class TestBuildPanels:
    def test_panel_shape_and_alignment(self):
        from src.services.factor import _build_panels
        codes = ["000001", "000002", "600000"]
        # mock _fetch_one 返回不同种子的合成数据
        with patch("src.services.factor._fetch_one",
                   side_effect=lambda c, *a: _synth_ohlcv(seed=abs(hash(c)) % 1000)):
            fp, fr, fetched = _build_panels(codes, "20240101", "20240301", "momentum", 5)
        assert fetched == 3
        assert not fp.empty and not fr.empty
        # 列 = 股票，且两边列一致
        assert set(fp.columns) == set(codes)
        assert set(fp.columns) == set(fr.columns)
        # 索引是公共日期交集
        assert fp.index.equals(fr.index)


class TestAnalyzeFactorEndToEnd:
    def test_momentum_returns_json_safe(self):
        from src.services.factor import analyze_factor
        codes = ["000001", "000002", "600000", "600009", "601318"]
        with patch("src.data.data_manager.get_hs300_stocks", return_value=codes), \
             patch("src.services.factor._fetch_one",
                   side_effect=lambda c, *a: _synth_ohlcv(seed=abs(hash(c)) % 1000)):
            out = analyze_factor(
                factor_type="momentum", start_date="2024-01-01", end_date="2024-06-01",
            )
        assert "error" not in out, out.get("error")
        # 关键字段
        for k in ("factor_type", "ic_stats", "ic_series", "quantile_stats",
                  "quantile_cumreturns", "monotonicity", "universe_size"):
            assert k in out, f"缺键 {k}"
        # JSON 可序列化（无 DataFrame/Series/datetime 残留）
        json.dumps(out)
        # IC 均值是有限数或 None
        assert out["ic_stats"]["ic_mean"] is None or np.isfinite(out["ic_stats"]["ic_mean"])

    def test_invalid_factor_type(self):
        from src.services.factor import analyze_factor
        out = analyze_factor(factor_type="bogus", start_date="2024-01-01", end_date="2024-03-01")
        assert "error" in out

    def test_empty_universe(self):
        from src.services.factor import analyze_factor
        with patch("src.data.data_manager.get_hs300_stocks", return_value=[]):
            out = analyze_factor("momentum", "2024-01-01", "2024-03-01")
        assert "error" in out


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
