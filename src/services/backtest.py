"""回测服务层：参数校验 + 市场归一 + 运行委托（深模块）。

统一四个调用方共用的校验链与默认基准映射：
    - web_app.py HTML 路由 POST /run_backtest
    - web_app.py JSON 路由 POST /api/backtest/run
    - web_app.py JSON 路由 POST /api/strategies/compare
    - agent 工具 src/agent/tools.py:run_backtest

路由层只负责 HTTP 解析、错误码映射与响应封装；校验文案、参数默认值与
响应形状与既有行为逐字一致（SPA 的 types.ts 与 localStorage 存档依赖）。
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Tuple

from src.utils.validators import (
    sanitize_string,
    validate_commission_rate,
    validate_date_range,
    validate_initial_capital,
    validate_stock_code,
    validate_strategy_name,
)

logger = logging.getLogger(__name__)


def normalize_market(market: Any) -> str:
    """市场参数归一：仅接受 'zh_a'/'us'，其余一律回落 'zh_a'（与既有行为一致）。"""
    return market if market in ("zh_a", "us") else "zh_a"


def default_benchmark_index(market: str) -> str:
    """默认基准指数映射：美股标普500(SP500)，A股沪深300(000300)。"""
    return "SP500" if market == "us" else "000300"


def validate_backtest_params(payload: Dict) -> Tuple[Optional[Dict], Optional[str]]:
    """校验单次回测参数（纯函数，无 HTTP 依赖）。

    校验链（顺序与既有路由一致）：strategy_name → stock_code → date_range →
    initial_capital → commission_rate，错误文案由 src/utils/validators 生成、
    与既有路由逐字一致。initial_capital/commission_rate 的 float() 转换异常
    按原样向调用方传播（/api/backtest/run 以 400 回显，策略对比路由落入 500，
    与现状一致）。

    :param payload: 请求参数 dict（strategy_name/stock_code/start_date/end_date/
                    initial_capital/commission_rate/market，缺省键走既有默认值）
    :return: (params, error)：通过时返回 (归一后参数 dict, None)；
             失败时返回 (None, 错误文案)
    """
    strategy_name = sanitize_string(str(payload.get("strategy_name", "")), 50)
    stock_code = sanitize_string(str(payload.get("stock_code", "")), 10)
    market = normalize_market(payload.get("market", "zh_a"))
    start_date = str(payload.get("start_date", ""))
    end_date = str(payload.get("end_date", ""))
    initial_capital = float(payload.get("initial_capital", 100000.0))
    commission_rate = float(payload.get("commission_rate", 0.0003))

    valid, error = validate_strategy_name(strategy_name)
    if not valid:
        return None, error
    valid, error = validate_stock_code(stock_code, market=market)
    if not valid:
        return None, error
    valid, error = validate_date_range(start_date, end_date)
    if not valid:
        return None, error
    valid, error = validate_initial_capital(initial_capital)
    if not valid:
        return None, error
    valid, error = validate_commission_rate(commission_rate)
    if not valid:
        return None, error

    return {
        "strategy_name": strategy_name,
        "stock_code": stock_code,
        "start_date": start_date,
        "end_date": end_date,
        "initial_capital": initial_capital,
        "commission_rate": commission_rate,
        "market": market,
    }, None


def validate_compare_params(payload: Dict) -> Tuple[Optional[Dict], Optional[str]]:
    """校验策略对比参数（strategy_names/stock_code/日期区间），纯函数。

    校验链与既有 /api/strategies/compare 路由一致：strategy_names 非空数组 →
    stock_code → date_range，错误文案逐字一致；initial_capital/commission_rate
    的 float() 转换异常按原样传播（路由层落入 500，与现状一致）。

    :return: (params, error)，params 键与 compare_strategies 签名一一对应
    """
    names = payload.get("strategy_names") or []
    if not isinstance(names, list) or not names:
        return None, "strategy_names 必须是非空数组"
    names = [sanitize_string(str(n), 50) for n in names][:5]

    stock_code = sanitize_string(str(payload.get("stock_code", "")), 10)
    market = normalize_market(payload.get("market", "zh_a"))
    start_date = str(payload.get("start_date", ""))
    end_date = str(payload.get("end_date", ""))
    initial_capital = float(payload.get("initial_capital", 100000.0))
    commission_rate = float(payload.get("commission_rate", 0.0003))

    valid, error = validate_stock_code(stock_code, market=market)
    if not valid:
        return None, error
    valid, error = validate_date_range(start_date, end_date)
    if not valid:
        return None, error

    return {
        "strategy_names": names,
        "stock_code": stock_code,
        "start_date": start_date,
        "end_date": end_date,
        "market": market,
        "initial_capital": initial_capital,
        "commission_rate": commission_rate,
    }, None


def run_json(
    strategy_name: str,
    stock_code: str,
    start_date: str,
    end_date: str,
    initial_capital: float = 100000.0,
    commission_rate: float = 0.0003,
    market: str = "zh_a",
    slippage_rate: float = 0.0005,
) -> Dict:
    """运行回测并返回 JSON 时序（委托 backtest_manager.run_backtest_json）。

    默认基准指数按市场映射（美股 SP500 / A股 000300），同步阻塞，调用方
    （路由/工具）需自行放线程池。
    """
    from src.backtest.backtest_manager import run_backtest_json

    return run_backtest_json(
        strategy_name=strategy_name, stock_code=stock_code,
        start_date=start_date, end_date=end_date,
        initial_capital=initial_capital, commission_rate=commission_rate,
        benchmark_index=default_benchmark_index(market), market=market,
        slippage_rate=slippage_rate,
    )


def run_with_charts(
    strategy_name: str,
    stock_code: str,
    start_date: str,
    end_date: str,
    initial_capital: float = 100000.0,
    commission_rate: float = 0.0003,
    output_dir: str = "output",
    market: str = "zh_a",
    slippage_rate: float = 0.0005,
) -> Dict:
    """运行回测并生成 matplotlib PNG 图表（委托 backtest_manager.run_backtest_with_charts）。"""
    from src.backtest.backtest_manager import run_backtest_with_charts

    return run_backtest_with_charts(
        strategy_name=strategy_name, stock_code=stock_code,
        start_date=start_date, end_date=end_date,
        initial_capital=initial_capital, commission_rate=commission_rate,
        output_dir=output_dir, benchmark_index=default_benchmark_index(market),
        slippage_rate=slippage_rate, market=market,
    )
