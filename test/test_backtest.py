"""回测模块单元测试。

覆盖 Phase 0-3 的核心逻辑：
- AShareCommInfo：印花税仅卖出、最低佣金、过户费
- extract_param_value / build_param_dict：value/default 键与类型转换
- calculate_strategy_metrics：总收益/年化/夏普/最大回撤，及胜率/盈亏比覆盖
- PerformanceAnalyzer.calculate_alpha_beta：协方差法

运行：pytest test/test_backtest.py -v
（需在项目 conda 环境 qdt 中，依赖 backtrader/pandas/numpy）
"""
import os
import sys

import numpy as np
import pandas as pd
import pytest

# 确保项目根在 sys.path（从 test/ 目录直接 pytest 时也生效）
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)


# ---------------------------------------------------------------------------
# Phase 2: AShareCommInfo
# ---------------------------------------------------------------------------
class TestAShareCommInfo:
    """A股真实交易成本模型测试。"""

    def _make(self, **kw):
        from src.backtest.backtest_manager import AShareCommInfo
        return AShareCommInfo(**kw)

    def test_stamp_duty_only_on_sell(self):
        """印花税只在卖出收取，买入为 0。"""
        ci = self._make(stamp_duty=0.0005)
        buy_fee = ci._getcommission(1000, 10.0, False)    # 买入
        sell_fee = ci._getcommission(-1000, 10.0, False)  # 卖出
        # 成交额 10000；佣金 max(10000*0.0003,5)=5；过户费 10000*0.00001=0.1
        # 买入：5 + 0.1 + 0(印花税) = 5.1
        # 卖出：5 + 0.1 + 5(印花税) = 10.1
        assert buy_fee == pytest.approx(5.1, abs=1e-6)
        assert sell_fee == pytest.approx(10.1, abs=1e-6)
        # 印花税恰好是差值
        assert (sell_fee - buy_fee) == pytest.approx(
            10000 * 0.0005, abs=1e-6
        )

    def test_min_commission_floor(self):
        """单笔佣金不低于最低收费（小额交易命中下限）。"""
        ci = self._make(commission_rate=0.0003, min_commission=5.0)
        # 成交额仅 100 元，按比例佣金 0.03 元 -> 命中最低 5 元
        fee = ci._getcommission(10, 10.0, False)
        # 5（最低佣金）+ 0.001（过户费 100*0.00001）= 5.001
        assert fee == pytest.approx(5.001, abs=1e-6)

    def test_transfer_fee_both_sides(self):
        """过户费双边收取，买卖相等。"""
        ci = self._make(transfer_fee_rate=0.00001, stamp_duty=0.0, min_commission=0.0)
        buy_fee = ci._getcommission(1000, 10.0, False)
        sell_fee = ci._getcommission(-1000, 10.0, False)
        # 印花税设 0 后，买卖费用应完全相等
        assert buy_fee == pytest.approx(sell_fee, abs=1e-9)

    def test_fee_always_nonnegative(self):
        """费用恒为正数（即便成交量为 0）。"""
        ci = self._make()
        for size in [0, 1, -1, 1000, -1000]:
            assert ci._getcommission(size, 10.0, False) >= 0


