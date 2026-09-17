"""因子库服务（v2 方案 D5）：Python 因子 CRUD + 编译执行 + 横截面分析。

- 因子源码契约：模块顶层 ``def compute(df) -> pd.Series``——df 为单标的
  OHLCV（DatetimeIndex 升序，中文列名），返回按日期索引的因子值 Series。
  校验复用 src/Strategy/code_validator.py 的 ast 白名单（防呆不防恶），
  仅必备函数与参数约定不同（require_params=False，FACTOR_PARAMS 等
  自定义常量不受限）。
- 市场本期限定 zh_a：universe 硬编码 HS300，us 显式本地化报错。
- 分析直接喂既有管线：src/services/factor.py 的 analyze_compute_fn
  （取数/面板/FactorAnalyzer/序列化唯一出口），不复制流水线。
- 版本语义与代码策略一致：更新/删除前自动快照，回滚先快照当前态。
"""
from __future__ import annotations

import logging
import sqlite3
from typing import Any, Dict, List, Optional

import pandas as pd

from src.utils.i18n import vmsg
from src.utils.validators import sanitize_string

logger = logging.getLogger(__name__)

# 因子名称上限（与策略名一致）
_MAX_NAME_LEN = 50


def _ensure_db() -> None:
    from src.store.db import init_db

    init_db()


# ---------------------------------------------------------------------------
# 源码校验与编译执行
# ---------------------------------------------------------------------------
def validate_factor_source(source: str) -> Dict[str, Any]:
    """因子源码校验（编辑器实时调用）：ast 白名单 + compute 必备。

    :return: {"ok": bool, "errors": [str]}
    """
    # 空源码/超限用因子措辞先行拦截（校验器内同类文案是"策略"措辞）
    if not source or not source.strip():
        return {"ok": False, "errors": [vmsg("factorlib.sourceEmpty", "因子代码不能为空")]}
    from src.Strategy.code_validator import MAX_SOURCE_BYTES

    if len(source.encode("utf-8")) > MAX_SOURCE_BYTES:
        return {"ok": False, "errors": [vmsg("factorlib.sourceTooLarge", "因子代码超过大小上限（100KB）")]}
    from src.Strategy.code_validator import validate_source as _validate

    errors, _defaults = _validate(source, required_functions=("compute",), require_params=False)
    return {"ok": not errors, "errors": errors}


def compile_factor(source: str):
    """编译因子源码，返回 compute 可调用（executor 线程内亦安全）。

    :raises ValueError: 校验未通过（文案已本地化）
    """
    result = validate_factor_source(source)
    if not result["ok"]:
        raise ValueError("；".join(result["errors"]))
    namespace: Dict[str, Any] = {"pd": pd}
    import math

    import numpy as np

    namespace["np"] = np
    namespace["math"] = math
    try:
        exec(compile(source, "<factor>", "exec"), namespace)  # noqa: S102（定位"防呆不防恶"，见模块 docstring）
    except Exception as e:
        raise ValueError(vmsg("factorlib.compileFailed", "因子代码执行失败: {err}", err=str(e)))
    compute = namespace.get("compute")
    if not callable(compute):
        raise ValueError(vmsg("factorlib.sourceMissingFunction",
                              "缺少必备函数 {name}（模块顶层定义）", name="compute"))
    return compute


def run_compute(compute, df: pd.DataFrame) -> pd.Series:
    """在单标的 OHLCV 上执行 compute 并做返回契约校验（数值化 + 去 NA）。

    :raises ValueError: 返回类型/索引/数值契约不满足（文案已本地化）
    """
    try:
        result = compute(df)
    except ValueError:
        raise
    except Exception as e:
        raise ValueError(vmsg("factorlib.computeFailed", "因子计算失败: {err}", err=str(e)))
    if not isinstance(result, pd.Series):
        raise ValueError(vmsg("factorlib.badReturnType",
                              "compute 必须返回 pandas Series（实际返回 {t}）", t=type(result).__name__))
    result = pd.to_numeric(result, errors="coerce").dropna()
    if result.empty:
        raise ValueError(vmsg("factorlib.emptyResult",
                              "compute 返回的因子值全为空（请检查窗口长度或 dropna）"))
    if not set(result.index).issubset(set(df.index)):
        raise ValueError(vmsg("factorlib.indexMismatch",
                              "返回 Series 的索引必须是输入 DataFrame 日期索引的子集"))
    return result


