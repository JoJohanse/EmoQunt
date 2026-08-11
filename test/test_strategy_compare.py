# coding=utf-8
"""策略对比服务测试。

验证 compare_strategies：
- 调用 _run_backtest_core 跑多个策略
- equity 曲线对齐到公共日期
- 返回每策略 metrics 摘要 + errors（个别失败隔离）
- 上限校验（>5 报错）

mock _run_backtest_core 返回合成 core，不跑真实回测。

运行：pytest test/test_strategy_compare.py -v
"""
import os
import sys
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)


def _fake_core(name: str, n=40):
    """构造 _run_backtest_core 的合成返回值。不同 name 用不同收益种子。"""
    dates = pd.date_range("2024-01-02", periods=n, freq="B")
    rng = np.random.default_rng(hash(name) % (2**32))
    daily_ret = pd.Series(rng.normal(0.0008, 0.011, n), index=dates)
    equity = (1 + daily_ret).cumprod() * 100000
    return {
        "equity": equity,
        "metrics_raw": {"总收益率": float(equity.iloc[-1] / 100000 - 1),
                        "年化收益率": 0.1, "夏普比率": 1.2, "最大回撤": -0.06,
                        "胜率": 0.55, "盈亏比": 1.5},
        "alpha": 0.02, "beta": 0.95, "info_ratio": 0.3,
        # 其它键对比服务不直接用，省略
    }


class TestCompareStrategies:
    def test_multiple_strategies_aligned(self):
        from src.services.strategy_compare import compare_strategies
        names = ["alpha_strategy", "beta_strategy", "gamma_strategy"]
        # _run_backtest_core 在 compare_strategies 内部 from...import，
        # patch 必须指向定义模块 src.backtest.backtest_manager
        with patch("src.backtest.backtest_manager._run_backtest_core",
                   side_effect=lambda **kw: _fake_core(kw["strategy_name"])):
            out = compare_strategies(
                strategy_names=names, stock_code="000001",
                start_date="2024-01-01", end_date="2024-03-01",
                market="zh_a",
            )
        assert "error" not in out
        assert len(out["series"]) == 3
        # 所有 series 的 equity_curve 长度对齐到公共 dates
        common_len = len(out["dates"])
        for s in out["series"]:
            assert len(s["equity_curve"]) == common_len
            assert set(s["metrics"].keys()) >= {"总收益率", "夏普比率", "最大回撤", "胜率"}
        # 顺序与输入一致
        assert [s["name"] for s in out["series"]] == names

    def test_reindex_uses_date_intersection_not_union(self):
        """各策略日期不一致时应取【交集】而非最长并集+ffill（修复凭空捏造净值）。

        long 策略覆盖 40 天 [01-02, 02-26)，short 策略只覆盖 20 天且日期不同
        （从 02-01 起）。交集应 < 任一单策略长度，且 > 0。
        """
        from src.services.strategy_compare import compare_strategies

        def _offset_core(**kw):
            name = kw["strategy_name"]
            if name == "long":
                return _fake_core(name, n=40)  # 从 2024-01-02 起
            # short: 从 2024-02-01 起，20 天（与 long 前段不重叠）
            dates = pd.date_range("2024-02-01", periods=20, freq="B")
            rng = np.random.default_rng(7)
            daily_ret = pd.Series(rng.normal(0.0008, 0.01, 20), index=dates)
            equity = (1 + daily_ret).cumprod() * 100000
            return {
                "equity": equity,
                "metrics_raw": {"总收益率": 0.05, "年化收益率": 0.1, "夏普比率": 1.0,
                                "最大回撤": -0.04, "胜率": 0.5, "盈亏比": 1.2},
                "alpha": None, "beta": None,
            }

        with patch("src.backtest.backtest_manager._run_backtest_core", side_effect=_offset_core):
            out = compare_strategies(
                strategy_names=["long", "short"], stock_code="000001",
                start_date="2024-01-01", end_date="2024-03-01", market="zh_a",
            )
        # 交集应 < long 的 40 天（不是并集 60 天，也不是 long 的全长）
        assert 0 < len(out["dates"]) < 40

    def test_one_failure_isolated(self):
        """一个策略抛异常应被隔离到 errors，其余正常返回。"""
        from src.services.strategy_compare import compare_strategies

        def _flaky(**kw):
            if kw["strategy_name"] == "bad":
                raise RuntimeError("策略不存在")
            return _fake_core(kw["strategy_name"])

        with patch("src.backtest.backtest_manager._run_backtest_core", side_effect=_flaky):
            out = compare_strategies(
                strategy_names=["good_a", "bad", "good_b"], stock_code="000001",
                start_date="2024-01-01", end_date="2024-03-01", market="zh_a",
            )
        assert len(out["series"]) == 2  # bad 被隔离
        assert len(out["errors"]) == 1
        assert out["errors"][0]["name"] == "bad"

    def test_max_limit(self):
        from src.services.strategy_compare import compare_strategies
        out = compare_strategies(
            strategy_names=["a", "b", "c", "d", "e", "f"], stock_code="000001",
            start_date="2024-01-01", end_date="2024-03-01",
        )
        assert "error" in out
        assert "5" in out["error"]

    def test_all_fail_returns_error(self):
        from src.services.strategy_compare import compare_strategies
        with patch("src.backtest.backtest_manager._run_backtest_core",
                   side_effect=RuntimeError("boom")):
            out = compare_strategies(
                strategy_names=["a", "b"], stock_code="000001",
                start_date="2024-01-01", end_date="2024-03-01",
            )
        assert "error" in out
        assert len(out["details"]) == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