# ---------------------------------------------------------------------------
# Phase 0: extract_param_value / build_param_dict
# ---------------------------------------------------------------------------
class TestParamExtraction:
    """参数解析测试（修复 Bug 1.1：value/default 键不匹配）。"""

    def test_value_key_recognized(self):
        from src.Strategy.Strategy import extract_param_value
        # strategies.json 实际写入的是 "value"
        assert extract_param_value({"name": "short_period", "value": 5, "type": "int"}) == ("short_period", 5)

    def test_default_key_recognized(self):
        from src.Strategy.Strategy import extract_param_value
        # 模板里用的是 "default"
        assert extract_param_value({"name": "long_period", "default": 30, "type": "int"}) == ("long_period", 30)

    def test_value_overrides_default(self):
        from src.Strategy.Strategy import extract_param_value
        # 两者并存时优先 value
        assert extract_param_value(
            {"name": "x", "value": 7, "default": 3, "type": "int"}
        ) == ("x", 7)

    def test_type_conversion(self):
        from src.Strategy.Strategy import extract_param_value
        assert extract_param_value({"name": "a", "value": "5", "type": "int"}) == ("a", 5)
        assert isinstance(extract_param_value({"name": "a", "value": "5", "type": "int"})[1], int)
        assert extract_param_value({"name": "b", "value": "0.3", "type": "float"}) == ("b", 0.3)
        assert isinstance(extract_param_value({"name": "b", "value": "0.3", "type": "float"})[1], float)
        assert extract_param_value({"name": "c", "value": "true", "type": "bool"}) == ("c", True)
        assert extract_param_value({"name": "d", "value": "0", "type": "bool"}) == ("d", False)

    def test_missing_value_returns_none(self):
        from src.Strategy.Strategy import extract_param_value
        assert extract_param_value({"name": "x", "type": "int"}) == (None, None)
        assert extract_param_value({"value": 5, "type": "int"}) == (None, None)

    def test_build_param_dict_user_overrides_template(self):
        """用户配置覆盖模板默认值。"""
        from src.Strategy.Strategy import build_param_dict
        d = build_param_dict({
            "template": "sentiment_ma",
            "parameters": [
                {"name": "short_period", "value": 13, "type": "int"},
                {"name": "use_sentiment_filter", "value": False, "type": "bool"},
            ],
        })
        assert d["short_period"] == 13            # 用户覆盖
        assert d["long_period"] == 20             # 模板默认保留
        assert d["use_sentiment_filter"] is False  # 用户覆盖


# ---------------------------------------------------------------------------
# Phase 1: calculate_strategy_metrics
# ---------------------------------------------------------------------------
class TestCalculateStrategyMetrics:
    """绩效指标计算测试（含 Bug 1.2/1.3 修复验证）。"""

    def _equity(self, start, end, n=252):
        """构造一条线性增长的净值序列。"""
        idx = pd.date_range("2024-01-01", periods=n, freq="D")
        values = np.linspace(start, end, n)
        return pd.Series(values, index=idx)

    def test_total_return(self):
        from src.backtest.backtest_manager import calculate_strategy_metrics
        eq = self._equity(100000, 120000, n=252)
        m = calculate_strategy_metrics(eq)
        assert m["总收益率"] == pytest.approx(0.20, abs=1e-9)

    def test_annualized_return_positive(self):
        from src.backtest.backtest_manager import calculate_strategy_metrics
        eq = self._equity(100000, 120000, n=252)  # 恰好 252 个交易日 -> 年化≈总收益
        m = calculate_strategy_metrics(eq)
        assert m["年化收益率"] == pytest.approx(0.20, abs=1e-6)

    def test_max_drawdown_nonpositive(self):
        from src.backtest.backtest_manager import calculate_strategy_metrics
        # 先涨后跌的净值，确保产生回撤
        idx = pd.date_range("2024-01-01", periods=100, freq="D")
        values = list(np.linspace(100000, 130000, 50)) + list(np.linspace(130000, 110000, 50))
        eq = pd.Series(values, index=idx)
        m = calculate_strategy_metrics(eq)
        assert m["最大回撤"] < 0  # 当前实现 drawdown.min() 为负
        assert -0.20 <= m["最大回撤"] <= 0.0

    def test_win_rate_override_used(self):
        """胜率覆盖：传入真实交易级胜率应被采用，而非按盈利日。"""
        from src.backtest.backtest_manager import calculate_strategy_metrics
        eq = self._equity(100000, 120000, n=252)
        m = calculate_strategy_metrics(eq, win_rate_override=0.65, profit_loss_ratio_override=2.5)
        assert m["胜率"] == 0.65
        assert m["盈亏比"] == 2.5

    def test_win_rate_fallback_when_no_override(self):
        """未提供覆盖时回退到旧（按日）口径——此时单调上涨净值胜率应为 1.0。"""
        from src.backtest.backtest_manager import calculate_strategy_metrics
        eq = self._equity(100000, 120000, n=252)  # 每日都涨
        m = calculate_strategy_metrics(eq)
        # 单调上涨 -> 每个交易日收益为正 -> 旧口径胜率=1.0
        assert m["胜率"] == pytest.approx(1.0, abs=1e-9)


