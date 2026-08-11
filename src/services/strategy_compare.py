"""策略对比服务：在同一标的上运行多个用户策略，返回对齐的净值曲线与指标。

激活休眠的多策略对比能力（替代半成品的 run_multiple_strategies）。
复用已验证的 `_run_backtest_core` 路径（正确佣金/复权/create_user_strategy_class），
而非 run_multiple_strategies（其依赖空的 global_strategy_manager + 默认佣金）。
"""
from __future__ import annotations

import logging
from typing import Dict, List

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# 单次对比的最多策略数（防止过载；每个策略都是一次完整回测）
MAX_STRATEGIES = 5


def _safe_float(v, nd=4) -> float:
    try:
        f = float(v)
        return 0.0 if not np.isfinite(f) else round(f, nd)
    except (TypeError, ValueError):
        return 0.0


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

    if not strategy_names:
        return {"error": "未提供策略列表"}
    if len(strategy_names) > MAX_STRATEGIES:
        return {"error": f"最多同时对比 {MAX_STRATEGIES} 个策略"}

    benchmark_index = "SP500" if market == "us" else "000300"
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
                "equity_curve": [_safe_float(v, 2) for v in equity.tolist()],
                "metrics": {
                    "总收益率": _safe_float(m.get("总收益率", 0), 6),
                    "年化收益率": _safe_float(m.get("年化收益率", 0), 6),
                    "夏普比率": _safe_float(m.get("夏普比率", 0), 4),
                    "最大回撤": _safe_float(m.get("最大回撤", 0), 6),
                    "胜率": _safe_float(m.get("胜率", 0), 6),
                    "盈亏比": _safe_float(m.get("盈亏比", 0), 4),
                    "Alpha": _safe_float(core.get("alpha"), 6) if core.get("alpha") is not None else None,
                    "Beta": _safe_float(core.get("beta"), 4) if core.get("beta") is not None else None,
                },
                "alpha_raw": core.get("alpha"),
                "beta_raw": core.get("beta"),
            })
        except Exception as e:
            logger.warning(f"策略 {name} 回测失败（对比中跳过）: {e}")
            errors.append({"name": name, "error": str(e)})

    if not results:
        return {"error": "所有策略均回测失败", "details": errors}

    # 对齐到公共日期区间（各策略回测区间可能因数据略有差异）
    # 以最长 dates 序列为基准，其它按日期 reindex（ffill 兜底）
    base = max(results, key=lambda r: len(r["dates"]))
    base_dates = base["dates"]
    base_idx = pd.to_datetime(base_dates)

    aligned_series = []
    for r in results:
        eq = pd.Series(r["equity_curve"], index=pd.to_datetime(r["dates"]))
        eq = eq.reindex(base_idx).ffill().bfill()
        # 清理 metrics 里的临时键
        metrics = {k: v for k, v in r["metrics"].items()}
        aligned_series.append({
            "name": r["name"],
            "equity_curve": [_safe_float(v, 2) for v in eq.tolist()],
            "metrics": metrics,
        })

    return {
        "dates": base_dates,
        "common_start": base_dates[0] if base_dates else None,
        "common_end": base_dates[-1] if base_dates else None,
        "series": aligned_series,
        "errors": errors,
        "stock_code": stock_code,
        "market": market,
    }
