"""策略服务：策略列表/详情/创建/更新/删除的业务编排。

原 web_app.py 中 3 个策略列表路由（HTML /strategies、JSON /api/strategies、
JSON /api/strategies/list）+ detail/create/update/delete 共享同一套底层调用，
但各写一遍。本模块统一为深接口，路由层变为薄适配器。
"""
import logging
from datetime import datetime
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


def _extract_params(strategy_class, strategy_name: str = "") -> list:
    """从 backtrader 策略类提取参数列表。"""
    parameters = []
    if hasattr(strategy_class, 'params'):
        try:
            for param_name, default_value in strategy_class.params._getpairs().items():
                parameters.append({
                    "name": param_name,
                    "default": default_value,
                    "type": type(default_value).__name__,
                })
        except (AttributeError, TypeError) as e:
            logger.warning(f"获取策略 {strategy_name} 参数时出错: {e}")
    return parameters


def list_strategy_names() -> List[str]:
    """获取缓存的用户策略名列表（仅用户策略，供下拉框/首页）。

    注意：缓存逻辑仍由 web_app.py 的 get_cached_strategies 管理，
    此函数是底层加载入口（无缓存）。
    """
    from src.Strategy.strategy_manager import load_user_strategies
    return list(load_user_strategies().keys())


def list_strategy_details() -> List[Dict]:
    """获取全部策略详情（内置 + 用户），数组形式。

    统一了原 /strategies (HTML) 与 /api/strategies/list (JSON) 的业务逻辑。
    内置策略也提取真实参数（修复原 JSON 版硬编码空数组的问题）。
    """
    from src.Strategy.strategy_manager import load_user_strategies, get_strategy_templates
    from src.Strategy import global_strategy_manager

    user_strategies = load_user_strategies()
    strategy_templates = get_strategy_templates()
    builtin = global_strategy_manager.get_all_strategies()

    details: List[Dict] = []
    # 内置策略
    for name, strategy_class in builtin.items():
        tmpl_name = "sentiment_ma"
        tmpl = strategy_templates.get(tmpl_name, {})
        details.append({
            "name": name,
            "description": getattr(strategy_class, '__doc__', '') or '',
            "parameters": _extract_params(strategy_class, name),
            "template": tmpl_name,
            "template_name": tmpl.get("name", ""),
            "is_user_strategy": False,
        })
    # 用户策略
    for name, config in user_strategies.items():
        tmpl_name = config.get("template", "sentiment_ma")
        tmpl = strategy_templates.get(tmpl_name, {})
        details.append({
            "name": name,
            "description": config.get("description", ""),
            "parameters": config.get("parameters", []),
            "template": tmpl_name,
            "template_name": tmpl.get("name", ""),
            "is_user_strategy": True,
        })
    return details


def get_strategy_detail(name: str) -> Optional[Dict]:
    """获取单个策略详情。返回 None 表示不存在。

    统一了原 /api/strategies/detail/{name} 的逻辑。
    """
    from src.Strategy.strategy_manager import get_user_strategy
    from src.Strategy import global_strategy_manager

    user_strategy = get_user_strategy(name)
    if user_strategy:
        return {
            "name": name,
            "description": user_strategy.get("description", ""),
            "template": user_strategy.get("template", "sentiment_ma"),
            "parameters": user_strategy.get("parameters", []),
            "is_user_strategy": True,
        }

    strategy_class = global_strategy_manager.get_strategy(name)
    if not strategy_class:
        return None

    return {
        "name": name,
        "description": getattr(strategy_class, '__doc__', '') or '',
        "parameters": _extract_params(strategy_class, name),
        "is_user_strategy": False,
    }


def create_strategy(name: str, description: str, template: str, parameters: list) -> Dict:
    """创建自定义策略（自定义参数）。

    :return: {"success": True, "name": ...} 或 {"error": "..."}
    """
    from src.Strategy.strategy_manager import save_user_strategy, is_user_strategy

    if is_user_strategy(name):
        return {"error": "策略名称已存在"}
    if not parameters:
        return {"error": "自定义参数不能为空"}

    config = {
        "description": description,
        "template": template,
        "parameters": parameters,
        "created_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    }
    if save_user_strategy(name, config):
        return {"success": True, "name": name}
    return {"error": "保存策略失败"}


def create_from_template(name: str, description: str, template: str) -> Dict:
    """根据模板创建策略（使用模板默认参数）。

    :return: {"success": True, "name": ..., "parameters": [...]} 或 {"error": "..."}
    """
    from src.Strategy.strategy_manager import (
        save_user_strategy, is_user_strategy, get_strategy_template,
    )

    if is_user_strategy(name):
        return {"error": "策略名称已存在"}

    tmpl = get_strategy_template(template)
    if not tmpl:
        return {"error": f"模板 {template} 不存在"}

    base_params = tmpl.get("base_params", [])
    config = {
        "description": description,
        "template": template,
        "parameters": base_params,
        "created_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    }
    if save_user_strategy(name, config):
        return {"success": True, "name": name, "parameters": base_params}
    return {"error": "保存策略失败"}


def update_strategy(name: str, description: str, template: str, parameters: list) -> Dict:
    """更新用户策略。

    :return: {"success": True, "name": ...} 或 {"error": "..."}
    """
    from src.Strategy.strategy_manager import save_user_strategy, is_user_strategy

    if not is_user_strategy(name):
        return {"error": f"策略 {name} 不存在或不是用户策略"}

    config = {
        "description": description,
        "template": template,
        "parameters": parameters,
        "created_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    }
    if save_user_strategy(name, config):
        return {"success": True, "name": name}
    return {"error": "保存策略失败"}


def delete_strategy(name: str) -> Dict:
    """删除用户策略。

    :return: {"success": True} 或 {"error": "..."}
    """
    from src.Strategy.strategy_manager import delete_user_strategy as _delete, is_user_strategy

    if not is_user_strategy(name):
        return {"error": f"策略 {name} 不存在或不是用户策略"}
    if _delete(name):
        return {"success": True}
    return {"error": f"删除策略 {name} 失败"}


def get_templates() -> Dict:
    """获取策略模板。"""
    from src.Strategy.strategy_manager import get_strategy_templates
    return get_strategy_templates()
