"""策略对比服务：在同一标的上运行多个用户策略，返回对齐的净值曲线与指标。

复用已验证的 `_run_backtest_core` 路径（正确佣金/复权/create_user_strategy_class）。
"""
from __future__ import annotations

import logging
from typing import Dict, List

import pandas as pd

from src.utils.serialize import safe_float

logger = logging.getLogger(__name__)

# 单次对比的最多策略数（防止过载；每个策略都是一次完整回测）
MAX_STRATEGIES = 5


def compare_strategies(
    strategy_names: List[str],
    stock_code: str,
    start_date: str,
    end_date: str,
    market: str = "zh_a",
    initial_capital: float = 100000.0,
    commission_rate: float = 0.0003,
) -> Dict:
    """在同一标的上对比多个策略。

    :param strategy_names: 用户策略名列表（≤5）
    :param stock_code: 标的代码
    :param start_date/end_date: 'YYYY-MM-DD'
    :param market: 'zh_a' / 'us'
    :return: {
        "dates": [...],
        "series": [{"name": strategy, "equity_curve": [...], "metrics": {...}}, ...],
        "common_start": ..., "common_end": ...,
    } 或 {"error": "..."}
    """
    from src.backtest.backtest_manager import _run_backtest_core

    from src.services.backtest import default_benchmark_index

    if not strategy_names:
        return {"error": "未提供策略列表"}
    if len(strategy_names) > MAX_STRATEGIES:
        return {"error": f"最多同时对比 {MAX_STRATEGIES} 个策略"}

    benchmark_index = default_benchmark_index(market)
    sd = start_date.replace("-", "")
    ed = end_date.replace("-", "")

    results = []  # [(name, dates, equity, metrics_dict)]
    errors = []
    for name in strategy_names:
        try:
            core = _run_backtest_core(
                strategy_name=name, stock_code=stock_code,
                start_date=sd, end_date=ed,
                initial_capital=initial_capital, commission_rate=commission_rate,
                benchmark_index=benchmark_index, market=market,
                apply_sentiment_filter=False,
            )
            equity = core["equity"]  # pd.Series indexed by date
            dates = [d.strftime("%Y-%m-%d") for d in equity.index]
            m = core["metrics_raw"]
            results.append({
                "name": name,
                "dates": dates,
                "equity_curve": [safe_float(v, 2) for v in equity.tolist()],
                "metrics": {
                    "总收益率": safe_float(m.get("总收益率", 0), 6),
                    "年化收益率": safe_float(m.get("年化收益率", 0), 6),
                    "夏普比率": safe_float(m.get("夏普比率", 0), 4),
                    "最大回撤": safe_float(m.get("最大回撤", 0), 6),
                    "胜率": safe_float(m.get("胜率", 0), 6),
                    "盈亏比": safe_float(m.get("盈亏比", 0), 4),
                    "Alpha": safe_float(core.get("alpha"), 6) if core.get("alpha") is not None else None,
                    "Beta": safe_float(core.get("beta"), 4) if core.get("beta") is not None else None,
                },
            })
        except Exception as e:
            logger.warning(f"策略 {name} 回测失败（对比中跳过）: {e}")
            errors.append({"name": name, "error": str(e)})

    if not results:
        return {"error": "所有策略均回测失败", "details": errors}

    # 对齐到【公共日期交集】——只保留所有策略都有真实净值的交易日，
    # 不用并集+ffill/bfill（那会凭空捏造某策略未交易的日期的净值）。
    common_idx = pd.to_datetime(results[0]["dates"])
    for r in results[1:]:
        common_idx = common_idx.intersection(pd.to_datetime(r["dates"]))
    common_idx = common_idx.sort_values()
    common_dates = [d.strftime("%Y-%m-%d") for d in common_idx]

    if not common_dates:
        return {"error": "各策略无公共交易日，无法对齐", "details": errors}

    aligned_series = []
    for r in results:
        eq = pd.Series(r["equity_curve"], index=pd.to_datetime(r["dates"]))
        # common_idx ⊆ 该策略的日期，reindex 后无 NaN（均为真实净值）
        eq = eq.reindex(common_idx)
        aligned_series.append({
            "name": r["name"],
            "equity_curve": [safe_float(v, 2) for v in eq.tolist()],
            "metrics": r["metrics"],
        })

    return {
        "dates": common_dates,
        "common_start": common_dates[0],
        "common_end": common_dates[-1],
        "series": aligned_series,
        "errors": errors,
        "stock_code": stock_code,
        "market": market,
    }
