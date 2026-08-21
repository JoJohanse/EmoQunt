"""参数解析单点：统一 value/default 优先级规则。

历史上有两套优先级：
- Strategy 物化 ``extract_param_value``：value 优先、default 兜底
- 舆情 ``sentiment_weight`` 读取：default 优先、value 兜底、0.3 最终兜底

本模块以 ``resolve_param(prefer=...)`` 统一收敛，保持各自原语义
行为不变，仅消除复制。
"""

from typing import Any


def resolve_param(param: dict, fallback=None, prefer: str = "value") -> Any:
    """从参数 dict 解析值。

    :param param: 形如 {"name": "...", "value": ..., "default": ...}
    :param fallback: 两者皆缺（或为 None）时返回
    :param prefer: "value" 时 value 优先 default 兜底；
                   "default" 时反之
    :return: 解析到的值或 fallback
    """
    if not isinstance(param, dict):
        return fallback
    if prefer == "value":
        primary, secondary = "value", "default"
    elif prefer == "default":
        primary, secondary = "default", "value"
    else:
        # 未知 prefer 视为 value 优先，避免静默错误
        primary, secondary = "value", "default"

    v = param.get(primary)
    if v is not None:
        return v
    v2 = param.get(secondary)
    if v2 is not None:
        return v2
    return fallback


def resolve_sentiment_weight(parameters: list) -> float:
    """从 parameters 列表解析 sentiment_weight。

    语义与原 ``services/sentiment.py`` 内联逻辑一致：
    default 优先、value 兜底、0.3 最终兜底；float 转换失败回退 0.3。

    :param parameters: 参数描述列表
    :return: sentiment_weight 浮点值
    """
    if not isinstance(parameters, list) or not parameters:
        return 0.3

    raw_value = None
    found = False
    for param in parameters:
        if not isinstance(param, dict):
            continue
        if param.get("name") != "sentiment_weight":
            continue
        # 记录最后一次匹配（与原 for 循环覆盖语义一致）
        raw_value = resolve_param(param, fallback=0.3, prefer="default")
        found = True

    if not found:
        return 0.3

    try:
        return float(raw_value)
    except (TypeError, ValueError):
        return 0.3