# ---------------------------------------------------------------------------
# CRUD（版本语义与代码策略一致）
# ---------------------------------------------------------------------------
def _validate_name(name: str) -> str:
    name = sanitize_string(str(name or ""), _MAX_NAME_LEN).strip()
    if not name:
        raise ValueError(vmsg("factorlib.nameEmpty", "因子名称不能为空"))
    if len(name) < 2:
        raise ValueError(vmsg("factorlib.nameTooShort", "因子名称长度不能少于 2 个字符"))
    if len(name) > _MAX_NAME_LEN:
        raise ValueError(vmsg("factorlib.nameTooLong", "因子名称最长 {max} 个字符", max=_MAX_NAME_LEN))
    return name


def _validate_market(market: str) -> str:
    market = str(market or "zh_a")
    if market != "zh_a":
        # D5：universe 硬编码 HS300，本期限定 zh_a
        raise ValueError(vmsg("factorlib.badMarket", "因子库仅支持 A 股（zh_a）"))
    return market


def create_factor(name: str, description: str, market: str, source: str, tags: str = "") -> Dict[str, Any]:
    """创建因子（源码先过校验）。"""
    from src.store import db as store

    _ensure_db()
    name = _validate_name(name)
    market = _validate_market(market)
    check = validate_factor_source(str(source or ""))
    if not check["ok"]:
        raise ValueError("；".join(check["errors"]))
    try:
        factor_id = store.insert_factor(name, market, str(description or ""), str(source), str(tags or ""))
    except sqlite3.IntegrityError:
        raise ValueError(vmsg("factorlib.duplicateName", "因子名称已存在: {name}", name=name))
    compile_factor(source)  # 试编译（校验已过，纵深防御）
    return {"id": factor_id, "name": name}


def _snapshot_current(factor_id: int, note: str) -> None:
    from src.store import db as store

    row = store.get_factor_row(factor_id)
    store.insert_factor_version(
        factor_id, row["name"], row["market"], row["description"],
        row["source"], row["tags"], note,
    )


def update_factor(factor_id: int, description: Optional[str] = None,
                  source: Optional[str] = None, tags: Optional[str] = None,
                  market: Optional[str] = None, note: str = "") -> Dict[str, Any]:
    """更新因子（先快照旧态为版本）。仅更新传入字段。"""
    from src.store import db as store

    _ensure_db()
    row = store.get_factor_row(int(factor_id))
    if row is None:
        raise ValueError(vmsg("factorlib.notFound", "因子不存在"))
    fields: Dict[str, Any] = {}
    if description is not None:
        fields["description"] = str(description)
    if tags is not None:
        fields["tags"] = str(tags)
    if market is not None:
        fields["market"] = _validate_market(market)
    if source is not None:
        source = str(source)
        check = validate_factor_source(source)
        if not check["ok"]:
            raise ValueError("；".join(check["errors"]))
        fields["source"] = source
    _snapshot_current(int(factor_id), note or "")
    try:
        store.update_factor_row(int(factor_id), fields)
        store.prune_factor_versions(int(factor_id), keep=20)
    except sqlite3.IntegrityError:
        raise ValueError(vmsg("factorlib.duplicateName", "因子名称已存在"))
    return {"id": int(factor_id), "updated": bool(fields)}


def delete_factor(factor_id: int) -> Dict[str, Any]:
    """删除因子（删除前自动快照）。"""
    from src.store import db as store

    _ensure_db()
    row = store.get_factor_row(int(factor_id))
    if row is None:
        raise ValueError(vmsg("factorlib.notFound", "因子不存在"))
    _snapshot_current(int(factor_id), "删除前快照")
    store.delete_factor_row(int(factor_id))
    return {"id": int(factor_id), "deleted": True}


