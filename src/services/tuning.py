"""参数调优服务：网格生成 → 执行器并发回测 → 组合落库 → 应用参数。

对齐 docs/plans/pandaai-style-platform-plan.md D4：
- 网格 = ``{参数名: [取值...]}`` 的笛卡尔积，候选上限 63 组，加基准共 ≤64；
  组合 0 恒为基准（策略当前生效参数），is_baseline=1；
- 参数覆盖经 _run_backtest_core 的 ``strategy_params`` seam 逐组生效，
  **绝不回写策略存储**——只有显式 apply 才写：code 策略 UPDATE DB 参数列
  （经 update_code_strategy，自动快照版本），template 策略走既有
  update_strategy 写 strategies.json；
- 执行 = 单个 task_runner 作业内嵌 ``ThreadPoolExecutor(workers)`` 并发跑
  组合；组合结果只落 tuning_runs（指标 + ≤240 点降采样净值），不进
  backtest_runs（运行历史页保持用户手动发起的记录，不被 64 行刷屏）；
- 超时看门狗 = "放弃等待 + 任务标 failed + 活跃组合标 failed"（迟到的
  组合结果经条件更新不会覆盖）。
"""
from __future__ import annotations

import itertools
import json
import logging
import math
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional, Tuple

from src.utils.env import get_env_int
from src.utils.i18n import vmsg

logger = logging.getLogger(__name__)

# 候选组合上限（不含基准）；PandaAI 口径：63 候选 + 1 基准 = 64
MAX_GRID_COMBOS = 63
MAX_VALUES_PER_PARAM = 10
# 每组净值降采样点数（归一化对比图用）
EQUITY_POINTS = 240

# 目标指标 → 是否越大越好（API 指标中文键契约）
TARGET_METRICS: Dict[str, bool] = {
    "总收益率": True,
    "夏普比率": True,
    "最大回撤": False,
}


def _per_combo_timeout() -> float:
    return float(max(30, get_env_int("QDT_BACKTEST_TIMEOUT", 300)))


# ---------------------------------------------------------------------------
# 创建：校验 + 建行 + 提交
# ---------------------------------------------------------------------------
def _resolve_baseline(payload: Dict[str, Any]) -> Tuple[str, Optional[int], str, Dict[str, Any]]:
    """解析策略与其基准参数（当前生效参数）。

    :return: (strategy_kind, strategy_id, strategy_name, baseline_params)
    :raises ValueError: 策略不存在/种类非法（文案已本地化）
    """
    kind = payload.get("strategy_kind") or "code"
    if kind not in ("template", "code"):
        raise ValueError(vmsg("tuning.badStrategyKind", "strategy_kind 仅支持 template 或 code"))
    if kind == "code":
        from src.services.strategy_library import get_code_strategy

        row = get_code_strategy(payload.get("strategy_id"), payload.get("strategy_name"))
        if row is None:
            raise ValueError(vmsg("tuning.codeStrategyNotFound",
                                  "代码策略不存在（需提供有效的 strategy_id）"))
        return "code", int(row["id"]), row["name"], dict(row["params"] or {})
    from src.Strategy.strategy_manager import get_user_strategy
    from src.Strategy.Strategy import build_param_dict

    name = str(payload.get("strategy_name") or "")
    config = get_user_strategy(name)
    if not config:
        raise ValueError(vmsg("tuning.templateStrategyNotFound", "模板策略不存在: {name}", name=name))
    return "template", None, name, build_param_dict(config)


def _validate_grid(param_grid: Any, baseline_params: Dict[str, Any]) -> Dict[str, List[Any]]:
    """校验参数网格：键必须是策略已有参数，值为 1..10 个数字/布尔列表。

    :return: 规范化后的网格
    :raises ValueError: 校验失败（文案已本地化）
    """
    if not isinstance(param_grid, dict) or not param_grid:
        raise ValueError(vmsg("tuning.badParamGrid", "参数网格必须是非空对象（{参数名: [取值...]}）"))
    grid: Dict[str, List[Any]] = {}
    total = 1
    for name, values in param_grid.items():
        name = str(name)
        if name not in baseline_params:
            raise ValueError(vmsg("tuning.gridParamUnknown",
                                  "参数 {name} 不在该策略的参数中", name=name))
        if not isinstance(values, list) or not values:
            raise ValueError(vmsg("tuning.gridValuesEmpty",
                                  "参数 {name} 的取值列表为空", name=name))
        if len(values) > MAX_VALUES_PER_PARAM:
            raise ValueError(vmsg("tuning.gridValuesTooMany",
                                  "参数 {name} 的取值最多 {max} 个", name=name, max=MAX_VALUES_PER_PARAM))
        cleaned: List[Any] = []
        for v in values:
            if isinstance(v, bool) or isinstance(v, (int, float)):
                cleaned.append(v)
            else:
                raise ValueError(vmsg("tuning.gridValuesType",
                                      "参数 {name} 的取值必须是数字或布尔值", name=name))
        grid[name] = cleaned
        total *= len(cleaned)
    if total > MAX_GRID_COMBOS:
        raise ValueError(vmsg(
            "tuning.gridTooLarge",
            "参数组合数 {count} 超过上限 {max}（加基准共 {total} 组）",
            count=total, max=MAX_GRID_COMBOS, total=total + 1,
        ))
    return grid


