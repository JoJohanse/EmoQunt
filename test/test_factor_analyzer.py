# coding=utf-8
"""因子分析模块 (src/analysis/factor_analyzer.py) 单元测试。

覆盖 FactorPreprocessor 的预处理方法：
- winsorize 去极值
- z_score_normalize 标准化（standard / robust / 手动）
- neutralize_by_group 按组中性化
- neutralize_by_market_cap 市值中性化
- neutralize_by_industry / industry_dummy_neutralize 行业中性化
- rank_transform 排序变换
- orthogonalize_factors 正交化

使用合成面板（index=日期, columns=股票）测试，不依赖外部数据。

运行：pytest test/test_factor_analyzer.py -v
"""
import os
import sys

import numpy as np
import pandas as pd
import pytest

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from src.analysis.factor_analyzer import FactorPreprocessor


@pytest.fixture
def factor_panel():
    """合成因子面板：2 日 × 4 股，D 为极端值。"""
    dates = pd.date_range("2024-01-01", periods=2, freq="D")
    stocks = ["A", "B", "C", "D"]
    data = np.array([
        [1.0, 2.0, 3.0, 100.0],
        [2.0, 4.0, 6.0, 200.0],
    ])
    return pd.DataFrame(data, index=dates, columns=stocks)


@pytest.fixture
def group_panel(factor_panel):
    """与因子面板对齐的分组数据：A/B 同组 g1，C/D 同组 g2。"""
    arr = np.array([["g1", "g1", "g2", "g2"]] * len(factor_panel.index))
    return pd.DataFrame(arr, index=factor_panel.index, columns=factor_panel.columns)


class TestWinsorize:
    """去极值测试。"""

    def test_clips_extreme(self, factor_panel):
        out = FactorPreprocessor().winsorize(factor_panel, limits=(0.25, 0.25))
        # D 原为 100，应被裁剪到上分位附近
        assert out.loc[out.index[0], "D"] < 100.0
        assert out.shape == factor_panel.shape

    def test_preserves_shape(self, factor_panel):
        out = FactorPreprocessor().winsorize(factor_panel, limits=(0.025, 0.025))
        assert out.shape == factor_panel.shape


class TestZScoreNormalize:
    """标准化测试。"""

    def test_standard_mean_zero_std_one(self, factor_panel):
        out = FactorPreprocessor().z_score_normalize(factor_panel, method="standard")
        row = out.iloc[0].dropna()
        assert row.mean() == pytest.approx(0.0, abs=1e-9)
        # StandardScaler 使用总体标准差（ddof=0）
        assert row.std(ddof=0) == pytest.approx(1.0, abs=1e-6)

    def test_robust_method(self, factor_panel):
        out = FactorPreprocessor().z_score_normalize(factor_panel, method="robust")
        assert out.shape == factor_panel.shape
        assert not out.isna().all().all()

    def test_manual_fallback(self, factor_panel):
        out = FactorPreprocessor().z_score_normalize(factor_panel, method="manual")
        row = out.iloc[0].dropna()
        assert row.mean() == pytest.approx(0.0, abs=1e-9)


class TestNeutralizeByGroup:
    """按组中性化测试。"""

    def test_subtracts_group_mean(self, factor_panel, group_panel):
        out = FactorPreprocessor().neutralize_by_group(factor_panel, group_panel)
        row0 = factor_panel.iloc[0]
        # g1 = {A, B}，A 应等于 A - mean(A, B)
        assert out.iloc[0]["A"] == pytest.approx(row0["A"] - (row0["A"] + row0["B"]) / 2)
        # g2 = {C, D}
        assert out.iloc[0]["D"] == pytest.approx(row0["D"] - (row0["C"] + row0["D"]) / 2)

    def test_neutralize_by_industry_alias(self, factor_panel, group_panel):
        # neutralize_by_industry 应委托给 neutralize_by_group
        out = FactorPreprocessor().neutralize_by_industry(factor_panel, group_panel)
        assert out.shape == factor_panel.shape


class TestNeutralizeByMarketCap:
    """市值中性化测试。"""

    def test_returns_residuals(self, factor_panel):
        mcap = pd.DataFrame(
            [[1e10, 2e10, 3e10, 4e10]] * len(factor_panel.index),
            index=factor_panel.index, columns=factor_panel.columns,
        )
        out = FactorPreprocessor().neutralize_by_market_cap(factor_panel, mcap)
        assert out.shape == factor_panel.shape
        assert not out.isna().all().all()


class TestIndustryDummyNeutralize:
    """行业哑变量中性化测试。"""

    def test_shape_preserved(self, factor_panel, group_panel):
        out = FactorPreprocessor().industry_dummy_neutralize(factor_panel, group_panel)
        assert out.shape == factor_panel.shape
        assert not out.isna().all().all()


class TestRankTransform:
    """排序变换测试。"""

    def test_shape_and_finite(self, factor_panel):
        out = FactorPreprocessor().rank_transform(factor_panel)
        assert out.shape == factor_panel.shape
        assert not out.isna().all().all()


class TestOrthogonalizeFactors:
    """正交化测试。"""

    def test_residuals_near_zero_when_identical(self, factor_panel):
        """目标因子与参考因子完全相同时，残差应接近 0。"""
        out = FactorPreprocessor().orthogonalize_factors(factor_panel, [factor_panel.copy()])
        assert out.shape == factor_panel.shape
        # 残差应非常接近 0
        assert out.abs().max().max() == pytest.approx(0.0, abs=1e-6)

    def test_shape_with_distinct_reference(self, factor_panel):
        ref = factor_panel * 0.5
        out = FactorPreprocessor().orthogonalize_factors(factor_panel, [ref])
        assert out.shape == factor_panel.shape


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