# ---------------------------------------------------------------------------
# Phase 3: Alpha/Beta（协方差法）
# ---------------------------------------------------------------------------
class TestAlphaBeta:
    """Alpha/Beta 协方差法测试。"""

    def test_beta_of_replicated_benchmark(self):
        """策略收益率 = 基准收益率时，Beta 应为 1，Alpha ≈ 0。"""
        from src.backtest.backtest_manager import PerformanceAnalyzer
        rng = np.random.default_rng(42)
        bench = pd.Series(rng.normal(0.001, 0.02, 300))
        strat = bench.copy()  # 完全跟随基准
        a = PerformanceAnalyzer(strat, bench)
        alpha, beta = a.calculate_alpha_beta()
        assert beta == pytest.approx(1.0, abs=1e-6)
        # alpha 接近 0（仅因无风险利率项造成微小偏移）
        assert abs(alpha) < 0.05

    def test_beta_zero_for_uncorrelated(self):
        """策略与基准不相关时，Beta 接近 0。"""
        from src.backtest.backtest_manager import PerformanceAnalyzer
        rng = np.random.default_rng(7)
        bench = pd.Series(rng.normal(0, 1, 2000))
        strat = pd.Series(rng.normal(0, 1, 2000))
        a = PerformanceAnalyzer(strat, bench)
        _, beta = a.calculate_alpha_beta()
        assert abs(beta) < 0.1

    def test_alpha_beta_without_benchmark(self):
        """无基准时返回 (0, 0)。"""
        from src.backtest.backtest_manager import PerformanceAnalyzer
        rng = np.random.default_rng(0)
        strat = pd.Series(rng.normal(0, 0.01, 100))
        a = PerformanceAnalyzer(strat, None)
        alpha, beta = a.calculate_alpha_beta()
        assert alpha == 0.0 and beta == 0.0


# ---------------------------------------------------------------------------
# Phase 3 / 4: 数据层（面板构建）
# ---------------------------------------------------------------------------
class TestSentimentSnapshots:
    """情绪快照面板构建测试。"""

    def test_panel_shape_and_normalization(self):
        """面板应为 日期×行业，且情绪归一化到 -1..1。"""
        from src.data.data_manager import load_sentiment_snapshots
        panel = load_sentiment_snapshots()
        if panel.empty:
            pytest.skip("无本地情绪快照，跳过")
        assert panel.index.name == "日期"
        # 原始 0-100 -> (s-50)/50 -> 范围 [-1, 1]
        assert panel.values.min() >= -1.0 - 1e-9
        assert panel.values.max() <= 1.0 + 1e-9

    def test_stock_series_lookup(self):
        """已知成分股能定位到行业。"""
        from src.data.data_manager import load_sentiment_snapshots, build_stock_sentiment_series
        panel = load_sentiment_snapshots()
        if panel.empty:
            pytest.skip("无本地情绪快照，跳过")
        # 600938 中国海油，快照里显式列在"石油行业"
        series, sector = build_stock_sentiment_series(panel, "600938")
        assert sector == "石油行业"
        assert len(series) == panel.shape[0]
        assert series.name == "石油行业"