def create_tuning_task(payload: Dict[str, Any]) -> Dict[str, Any]:
    """校验并创建调优任务，立即返回任务摘要（组合在后台并发执行）。

    :param payload: {strategy_kind, strategy_id|strategy_name, stock_code,
                     start_date, end_date, initial_capital?, commission_rate?,
                     param_grid: {参数名: [取值...]}, target_metric?}
    :return: {"id", "status": "queued", "total_combos"}
    :raises ValueError: 校验失败（文案已本地化）
    """
    from src.services.backtest import validate_backtest_params
    from src.services.task_runner import submit_task
    from src.store import db as store

    kind, strategy_id, strategy_name, baseline = _resolve_baseline(payload)

    grid = _validate_grid(payload.get("param_grid"), baseline)

    target_metric = payload.get("target_metric") or "总收益率"
    if target_metric not in TARGET_METRICS:
        raise ValueError(vmsg("tuning.badTargetMetric", "目标指标仅支持: {names}",
                              names="、".join(TARGET_METRICS)))

    # 回测参数走与运行历史同一条校验链（股票代码/日期/资金）
    bt_payload = {**payload, "strategy_name": strategy_name}
    params, error = validate_backtest_params(bt_payload)
    if error:
        raise ValueError(error)

    # 组合 0 = 基准（当前生效参数），其后为网格笛卡尔积（完整参数 = 基底 + 覆盖）
    combos: List[Dict[str, Any]] = [
        {"combo_index": 0, "is_baseline": 1, "params": dict(baseline)}
    ]
    keys = list(grid.keys())
    for i, values in enumerate(itertools.product(*(grid[k] for k in keys)), start=1):
        override = dict(zip(keys, values))
        combos.append({"combo_index": i, "is_baseline": 0, "params": {**baseline, **override}})

    task_id = store.create_tuning_task(
        {
            "strategy_kind": kind,
            "strategy_id": strategy_id,
            "strategy_name": strategy_name,
            "market": params["market"],
            "stock_code": params["stock_code"],
            "start_date": params["start_date"],
            "end_date": params["end_date"],
            "initial_capital": params["initial_capital"],
            "commission_rate": params["commission_rate"],
            "param_grid_json": json.dumps({k: list(v) for k, v in grid.items()}, ensure_ascii=False),
            "grid_keys_json": json.dumps(keys, ensure_ascii=False),
            "target_metric": target_metric,
            "target_metric_desc": 1 if TARGET_METRICS[target_metric] else 0,
        },
        combos,
    )

    # 看门狗上限按组合数/并发数放宽（"放弃等待"语义，见模块 docstring）
    workers = max(1, get_env_int("QDT_TASK_WORKERS", 2))
    leash = 30 + math.ceil(len(combos) * _per_combo_timeout() / workers)
    submit_task(task_id, lambda: _execute_tuning(task_id), leash, on_abandon=_abandon_tuning)
    logger.info("调优任务已提交: task=%s strategy=%s 组合数=%s", task_id, strategy_name, len(combos))
    return {"id": task_id, "status": "queued", "total_combos": len(combos)}


