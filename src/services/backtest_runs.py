"""回测运行历史服务：异步提交 → 执行器执行 → 结果落库 → 查询。

旧同步接口（services/backtest.run_json / run_with_charts）行为不变；
本模块是运行历史的唯一写入口（对比接口不落 runs，保持无状态）。

流程：submit_run 校验（复用 validate_backtest_params 同一链）→ 建行
（queued）→ task_runner 提交工作函数 → 工作线程置 running → 阶段化跑
_run_backtest_core → finish/fail（条件更新）。超时由 task_runner 看门狗
负责（"放弃等待"语义，见其模块 docstring）。
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

from src.utils.env import get_env_int
from src.utils.i18n import vmsg

logger = logging.getLogger(__name__)


def _timeout_seconds() -> float:
    return float(max(30, get_env_int("QDT_BACKTEST_TIMEOUT", 300)))


def _resolve_strategy(payload: Dict[str, Any]) -> tuple[str, Optional[int]]:
    """解析策略种类与 id。template 沿用旧按名解析；code 需存在策略库行。

    :return: (strategy_kind, strategy_id)
    :raises ValueError: 策略不存在/种类非法（文案已本地化）
    """
    kind = payload.get("strategy_kind") or "template"
    if kind not in ("template", "code"):
        raise ValueError(vmsg("library.badStrategyKind", "strategy_kind 仅支持 template 或 code"))
    if kind == "template":
        return "template", None
    from src.services.strategy_library import get_code_strategy

    strategy_id = payload.get("strategy_id")
    row = get_code_strategy(strategy_id, payload.get("strategy_name"))
    if row is None:
        raise ValueError(vmsg("library.codeStrategyNotFound", "代码策略不存在（需提供有效的 strategy_id）"))
    return "code", int(row["id"])


def submit_run(payload: Dict[str, Any]) -> Dict[str, Any]:
    """校验 + 登记 + 提交异步回测，立即返回 run 摘要。

    :param payload: 回测参数（同 /api/backtest/run 契约 + strategy_kind/strategy_id）
    :return: {"id": run_id, "status": "queued"}
    :raises ValueError: 参数/策略校验失败（文案已本地化）
    """
    from src.services.backtest import validate_backtest_params
    from src.store import db as store
    from src.services.task_runner import submit_task

    params, error = validate_backtest_params(payload)
    if error:
        raise ValueError(error)
    kind, strategy_id = _resolve_strategy(payload)

    run_id = store.create_run(params, strategy_kind=kind, strategy_id=strategy_id)

    def _work() -> None:
        _execute_run(run_id, params, kind, strategy_id)

    submit_task(run_id, _work, _timeout_seconds())
    logger.info("回测运行已提交: run=%s kind=%s strategy=%s stock=%s",
                run_id, kind, params["strategy_name"], params["stock_code"])
    return {"id": run_id, "status": "queued"}


def _execute_run(run_id: int, params: Dict[str, Any], kind: str, strategy_id: Optional[int]) -> None:
    """工作函数（执行器线程内跑）：running → 回测 → 落库终态。"""
    from src.backtest.backtest_manager import _run_backtest_core, _format_metrics_json
    from src.store import db as store

    store.set_run_running(run_id)
    start = time.perf_counter()
    try:
        core = _run_backtest_core(
            strategy_name=params["strategy_name"], stock_code=params["stock_code"],
            start_date=params["start_date"], end_date=params["end_date"],
            initial_capital=params["initial_capital"], commission_rate=params["commission_rate"],
            benchmark_index="SP500" if params["market"] == "us" else "000300",
            slippage_rate=0.0005, market=params["market"],
            strategy_kind=kind, strategy_id=strategy_id,
            progress_cb=lambda stage: logger.debug("run=%s stage=%s", run_id, stage),
        )
        metrics, _risk = _format_metrics_json(
            core["metrics_raw"], core.get("performance_report"), core.get("risk_report"),
            alpha=core["alpha"], beta=core["beta"], info_ratio=core["info_ratio"],
        )
        dates = [d.strftime("%Y-%m-%d") for d in core["daily_returns"].index]
        equity = [float(v) for v in core["equity"].tolist()]
        trades = core.get("trades", []) or []
        duration_ms = int((time.perf_counter() - start) * 1000)
        store.finish_run_if_active(
            run_id, metrics, dates, equity, trades,
            core.get("stages", []), duration_ms,
        )
        logger.info("回测运行完成: run=%s 用时=%dms", run_id, duration_ms)
    except Exception as e:
        logger.exception("回测运行失败: run=%s", run_id)
        store.fail_run_if_active(run_id, str(e))


def get_run_detail(run_id: int) -> Optional[Dict[str, Any]]:
    """运行详情（含时序/成交全量）。不存在返回 None。"""
    from src.store import db as store

    row = store.get_run_row(run_id)
    if row is None:
        return None
    return store.row_to_run_dict(row, unpack_series=True)


def list_runs(strategy_kind: Optional[str] = None, strategy_id: Optional[int] = None,
              market: Optional[str] = None, status: Optional[str] = None,
              limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
    """运行记录摘要列表（不含时序大字段）。"""
    from src.store import db as store

    rows = store.list_run_rows(
        strategy_kind=strategy_kind, strategy_id=strategy_id,
        market=market, status=status, limit=max(1, min(int(limit), 200)), offset=max(0, int(offset)),
    )
    return [store.row_to_run_dict(r) for r in rows]