# ---------------------------------------------------------------------------
# 美股功能：校验、成本模型、指数映射
# ---------------------------------------------------------------------------
class TestUSValidation:
    """美股代码校验测试。"""

    def test_us_valid_tickers(self):
        from src.utils.validators import validate_us_stock_code
        for t in ["AAPL", "MSFT", "BRK.B", "aapl", "TSLA", "BABA"]:
            assert validate_us_stock_code(t) == (True, None), f"{t} 应通过"

    def test_us_reject_pure_digits(self):
        """纯数字不应通过（避免与 A 股 6 位代码混淆）。"""
        from src.utils.validators import validate_us_stock_code
        for t in ["", "123456", "123", "0", "007"]:
            ok, _ = validate_us_stock_code(t)
            assert ok is False, f"{t!r} 应被拒绝"

    def test_us_reject_too_long_or_bad_chars(self):
        from src.utils.validators import validate_us_stock_code
        for t in ["TOOLONGCODE", "AA-BB", "AA BB", "A@B"]:
            ok, _ = validate_us_stock_code(t)
            assert ok is False, f"{t!r} 应被拒绝"

    def test_validate_stock_code_market_routing(self):
        """validate_stock_code 按 market 参数路由到美股/A股校验。"""
        from src.utils.validators import validate_stock_code
        # 美股路径：AAPL 通过，000001 失败
        assert validate_stock_code("AAPL", market="us")[0] is True
        assert validate_stock_code("000001", market="us")[0] is False
        # A 股路径（默认）：000001 通过，AAPL 失败
        assert validate_stock_code("000001")[0] is True
        assert validate_stock_code("000001", market="zh_a")[0] is True
        assert validate_stock_code("AAPL")[0] is False

    def test_validate_backtest_params_market_passthrough(self):
        """validate_backtest_params 透传 market 参数。"""
        from src.utils.validators import validate_backtest_params
        ok, _ = validate_backtest_params(
            "AAPL", "2024-01-01", "2024-06-30", 100000.0, 0.0005, market="us")
        assert ok is True
        # 美股模式下 000001 应失败
        ok, _ = validate_backtest_params(
            "000001", "2024-01-01", "2024-06-30", 100000.0, 0.0005, market="us")
        assert ok is False


class TestUSStockCommInfo:
    """美股成本模型测试（对比 A 股的不对称性）。"""

    def test_us_commission_symmetric(self):
        """美股佣金买卖对称（无印花税）。"""
        from src.backtest.backtest_manager import USStockCommInfo
        ci = USStockCommInfo(commission_rate=0.0005)
        buy = ci._getcommission(100, 200.0, False)
        sell = ci._getcommission(-100, 200.0, False)
        # 成交额 20000，佣金 20000 * 5e-4 = 10
        assert buy == pytest.approx(10.0, abs=1e-9)
        assert sell == pytest.approx(10.0, abs=1e-9)
        assert buy == sell

    def test_us_no_stamp_duty(self):
        """美股卖出费用等于买入费用（无印花税额外项）。"""
        from src.backtest.backtest_manager import USStockCommInfo
        ci = USStockCommInfo()
        assert ci._getcommission(1000, 10.0, False) == ci._getcommission(-1000, 10.0, False)

    def test_us_vs_a_share_asymmetry(self):
        """美股对称 vs A 股卖出更贵（印花税）。"""
        from src.backtest.backtest_manager import USStockCommInfo, AShareCommInfo
        us = USStockCommInfo()
        ac = AShareCommInfo()
        us_buy = us._getcommission(1000, 10.0, False)
        us_sell = us._getcommission(-1000, 10.0, False)
        ac_sell = ac._getcommission(-1000, 10.0, False)
        # 美股买卖相等
        assert us_buy == us_sell
        # A 股卖出（含印花税）严格大于美股卖出
        assert ac_sell > us_sell


class TestUSIndexSymbols:
    """美股指数映射测试。"""

    def test_us_index_symbols_mapping(self):
        from src.data.data_manager import US_INDEX_SYMBOLS
        assert US_INDEX_SYMBOLS["SP500"] == ".INX"
        assert US_INDEX_SYMBOLS["NASDAQ"] == ".IXIC"
        assert US_INDEX_SYMBOLS["DOWJONES"] == ".DJI"
        assert US_INDEX_SYMBOLS["NASDAQ100"] == ".NDX"

    def test_stock_us_init_uppercase(self):
        """美股 Stock 初始化大写化、无 sh/sz 前缀。"""
        from src.data.data_manager import Stock
        s = Stock("aapl", market="us")
        assert s.stock_code == "AAPL"
        assert s.get_code_without_prefix() == "AAPL"
        assert s.stock_data_dir.endswith(os.path.join("stock_data", "us"))

    def test_stock_ashare_unchanged(self):
        """A 股 Stock 初始化行为不变（向后兼容）。"""
        from src.data.data_manager import Stock
        s = Stock("000001")
        assert s.market == "zh_a"
        assert s.stock_code == "sz000001"
        assert s.get_code_without_prefix() == "000001"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
