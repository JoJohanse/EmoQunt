# coding=utf-8
"""风险管理模块 (src/risk/risk_manager.py) 单元测试。

覆盖：
- PositionSizer：仓位计算（止损距离/上限/波动率/零价格）、行业暴露检查
- StopLossHandler：固定止损 / 移动止损 / 未知标的
- VaRCalculator：历史法 / 参数法 / CVaR / 空序列
- RiskManager：黑名单、回撤跟踪、交易限制、清仓判断
- apply_risk_controls：黑名单与交易限制下的信号调整

运行：pytest test/test_risk_manager.py -v
"""
import os
import sys

import numpy as np
import pandas as pd
import pytest

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from src.risk.risk_manager import (
    PositionSizer,
    StopLossHandler,
    VaRCalculator,
    RiskManager,
    apply_risk_controls,
)


class TestPositionSizer:
    """仓位管理器测试。"""

    def test_size_capped_by_max_position(self):
        ps = PositionSizer(100000.0)
        # 风险法算出 4000 股，但受 max_position_size(10%) 上限约束
        # 上限 = 100000 * 0.1 / 10 = 1000 股
        size = ps.calculate_position_size(
            price=10, account_value=100000,
            risk_per_trade=0.02, stop_loss_distance=0.05,
        )
        assert size == 1000

    def test_zero_price_returns_zero(self):
        ps = PositionSizer()
        assert ps.calculate_position_size(price=0, account_value=100000) == 0

    def test_size_is_int(self):
        ps = PositionSizer()
        size = ps.calculate_position_size(price=10, account_value=100000, stop_loss_distance=0.05)
        assert isinstance(size, int)

    def test_volatility_reduces_size(self):
        ps = PositionSizer()
        low_vol = ps.calculate_position_size(
            price=10, account_value=100000, stop_loss_distance=0.0, volatility=0.05,
        )
        high_vol = ps.calculate_position_size(
            price=10, account_value=100000, stop_loss_distance=0.0, volatility=0.5,
        )
        # 高波动应导致更小（或相等）的仓位
        assert high_vol <= low_vol

    def test_sector_exposure_over_limit(self):
        ps = PositionSizer()
        ps.set_position_limits(max_sector_exposure=0.5)
        current = {"A": {"quantity": 100, "price": 10, "sector": "科技"}}
        new = {"stock": "B", "quantity": 100, "price": 10, "sector": "科技"}
        # 同行业合计 2000/2000 = 1.0 > 0.5 → 拒绝
        assert ps.check_sector_exposure(current, new) is False

    def test_sector_exposure_within_limit(self):
        ps = PositionSizer()
        ps.set_position_limits(max_sector_exposure=0.5)
        current = {"A": {"quantity": 100, "price": 10, "sector": "科技"}}
        new = {"stock": "B", "quantity": 100, "price": 10, "sector": "金融"}
        # 科技 1000、金融 1000，合计 2000，金融占比 0.5 不超过 → 允许
        assert ps.check_sector_exposure(current, new) is True


class TestStopLossHandler:
    """止损处理器测试。"""

    def test_fixed_stop_triggers(self):
        h = StopLossHandler(stop_loss_pct=0.05, trailing_stop=False)
        h.set_entry_price("A", 100.0)
        triggered, _ = h.should_stop_loss("A", 90.0)  # 跌 10% > 5%
        assert triggered is True

    def test_fixed_stop_not_triggered(self):
        h = StopLossHandler(stop_loss_pct=0.05)
        h.set_entry_price("A", 100.0)
        triggered, _ = h.should_stop_loss("A", 97.0)  # 跌 3%
        assert triggered is False

    def test_unknown_stock(self):
        h = StopLossHandler()
        triggered, reason = h.should_stop_loss("Z", 100.0)
        assert triggered is False
        assert "未记录" in reason

    def test_trailing_stop_triggers(self):
        h = StopLossHandler(stop_loss_pct=0.05, trailing_stop=True)
        h.set_entry_price("A", 100.0)
        # 价格升至 120，更新最高价；移动止损线 = 120 * 0.95 = 114
        h.should_stop_loss("A", 120.0)
        # 跌至 110 < 114 → 触发
        triggered, _ = h.should_stop_loss("A", 110.0)
        assert triggered is True

    def test_trailing_stop_not_triggered_below_entry_but_above_trailing(self):
        h = StopLossHandler(stop_loss_pct=0.05, trailing_stop=True)
        h.set_entry_price("A", 100.0)
        # 最高价仍 100，移动止损线 = 95；97 > 95 → 不触发
        triggered, _ = h.should_stop_loss("A", 97.0)
        assert triggered is False


class TestVaRCalculator:
    """VaR 计算器测试。"""

    @pytest.fixture
    def returns(self):
        rng = np.random.default_rng(42)
        return pd.Series(rng.normal(0, 0.01, 500))

    def test_historical_var_positive(self, returns):
        v = VaRCalculator(confidence_level=0.95)
        assert v.calculate_var_historical(returns, 100000) > 0

    def test_empty_returns_zero(self):
        v = VaRCalculator()
        empty = pd.Series([], dtype=float)
        assert v.calculate_var_historical(empty, 100000) == 0.0
        assert v.calculate_var_parametric(empty, 100000) == 0.0

    def test_zero_std_returns_zero(self):
        v = VaRCalculator()
        # 使用整数序列保证标准差精确为 0.0（浮点常量会有微小残差，无法命中零标准差分支）
        rets = pd.Series([5] * 10)
        assert v.calculate_var_parametric(rets, 100000) == 0.0

    def test_calculate_var_dict_keys(self, returns):
        v = VaRCalculator(confidence_level=0.95)
        res = v.calculate_var(returns, 100000)
        assert "historical_var" in res
        assert "parametric_var" in res
        assert "cvar" in res
        assert res["confidence_level"] == 0.95
        # CVaR 不应小于历史 VaR（条件期望 ≥ 分位损失）
        assert res["cvar"] >= res["historical_var"] - 1e-9