# ---------------------------------------------------------------------------
# 执行（task_runner 工作线程内）
# ---------------------------------------------------------------------------
def _execute_tuning(task_id: int) -> None:
    """工作函数：置 running → 并发跑全部组合 → 汇总终态与最优组合。"""
    from src.store import db as store

    store.set_tuning_task_running(task_id)
    start = time.perf_counter()
    try:
        task_row = store.get_tuning_task_row(task_id)
        if task_row is None:
            raise ValueError(f"调优任务不存在: {task_id}")
        combos = store.list_tuning_run_rows(task_id)

        # code 策略先做一次存在性检查（快速失败；组合内核心会按 id 再次解析，
        # 参数覆盖经 strategy_params seam 传入，不读 DB 参数列）
        if task_row["strategy_kind"] == "code":
            from src.services.strategy_library import get_code_strategy

            if get_code_strategy(task_row["strategy_id"], task_row["strategy_name"]) is None:
                raise ValueError(vmsg("tuning.codeStrategyNotFound",
                                      "代码策略不存在（需提供有效的 strategy_id）"))

        workers = max(1, min(get_env_int("QDT_TASK_WORKERS", 2), len(combos)))
        with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="qdt-tune") as pool:
            list(pool.map(lambda row: _run_combo(task_row, row), combos))

        # 汇总：按目标指标挑最优组合（基准同样参与排名）
        rows = store.list_tuning_run_rows(task_id)
        desc = bool(task_row["target_metric_desc"])
        best_index: Optional[int] = None
        best_value: Optional[float] = None
        for r in rows:
            if r["status"] != "succeeded" or not r["metrics_json"]:
                continue
            metrics = json.loads(r["metrics_json"])
            value = metrics.get(task_row["target_metric"])
            if value is None:
                continue
            value = float(value)
            if best_value is None or (value > best_value if desc else value < best_value):
                best_value, best_index = value, int(r["combo_index"])

        duration_ms = int((time.perf_counter() - start) * 1000)
        if best_index is None:
            store.finish_tuning_task_if_active(
                task_id, "failed", None, "所有参数组合均失败", duration_ms)
        else:
            store.finish_tuning_task_if_active(task_id, "succeeded", best_index, None, duration_ms)
        logger.info("调优任务完成: task=%s 最优组合=%s 用时=%dms", task_id, best_index, duration_ms)
    except Exception as e:
        logger.exception("调优任务失败: task=%s", task_id)
        store.fail_tuning_task_if_active(task_id, str(e))
        store.fail_tuning_runs_if_active(task_id, "任务中断")


def _run_combo(task_row: Any, combo_row: Any) -> None:
    """执行单个组合：running → 回测（strategy_params 覆盖）→ 组合终态落库。"""
    from src.backtest.backtest_manager import _format_metrics_json, _run_backtest_core
    from src.store import db as store

    task_id = int(task_row["id"])
    combo_index = int(combo_row["combo_index"])
    combo_params = json.loads(combo_row["params_json"] or "{}")
    store.update_tuning_run_result(task_id, combo_index, "running")
    start = time.perf_counter()
    try:
        core = _run_backtest_core(
            strategy_name=task_row["strategy_name"], stock_code=task_row["stock_code"],
            start_date=task_row["start_date"], end_date=task_row["end_date"],
            initial_capital=task_row["initial_capital"], commission_rate=task_row["commission_rate"],
            benchmark_index="SP500" if task_row["market"] == "us" else "000300",
            slippage_rate=0.0005, market=task_row["market"],
            strategy_kind=task_row["strategy_kind"], strategy_id=task_row["strategy_id"],
            strategy_params=combo_params,
        )
        metrics, _risk = _format_metrics_json(
            core["metrics_raw"], core.get("performance_report"), core.get("risk_report"),
            alpha=core["alpha"], beta=core["beta"], info_ratio=core["info_ratio"],
        )
        dates = [d.strftime("%Y-%m-%d") for d in core["daily_returns"].index]
        equity = [float(v) for v in core["equity"].tolist()]
        ds_dates, ds_equity = _downsample_xy(dates, equity, EQUITY_POINTS)
        duration_ms = int((time.perf_counter() - start) * 1000)
        store.update_tuning_run_result(
            task_id, combo_index, "succeeded", metrics=metrics,
            dates=ds_dates, equity=ds_equity, duration_ms=duration_ms,
        )
        store.bump_tuning_progress(task_id, succeeded=1)
        logger.debug("调优组合完成: task=%s combo=%s 用时=%dms", task_id, combo_index, duration_ms)
    except Exception as e:
        logger.warning("调优组合失败: task=%s combo=%s err=%s", task_id, combo_index, e)
        store.update_tuning_run_result(
            task_id, combo_index, "failed", error=str(e),
            duration_ms=int((time.perf_counter() - start) * 1000),
        )
        store.bump_tuning_progress(task_id, succeeded=0)


def _abandon_tuning(task_id: int) -> None:
    """调优看门狗：任务未终态则整体标 failed，活跃组合一并标记（条件更新防覆盖）。"""
    try:
        from src.store import db as store

        row = store.get_tuning_task_row(task_id)
        if row is None or row["status"] not in ("queued", "running"):
            return
        message = "调优超时，已放弃等待（后台线程将继续运行至自然结束，结果不采纳）"
        store.fail_tuning_task_if_active(task_id, message)
        store.fail_tuning_runs_if_active(task_id, message)
        logger.warning("调优任务 %s 超时，已放弃等待", task_id)
    except Exception:
        logger.exception("调优超时看门狗执行失败 task_id=%s", task_id)


