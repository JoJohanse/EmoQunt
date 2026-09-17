"""策略库 v2 服务：代码策略 CRUD + 源码校验 + 版本快照/回滚。

与模板策略（strategies.json，services/strategies.py）的双轨边界：
本模块只管 SQLite 里的代码策略；模板策略的 CRUD/缓存完全不动。
列表读取直接查 SQLite（单用户量级微秒级，无需再叠 TTL 缓存——若未来
需要缓存，必须复用 src/utils/ttl_cache.py 且本模块内"谁写谁失效"）。

所有变更函数在更新成功前先落版本快照（"更新即快照"），版本含源码全文，
保留最近 20 条防膨胀。回滚 = 把版本内容写回主行（同样先快照当前态）。
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from src.utils.i18n import vmsg
from src.utils.validators import validate_strategy_name

logger = logging.getLogger(__name__)

VALID_MARKETS = ("zh_a", "us")
VERSION_KEEP = 20


def validate_source(source: str) -> Dict[str, Any]:
    """校验源码（保存前/前端实时校验共用）。

    :return: {"ok": bool, "errors": [str], "params": 默认参数 dict}
    """
    from src.Strategy.code_validator import validate_source as _validate

    errors, defaults = _validate(source or "")
    return {"ok": not errors, "errors": errors, "params": defaults}


def _validate_market(market: str) -> None:
    if market not in VALID_MARKETS:
        raise ValueError(vmsg("library.marketInvalid", "market 仅支持 zh_a 或 us"))


def _validate_params(params: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if params is None:
        return {}
    if not isinstance(params, dict) or not all(isinstance(k, str) for k in params):
        raise ValueError(vmsg("library.paramsInvalid", "params 必须是键值参数对象"))
    return params


def get_code_strategy(strategy_id: Optional[int], name: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """按 id（优先）或名称取代码策略行（回测核心解析用）。"""
    from src.store import db as store

    _ensure_db()
    row = None
    if strategy_id is not None:
        row = store.get_strategy_row(int(strategy_id))
    if row is None and name:
        row = store.get_strategy_row_by_name(name)
    if row is None:
        return None
    return store.row_to_strategy_dict(row)


def create_code_strategy(name: str, description: str, market: str, source: str,
                         params: Optional[Dict[str, Any]] = None, tags: str = "") -> Dict[str, Any]:
    """创建代码策略（源码先过校验器）。

    :return: {"id": ..., "name": ..., "params": ...}；名称重复/校验失败抛 ValueError
    """
    from src.store import db as store

    _ensure_db()
    name = str(name or "").strip()
    valid, error = validate_strategy_name(name)
    if not valid:
        raise ValueError(error)
    _validate_market(market)
    params = _validate_params(params)

    check = validate_source(source)
    if not check["ok"]:
        raise ValueError("；".join(check["errors"]))
    # 用户显式传入的 params 优先（覆盖源码默认值），否则落源码提取的默认
    effective = check["params"] if not params else params

    if store.get_strategy_row_by_name(name) is not None:
        raise ValueError(vmsg("library.nameExists", "策略名称已存在"))
    try:
        strategy_id = store.insert_strategy(name, market, str(description or ""), source,
                                            effective, str(tags or ""))
    except Exception as e:
        # 名称唯一约束并发兜底
        if "UNIQUE" in str(e):
            raise ValueError(vmsg("library.nameExists", "策略名称已存在"))
        raise
    logger.info("代码策略已创建: id=%s name=%s market=%s", strategy_id, name, market)
    return {"id": strategy_id, "name": name, "params": effective}


def update_code_strategy(strategy_id: int, description: Optional[str] = None,
                         source: Optional[str] = None, params: Optional[Dict[str, Any]] = None,
                         tags: Optional[str] = None, market: Optional[str] = None,
                         note: str = "") -> Dict[str, Any]:
    """更新代码策略（先快照旧态为版本）。仅更新传入字段。

    :return: {"id": ..., "updated": True}
    """
    from src.store import db as store

    _ensure_db()
    row = store.get_strategy_row(int(strategy_id))
    if row is None:
        raise ValueError(vmsg("library.strategyNotFound", "策略不存在"))

    fields: Dict[str, Any] = {}
    if source is not None:
        check = validate_source(source)
        if not check["ok"]:
            raise ValueError("；".join(check["errors"]))
        fields["source"] = source
    if params is not None:
        fields["params_json"] = _json_dumps(_validate_params(params))
    if description is not None:
        fields["description"] = str(description)
    if tags is not None:
        fields["tags"] = str(tags)
    if market is not None:
        _validate_market(market)
        fields["market"] = market
    if not fields:
        return {"id": int(strategy_id), "updated": False}

    # 更新即快照（旧态）
    store.insert_strategy_version(
        row["id"], row["name"], row["market"], row["description"], row["source"],
        _loads(row["params_json"]), row["tags"], note=str(note or ""),
    )
    store.prune_strategy_versions(row["id"], keep=VERSION_KEEP)
    store.update_strategy_row(int(strategy_id), fields)
    logger.info("代码策略已更新: id=%s fields=%s", strategy_id, list(fields))
    return {"id": int(strategy_id), "updated": True}


def delete_code_strategy(strategy_id: int) -> Dict[str, Any]:
    """删除代码策略（先快照当前态，便于追溯；运行记录保留弱引用）。"""
    from src.store import db as store

    _ensure_db()
    row = store.get_strategy_row(int(strategy_id))
    if row is None:
        raise ValueError(vmsg("library.strategyNotFound", "策略不存在"))
    store.insert_strategy_version(
        row["id"], row["name"], row["market"], row["description"], row["source"],
        _loads(row["params_json"]), row["tags"], note="删除前快照",
    )
    store.delete_strategy_row(int(strategy_id))
    logger.info("代码策略已删除: id=%s name=%s", strategy_id, row["name"])
    return {"id": int(strategy_id), "deleted": True}


def get_strategy_detail(strategy_id: int) -> Optional[Dict[str, Any]]:
    """策略详情：全字段 + 源码默认参数 + 生效参数（DB 列为真相）。"""
    strategy = get_code_strategy(int(strategy_id))
    if strategy is None:
        return None
    from src.Strategy.code_validator import validate_source as _validate

    _errors, defaults = _validate(strategy["source"])
    strategy["default_params"] = defaults
    return strategy


def list_strategies(market: Optional[str] = None, q: str = "",
                    limit: int = 200, offset: int = 0) -> List[Dict[str, Any]]:
    """策略列表（卡片用：不含源码全文；附最近一次成功回测摘要）。"""
    from src.store import db as store

    _ensure_db()
    rows = store.list_strategy_rows(market=market, q=q, limit=limit, offset=offset)
    out = []
    for row in rows:
        item = store.row_to_strategy_dict(row, include_source=False)
        last = _last_succeeded_run(row["id"])
        item["last_run"] = last
        out.append(item)
    return out


def _last_succeeded_run(strategy_id: int) -> Optional[Dict[str, Any]]:
    """最近一次成功回测的指标摘要（策略卡片展示）。"""
    from src.store import db as store

    runs = store.list_run_rows(strategy_kind="code", strategy_id=strategy_id,
                               status="succeeded", limit=1)
    if not runs:
        return None
    row = runs[0]
    metrics = {}
    if row["metrics_json"]:
        m = __import__("json").loads(row["metrics_json"])
        metrics = {"总收益率": m.get("总收益率"), "夏普比率": m.get("夏普比率"),
                   "最大回撤": m.get("最大回撤"), "交易次数": m.get("交易次数")}
    return {"id": row["id"], "updated_at": row["updated_at"],
            "stock_code": row["stock_code"], "metrics": metrics}


def list_versions(strategy_id: int) -> List[Dict[str, Any]]:
    """版本列表（不含源码全文）。策略不存在抛 ValueError。"""
    from src.store import db as store

    _ensure_db()
    if store.get_strategy_row(int(strategy_id)) is None:
        raise ValueError(vmsg("library.strategyNotFound", "策略不存在"))
    return [dict(r) for r in store.list_strategy_versions(int(strategy_id))]


def restore_version(strategy_id: int, version_id: int) -> Dict[str, Any]:
    """回滚：把版本内容写回主行（当前态先快照）。"""
    from src.store import db as store

    _ensure_db()
    row = store.get_strategy_row(int(strategy_id))
    if row is None:
        raise ValueError(vmsg("library.strategyNotFound", "策略不存在"))
    version = store.get_strategy_version(int(version_id))
    if version is None or version["strategy_id"] != int(strategy_id):
        raise ValueError(vmsg("library.versionNotFound", "版本不存在"))
    store.insert_strategy_version(
        row["id"], row["name"], row["market"], row["description"], row["source"],
        _loads(row["params_json"]), row["tags"], note=f"回滚到版本 {version_id} 前快照",
    )
    store.prune_strategy_versions(row["id"], keep=VERSION_KEEP)
    store.update_strategy_row(int(strategy_id), {
        "source": version["source"],
        "params_json": version["params_json"],
        "description": version["description"],
        "tags": version["tags"],
    })
    logger.info("策略 %s 已回滚到版本 %s", strategy_id, version_id)
    return {"id": int(strategy_id), "restored_from": int(version_id)}


def get_version_source(version_id: int) -> Optional[Dict[str, Any]]:
    """版本全文（详情查看用）。"""
    from src.store import db as store

    _ensure_db()
    version = store.get_strategy_version(int(version_id))
    if version is None:
        return None
    out = dict(version)
    out["params"] = _loads(version["params_json"])
    return out


# ---------------------------------------------------------------------------
# 内部
# ---------------------------------------------------------------------------
def _ensure_db() -> None:
    from src.store.db import init_db

    init_db()


def _json_dumps(params: Dict[str, Any]) -> str:
    import json

    return json.dumps(params, ensure_ascii=False)


def _loads(raw: str) -> Dict[str, Any]:
    import json

    try:
        return json.loads(raw or "{}")
    except (ValueError, TypeError):
        return {}
