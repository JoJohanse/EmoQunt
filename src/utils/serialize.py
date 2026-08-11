"""JSON 序列化工具：把 pandas/numpy/datetime 值安全转为 JSON 可序列化的 Python 原生类型。

各 service / backtest 适配层此前各自重复实现 "safe-float with inf/NaN guard"，
本模块统一为唯一来源。
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd


def safe_float(value: Any, ndigits: int = 6) -> float:
    """数值安全转 float 并四舍五入；非数值/NaN/inf 返回 0.0。

    :param value: 任意值（int/float/np 标量/其它）
    :param ndigits: 保留小数位
    :return: 四舍五入的 float，或 0.0（不可解析/非有限时）
    """
    try:
        f = float(value)
        if not np.isfinite(f):
            return 0.0
        return round(f, ndigits)
    except (TypeError, ValueError):
        return 0.0


def safe_metric(value: Any, ndigits: int = 6) -> Any:
    """序列化单个指标值：

    - datetime / pd.Timestamp → 'YYYY-MM-DD' 字符串（pd.Timestamp 不是 datetime 子类，单独判）
    - 数值（含 np 标量）→ safe_float
    - 其它（str/bool/None）→ 原样返回
    """
    if isinstance(value, (datetime, pd.Timestamp)):
        return pd.Timestamp(value).strftime('%Y-%m-%d')
    if isinstance(value, bool):
        return value  # bool 是 int 子类，须在数值判断前拦截
    if isinstance(value, (int, float, np.floating, np.integer)):
        return safe_float(value, ndigits)
    return value


def json_safe(obj: Any, ndigits: int = 6) -> Any:
    """递归把嵌套结构（dict/list/Series/DataFrame）转为 JSON 可序列化对象。

    - dict → 递归处理 value
    - list/tuple → 递归处理元素
    - pd.Series → [{index, value}, ...]（dropna）
    - pd.DataFrame → {'index': [...], 'columns': [...], 'data': [[...], ...]}
    - datetime/Timestamp → ISO 日期 str
    - np 标量/数值 → safe_float（NaN→None）
    - 其它 → 原样
    """
    if obj is None:
        return None
    if isinstance(obj, (datetime, pd.Timestamp)):
        return pd.Timestamp(obj).strftime('%Y-%m-%d')
    if isinstance(obj, bool):
        return obj
    if isinstance(obj, (int, float, np.floating, np.integer)):
        f = float(obj)
        return round(f, ndigits) if np.isfinite(f) else None
    if isinstance(obj, str):
        return obj
    if isinstance(obj, pd.Series):
        obj = obj.dropna()
        return [{"date": d.strftime('%Y-%m-%d') if hasattr(d, 'strftime') else str(d),
                 "value": json_safe(v, ndigits)}
                for d, v in obj.items()]
    if isinstance(obj, pd.DataFrame):
        return {
            "index": [str(d) for d in obj.index.tolist()],
            "columns": list(obj.columns),
            "data": [[json_safe(c, ndigits) for c in row] for row in obj.values.tolist()],
        }
    if isinstance(obj, dict):
        return {str(k): json_safe(v, ndigits) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [json_safe(v, ndigits) for v in obj]
    # 兜底：str 化，避免未知类型导致 JSON 序列化崩溃
    return str(obj)