def _downsample_xy(dates: List[str], values: List[float], max_points: int) -> Tuple[List[str], List[float]]:
    """日期与净值按同一组下标等距降采样（保首尾，x/y 对齐）。"""
    n = len(values)
    if n <= max_points or n <= 2:
        return dates, values
    step = (n - 1) / (max_points - 1)
    idx = [int(i * step) for i in range(max_points)]
    return [dates[i] for i in idx], [values[i] for i in idx]


# ---------------------------------------------------------------------------
# 查询
# ---------------------------------------------------------------------------
def get_tuning_detail(task_id: int) -> Optional[Dict[str, Any]]:
    """任务详情 + 全部组合（含指标与降采样净值，归一化对比图数据源）。"""
    from src.store import db as store

    row = store.get_tuning_task_row(task_id)
    if row is None:
        return None
    detail = store.row_to_tuning_task_dict(row)
    detail["combos"] = [
        store.row_to_tuning_run_dict(r, unpack_series=True)
        for r in store.list_tuning_run_rows(task_id)
    ]
    return detail


def list_tuning_tasks(strategy_kind: Optional[str] = None, strategy_id: Optional[int] = None,
                      limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
    """任务列表（新→旧，不含组合）。"""
    from src.store import db as store

    rows = store.list_tuning_task_rows(
        strategy_kind=strategy_kind, strategy_id=strategy_id,
        limit=max(1, min(int(limit), 200)), offset=max(0, int(offset)),
    )
    return [store.row_to_tuning_task_dict(r) for r in rows]


# ---------------------------------------------------------------------------
# 应用参数（唯一回写策略存储的入口）
# ---------------------------------------------------------------------------
def apply_tuning_params(task_id: int, combo_index: int) -> Dict[str, Any]:
    """把指定组合的网格参数应用回策略（只改参数，不动源码/其他键）。

    code 策略：合并进 DB 参数列（经 update_code_strategy，自动快照版本）；
    template 策略：合并进 strategies.json 的 parameters（经既有 update_strategy）。
    """
    from src.store import db as store

    task_row = store.get_tuning_task_row(task_id)
    if task_row is None:
        raise ValueError(vmsg("tuning.taskNotFound", "调优任务不存在"))
    if task_row["status"] not in ("succeeded", "failed"):
        raise ValueError(vmsg("tuning.taskNotFinished", "调优任务尚未结束，无法应用参数"))
    combo = store.get_tuning_run_row(task_id, combo_index)
    if combo is None:
        raise ValueError(vmsg("tuning.comboNotFound", "参数组合不存在"))
    if combo["status"] != "succeeded":
        raise ValueError(vmsg("tuning.comboNotSucceeded", "该参数组合未成功完成，无法应用"))

    combo_params = json.loads(combo["params_json"] or "{}")
    grid_keys = json.loads(task_row["grid_keys_json"] or "[]")
    override = {k: combo_params[k] for k in grid_keys if k in combo_params}

    if task_row["strategy_kind"] == "code":
        from src.services.strategy_library import get_code_strategy, update_code_strategy

        current = get_code_strategy(task_row["strategy_id"], task_row["strategy_name"])
        if current is None:
            raise ValueError(vmsg("tuning.codeStrategyNotFound",
                                  "代码策略不存在（需提供有效的 strategy_id）"))
        merged = {**dict(current["params"] or {}), **override}
        update_code_strategy(int(task_row["strategy_id"]), params=merged,
                             note=f"应用调优组合 #{combo_index}")
    else:
        from src.Strategy.strategy_manager import get_user_strategy
        from src.services.strategies import update_strategy

        config = get_user_strategy(task_row["strategy_name"])
        if not config:
            raise ValueError(vmsg("tuning.templateStrategyNotFound",
                                  "模板策略不存在: {name}", name=task_row["strategy_name"]))
        parameters = []
        for p in config.get("parameters", []):
            name = p.get("name")
            entry = dict(p)
            if name in override:
                entry["value"] = override[name]
            parameters.append(entry)
        # 网格里策略原本没有的键（不太可能，防御性兜底）追加
        known = {p.get("name") for p in parameters}
        for name, value in override.items():
            if name not in known:
                parameters.append({"name": name, "value": value})
        update_strategy(
            task_row["strategy_name"], config.get("description", ""),
            config.get("template", "sentiment_ma"), parameters,
        )

    logger.info("调优参数已应用: task=%s combo=%s params=%s", task_id, combo_index, override)
    return {"id": task_id, "combo_index": combo_index, "applied_params": override}