def list_factors(market: Optional[str] = None, q: str = "",
                 limit: int = 200, offset: int = 0) -> List[Dict[str, Any]]:
    """因子列表（不含源码全文）。"""
    from src.store import db as store

    _ensure_db()
    rows = store.list_factor_rows(market=market, q=q, limit=limit, offset=offset)
    return [store.row_to_factor_dict(r, include_source=False) for r in rows]


def get_factor_detail(factor_id: int) -> Optional[Dict[str, Any]]:
    """因子详情（含源码全文）。"""
    from src.store import db as store

    _ensure_db()
    row = store.get_factor_row(int(factor_id))
    if row is None:
        return None
    return store.row_to_factor_dict(row, include_source=True)


def list_versions(factor_id: int) -> List[Dict[str, Any]]:
    from src.store import db as store

    _ensure_db()
    if store.get_factor_row(int(factor_id)) is None:
        raise ValueError(vmsg("factorlib.notFound", "因子不存在"))
    return [dict(r) for r in store.list_factor_versions(int(factor_id))]


def get_version_source(version_id: int) -> Optional[Dict[str, Any]]:
    from src.store import db as store

    _ensure_db()
    row = store.get_factor_version(int(version_id))
    return store.row_to_factor_dict(row) if row else None


def restore_version(factor_id: int, version_id: int) -> Dict[str, Any]:
    """回滚到指定版本（当前态先快照）。"""
    from src.store import db as store

    _ensure_db()
    if store.get_factor_row(int(factor_id)) is None:
        raise ValueError(vmsg("factorlib.notFound", "因子不存在"))
    version = store.get_factor_version(int(version_id))
    if version is None or version["factor_id"] != int(factor_id):
        raise ValueError(vmsg("factorlib.versionNotFound", "因子版本不存在"))
    _snapshot_current(int(factor_id), "回滚前快照")
    store.update_factor_row(int(factor_id), {
        "name": version["name"], "market": version["market"],
        "description": version["description"], "source": version["source"], "tags": version["tags"],
    })
    store.prune_factor_versions(int(factor_id), keep=20)
    return {"id": int(factor_id), "restored_from": int(version_id)}


# ---------------------------------------------------------------------------
# 分析（复用 services/factor.py 管线；同步调用，路由层走线程池）
# ---------------------------------------------------------------------------
def analyze_user_factor(factor_id: int, start_date: str, end_date: str,
                        n_quantiles: int = 5, forward_period: int = 5) -> Dict[str, Any]:
    """运行用户因子的横截面分析（HS300 × IC/RankIC/ICIR/分层/单调性）。

    :return: JSON 可序列化 dict（含 ic_stats/ic_series/quantile_*），失败带 {"error": ...}
    :raises ValueError: 因子不存在/市场非法（路由层 404/400）
    """
    from src.store import db as store

    _ensure_db()
    row = store.get_factor_row(int(factor_id))
    if row is None:
        raise ValueError(vmsg("factorlib.notFound", "因子不存在"))
    if row["market"] != "zh_a":
        raise ValueError(vmsg("factorlib.badMarket", "因子库仅支持 A 股（zh_a）"))

    compute = compile_factor(row["source"])

    def _compute(df: pd.DataFrame) -> pd.Series:
        # 单股失败跳过（数据不足/退市股等），与内置因子"失败返回空"契约一致；
        # 全部失败时 _analyze_panels 会报"有效数据不足"
        try:
            return run_compute(compute, df)
        except ValueError as e:
            logger.warning("因子计算跳过一只股票: %s", e)
            return pd.Series(dtype=float)

    from src.services.factor import analyze_compute_fn

    return analyze_compute_fn(
        _compute, row["name"], start_date, end_date,
        n_quantiles=int(n_quantiles), forward_period=int(forward_period),
    )
