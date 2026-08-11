# coding=utf-8
"""回测报告增强测试：PerformanceAnalyzer 完整报告 + RiskManager 事后风险报告。

验证 _run_backtest_core 输出含 performance_report / risk_report 键，
run_backtest_json 把新指标安全序列化（datetime→str、inf→0、嵌套 dict 可 JSON 化）。

不跑真实回测：用合成 daily_returns 构造 PerformanceAnalyzer / RiskManager 路径，
或 mock _run_backtest_core 验证 run_backtest_json 的序列化适配器。

运行：pytest test/test_backtest_enriched_metrics.py -v
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


def _synth_equity(n=60):
    """合成净值 + 日收益序列（回测核心产物的替身）。"""
    dates = pd.date_range("2024-01-02", periods=n, freq="B")
    rng = np.random.default_rng(42)
    daily_ret = pd.Series(rng.normal(0.0005, 0.012, n), index=dates)
    equity = (1 + daily_ret).cumprod() * 100000
    return daily_ret, equity


class TestPerformanceReport:
    """PerformanceAnalyzer.generate_report 激活后产出完整指标。"""

    def test_generate_report_has_full_keys(self):
        from src.backtest.backtest_manager import PerformanceAnalyzer
        daily_ret, _ = _synth_equity()
        pa = PerformanceAnalyzer(daily_ret)
        report = pa.generate_report()
        for k in ("总收益率", "年化收益率", "年化波动率", "夏普比率", "最大回撤",
                  "卡玛比率", "下行标准差", "VaR (95%)", "CVaR (95%)",
                  "Alpha", "Beta", "信息比率"):
            assert k in report, f"完整报告缺键: {k}"

    def test_win_rate_with_real_trades(self):
        from src.backtest.backtest_manager import PerformanceAnalyzer
        daily_ret, _ = _synth_equity()
        pa = PerformanceAnalyzer(daily_ret)
        # 真实交易级胜负：6 盈 4 亏 → 0.6
        wr = pa.calculate_win_rate(6, 4)
        assert wr == pytest.approx(0.6, rel=1e-6)


class TestRunBacktestJsonSerialization:
    """run_backtest_json 的序列化适配器把 performance/risk 报告安全转为 JSON。"""

    def test_metrics_include_enriched_keys(self):
        """mock _run_backtest_core 返回含 performance_report/risk_report 的 core，
        验证 run_backtest_json 产出含新键且整体可 JSON 序列化。"""
        from src.backtest.backtest_manager import run_backtest_json
        from datetime import datetime

        daily_ret, equity = _synth_equity()
        # 构造含 datetime（最大回撤起止）+ inf 的 performance_report，验证序列化
        fake_core = {
            "metrics_raw": {"总收益率": 0.12, "年化收益率": 0.12, "夏普比率": 1.5,
                            "最大回撤": -0.08, "胜率": 0.55, "盈亏比": 1.8},
            "alpha": 0.03, "beta": 0.9, "info_ratio": 0.4,
            "performance_report": {
                "年化波动率": 0.18, "卡玛比率": 1.5, "下行标准差": 0.14,
                "VaR (95%)": -2500.0, "CVaR (95%)": -3100.0,
                "交易次数": 10, "盈利交易数": 6, "亏损交易数": 4,
                "平均盈利": 500.0, "平均亏损": -300.0,
                "最大回撤开始时间": datetime(2024, 3, 15),
                "最大回撤结束时间": datetime(2024, 4, 10),
            },
            "risk_report": {
                "portfolio_value": 112000.0, "current_drawdown": 0.05,
                "max_drawdown_limit": 0.15, "volatility": 0.18, "sharpe_ratio": 1.5,
                "blacklist_count": 0,
                "var_analysis": {"historical_var": -2500.0, "parametric_var": -2400.0,
                                 "cvar": -3100.0, "confidence_level": 0.95},
                "stress_test": {"baseline_var": -2500.0, "市场冲击_var": -4200.0,
                                "市场冲击_change": 0.68},
                "risk_limits": {"max_daily_loss": 0.05, "max_leverage": 1.0},
            },
            "daily_returns": daily_ret, "equity": equity,
            "drawdown": pd.Series(-0.01 * np.arange(len(daily_ret)), index=daily_ret.index),
            "benchmark_curve": None,
        }
        with patch("src.backtest.backtest_manager._run_backtest_core", return_value=fake_core):
            out = run_backtest_json(
                strategy_name="test", stock_code="000001",
                start_date="2024-01-01", end_date="2024-03-31",
            )

        # 新指标键存在
        for k in ("年化波动率", "卡玛比率", "下行标准差", "VaR (95%)", "CVaR (95%)",
                  "交易次数", "盈利交易数", "亏损交易数",
                  "最大回撤开始时间", "最大回撤结束时间"):
            assert k in out["metrics"], f"metrics 缺新键: {k}"
        # datetime 已转 str
        assert out["metrics"]["最大回撤开始时间"] == "2024-03-15"
        assert isinstance(out["metrics"]["最大回撤开始时间"], str)
        # risk_report 顶层字段
        assert out["risk_report"] is not None
        assert "var_analysis" in out["risk_report"]
        assert "stress_test" in out["risk_report"]
        # 整体可 JSON 序列化（datetime/np 类型都已清理）
        json.dumps(out)  # 不抛即通过

    def test_no_perf_report_does_not_crash(self):
        """performance_report/risk_report 为 None 时不应崩。"""
        from src.backtest.backtest_manager import run_backtest_json
        daily_ret, equity = _synth_equity()
        fake_core = {
            "metrics_raw": {"总收益率": 0.1, "年化收益率": 0.1, "夏普比率": 1.0,
                            "最大回撤": -0.05, "胜率": 0.5, "盈亏比": 1.0},
            "alpha": None, "beta": None, "info_ratio": None,
            "performance_report": None, "risk_report": None,
            "daily_returns": daily_ret, "equity": equity,
            "drawdown": pd.Series(np.zeros(len(daily_ret)), index=daily_ret.index),
            "benchmark_curve": None,
        }
        with patch("src.backtest.backtest_manager._run_backtest_core", return_value=fake_core):
            out = run_backtest_json(
                strategy_name="t", stock_code="000001",
                start_date="2024-01-01", end_date="2024-02-01",
            )
        assert out["risk_report"] is None
        assert "总收益率" in out["metrics"]
        json.dumps(out)


class TestRiskReportComputes:
    """RiskManager.generate_risk_report + stress_test 真能算出风险指标。"""

    def test_risk_report_values(self):
        from src.risk import RiskManager
        daily_ret, equity = _synth_equity()
        rm = RiskManager(initial_capital=100000.0)
        rm.update_portfolio_value(float(equity.iloc[-1]))
        rr = rm.generate_risk_report(float(equity.iloc[-1]), daily_ret)
        assert "var_analysis" in rr
        # VaRCalculator 返回损失绝对额（正数），不是负数
        assert rr["var_analysis"]["historical_var"] > 0
        assert rr["var_analysis"]["cvar"] > 0
        assert rr["volatility"] > 0
        stress = rm.stress_test(daily_ret, stress_scenarios=[
            {"name": "市场冲击", "shock": -0.20},
            {"name": "波动放大", "vol_multiplier": 1.5},
        ])
        assert "市场冲击_var" in stress
        # 冲击下 VaR 应更糟（损失额更大）
        assert stress["市场冲击_var"] >= stress["baseline_var"]


class TestEnrichmentWiring:
    """_build_enrichment_reports（_run_backtest_core 抽出的 enrichment wiring）端到端测试。

    不跑完整 cerebro 回测，直接喂合成 daily_returns/equity/strat，验证：
    - PerformanceAnalyzer.generate_report 被调用并产出完整键
    - RiskManager.generate_risk_report + stress_test 被调用
    - 真实交易级胜负注入（strat.analyzers.tradeanalyzer）覆盖默认胜率
    - strat=None 时降级正常
    """

    def _fake_strat(self, won_total=6, lost_total=4):
        """构造带 tradeanalyzer 的假 strat（用 MagicMock）。"""
        from unittest.mock import MagicMock
        ta = MagicMock()
        ta.get_analysis.return_value = {
            'won': {'total': won_total, 'pnl': {'total': 6000.0}},
            'lost': {'total': lost_total, 'pnl': {'total': -3000.0}},
        }
        strat = MagicMock()
        strat.analyzers.getbyname.return_value = ta
        return strat

    def test_wiring_produces_both_reports(self):
        from src.backtest.backtest_manager import _build_enrichment_reports
        daily_ret, equity = _synth_equity()
        pr, rr = _build_enrichment_reports(
            daily_ret, equity, self._fake_strat(), 100000.0,
        )
        # 完整绩效报告
        assert pr is not None
        for k in ("年化波动率", "卡玛比率", "下行标准差", "VaR (95%)", "CVaR (95%)",
                  "交易次数", "胜率"):
            assert k in pr, f"performance_report 缺键: {k}"
        # 真实交易级胜率注入（6/(6+4)=0.6，非日线正收益启发式）
        assert pr["胜率"] == pytest.approx(0.6, rel=1e-6)
        # 风险报告 + 3 压力场景
        assert rr is not None
        assert "var_analysis" in rr and "stress_test" in rr
        assert "市场冲击_var" in rr["stress_test"]
        assert "波动放大_var" in rr["stress_test"]
        assert "流动性枯竭_var" in rr["stress_test"]

    def test_wiring_strat_none_degrades_gracefully(self):
        """strat=None（无 tradeanalyzer）时应降级到默认胜率，不崩。"""
        from src.backtest.backtest_manager import _build_enrichment_reports
        daily_ret, equity = _synth_equity()
        pr, rr = _build_enrichment_reports(daily_ret, equity, None, 100000.0)
        assert pr is not None
        assert "年化波动率" in pr
        assert rr is not None

    def test_wiring_reuses_perf_analyzer(self):
        """传入已构造的 perf_analyzer 应被复用（不再新建无基准实例）。"""
        from src.backtest.backtest_manager import _build_enrichment_reports, PerformanceAnalyzer
        daily_ret, equity = _synth_equity()
        pa = PerformanceAnalyzer(daily_ret.dropna())
        # spy generate_report 调用
        import unittest.mock as mock
        with mock.patch.object(pa, 'generate_report', wraps=pa.generate_report) as spy:
            _build_enrichment_reports(daily_ret, equity, None, 100000.0, perf_analyzer=pa)
            assert spy.called, "应复用传入的 perf_analyzer"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
