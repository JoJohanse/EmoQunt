"""src/Strategy/code_loader.py 代码策略加载器测试。

用合成 OHLCV 数据直接驱动 cerebro，验证：源码物化后可运行、SDK 交易 API
在线程绑定下可用、参数合并（DB 覆盖源码默认）、生命周期外调用被拒、
危险源码在构建时被拦截。不触网。
"""
import os
import sys

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import backtrader as bt  # noqa: E402
from emoquant._runtime import get_host, unbind_host  # noqa: E402
from src.Strategy.code_loader import build_backtrader_strategy  # noqa: E402

SOURCE_BUY = '''
STRATEGY_PARAMS = {
    "trade_percent": 0.5,
}


def initialize(context):
    context.bought = False


def handle_data(context, data):
    if not context.bought and data.close > 0:
        buy(percent=context.params["trade_percent"])
        context.bought = True
'''


def _synthetic_feed(days: int = 60) -> bt.feeds.PandasData:
    dates = pd.date_range("2024-01-01", periods=days, freq="B")
    close = np.linspace(10.0, 12.0, days)
    df = pd.DataFrame({
        "open": close, "high": close * 1.01, "low": close * 0.99,
        "close": close, "volume": np.full(days, 1_000_000.0),
    }, index=dates)
    return bt.feeds.PandasData(dataname=df)


RUN_INFO = {"start_date": "2024-01-01", "end_date": "2024-03-29",
            "stock_code": "600000", "market": "zh_a"}


def _run_strategy(source, params=None):
    cerebro = bt.Cerebro()
    cerebro.broker.setcash(100000.0)
    cerebro.adddata(_synthetic_feed())
    cerebro.addstrategy(build_backtrader_strategy(source, params, run_info=dict(RUN_INFO)))
    return cerebro.run()[0]


def test_strategy_runs_and_buys_via_sdk():
    strat = _run_strategy(SOURCE_BUY)
    assert strat.ctx.bought is True
    assert strat.ctx.get_position() == 5000  # 100000*0.5/10=5000 股（整手）
    assert strat.ctx.run_info.stock_code == "600000"
    assert strat.ctx.trade_date is not None


def test_params_override_source_defaults():
    strat = _run_strategy(SOURCE_BUY, params={"trade_percent": 0.2})
    assert strat.ctx.params["trade_percent"] == 0.2
    assert strat.ctx.get_position() == 2000  # 100000*0.2/10=2000 股


def test_sdk_call_outside_lifecycle_rejected():
    unbind_host()
    with pytest.raises(RuntimeError):
        get_host()
    with pytest.raises(RuntimeError):
        from emoquant.api import buy

        buy(percent=0.5)


def test_dangerous_source_rejected_at_build():
    with pytest.raises(ValueError):
        build_backtrader_strategy("import os\n" + SOURCE_BUY)
    with pytest.raises(ValueError):
        build_backtrader_strategy("def handle_data(context, data):\n    pass\n")


def test_target_percent_adjusts_position():
    source = SOURCE_BUY.replace(
        'buy(percent=context.params["trade_percent"])',
        'order_target_percent(context.params["trade_percent"])',
    )
    strat = _run_strategy(source)
    assert strat.ctx.get_position() == 5000