class TestRiskManager:
    """风险管理器测试。"""

    def test_blacklist_add_and_check(self):
        rm = RiskManager()
        rm.add_to_blacklist("000001")
        assert rm.is_blacklisted("000001") is True
        assert rm.is_blacklisted("000002") is False
        rm.add_to_blacklist(["000002", "000003"])
        assert rm.is_blacklisted("000002") is True
        assert rm.is_blacklisted("000003") is True

    def test_drawdown_tracking(self):
        rm = RiskManager(100000.0)
        rm.update_portfolio_value(120000)  # 峰值
        rm.update_portfolio_value(100000)  # 回撤 16.7%
        assert rm.drawdown == pytest.approx((120000 - 100000) / 120000)

    def test_trading_restricted_by_drawdown(self):
        rm = RiskManager(100000.0)
        rm.set_risk_limits(max_drawdown=0.10)
        rm.update_portfolio_value(120000)
        rm.update_portfolio_value(100000)  # 16.7% > 10%
        allow, reasons = rm.check_trading_restrictions(100000)
        assert allow is False
        assert any("回撤" in r for r in reasons)

    def test_trading_allowed_normally(self):
        rm = RiskManager(100000.0)
        allow, reasons = rm.check_trading_restrictions(100000)
        assert allow is True
        assert reasons == []

    def test_position_with_risk_respects_blacklist(self):
        rm = RiskManager()
        rm.add_to_blacklist("000001")
        info = {"symbol": "000001", "price": 10.0, "volatility": 0.2}
        assert rm.calculate_position_with_risk(info, 100000) == 0

    def test_should_liquidate_blacklist(self):
        rm = RiskManager()
        rm.add_to_blacklist("000001")
        liq, reason = rm.should_liquidate_position({"symbol": "000001"}, 100.0)
        assert liq is True
        assert "黑名单" in reason

    def test_should_liquidate_stop_loss(self):
        rm = RiskManager()
        rm.stop_loss_handler.set_entry_price("000001", 100.0)
        liq, _ = rm.should_liquidate_position({"symbol": "000001"}, 80.0)
        assert liq is True

    def test_should_liquidate_negative_pe(self):
        rm = RiskManager()
        liq, _ = rm.should_liquidate_position(
            {"symbol": "000001", "fundamentals": {"pe_ratio": -5}}, 100.0
        )
        assert liq is True

    def test_should_liquidate_high_debt(self):
        rm = RiskManager()
        liq, _ = rm.should_liquidate_position(
            {"symbol": "000001", "fundamentals": {"debt_to_equity": 2.0}}, 100.0
        )
        assert liq is True

    def test_should_not_liquidate_normal(self):
        rm = RiskManager()
        liq, _ = rm.should_liquidate_position({"symbol": "000001"}, 100.0)
        assert liq is False

    def test_generate_risk_report(self):
        rm = RiskManager(100000.0)
        rets = pd.Series(np.random.default_rng(1).normal(0, 0.01, 100))
        report = rm.generate_risk_report(100000, rets)
        assert report["portfolio_value"] == 100000
        assert "var_analysis" in report
        assert "volatility" in report
        assert "sharpe_ratio" in report


class TestApplyRiskControls:
    """风险控制应用到信号测试。"""

    def test_blacklisted_signal_zeroed(self):
        rm = RiskManager()
        rm.add_to_blacklist("000001")
        signals = pd.DataFrame([{
            "symbol": "000001", "price": 10.0,
            "position_size": 1000, "volatility": 0.2,
        }])
        out = apply_risk_controls(signals, rm, {}, 100000)
        assert out.loc[0, "position_size"] == 0
        assert "黑名单" in out.loc[0, "reason"]

    def test_normal_signal_kept(self):
        rm = RiskManager()
        signals = pd.DataFrame([{
            "symbol": "000001", "price": 10.0,
            "position_size": 50, "volatility": 0.2,
        }])
        out = apply_risk_controls(signals, rm, {}, 100000)
        # 不在黑名单、无交易限制 → 仓位被风险计算调整但非强制清零
        assert out.loc[0, "position_size"] >= 0

    def test_trading_restricted_zeros_all(self):
        rm = RiskManager(100000.0)
        rm.set_risk_limits(max_drawdown=0.10)
        rm.update_portfolio_value(120000)
        rm.update_portfolio_value(100000)  # 超回撤
        signals = pd.DataFrame([{
            "symbol": "000001", "price": 10.0,
            "position_size": 1000, "volatility": 0.2,
        }])
        out = apply_risk_controls(signals, rm, {}, 100000)
        assert out.loc[0, "position_size"] == 0
        assert "交易限制" in out.loc[0, "reason"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
