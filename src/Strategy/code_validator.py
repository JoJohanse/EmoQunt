"""代码源码校验器（ast 白名单，"防呆不防恶"）。

策略与因子（v2 D5）共用同一校验出口，仅必备函数与参数约定不同：
- 代码策略：必备 initialize(context)/handle_data(context, data) + STRATEGY_PARAMS；
- 因子：必备 compute(df)（require_params=False，FACTOR_PARAMS 等自定义常量不受限）。

保存/加载代码策略前的唯一校验出口（loader 内再跑一遍属纵深防御）：
1. 源码大小上限 + 语法解析；
2. import 白名单（emoquant/math/statistics/datetime/collections/itertools/
   pandas/numpy），拒绝通配 import；
3. 危险内建调用黑名单（eval/exec/open/getattr/... —— getattr 同时封堵
   ``().__class__`` 之外的属性链绕过）；
4. dunder 属性访问封堵（``__class__``/``__globals__``/``__subclasses__`` 链）；
5. 必备生命周期函数 initialize(context) / handle_data(context, data)；
6. STRATEGY_PARAMS 必须是字面量 dict（str -> int/float/bool/str），
   成功时提取为默认参数。

定位声明：这是防呆机制（挡住 LLM 幻觉与常见误写），不是安全沙箱——
平台为本地单用户工具，恶意对抗不在防御范围内（v2 方案 D1/风险 §5）。
"""
from __future__ import annotations

import ast
from typing import Any, Dict, List, Tuple

from src.utils.i18n import vmsg

MAX_SOURCE_BYTES = 100 * 1024

# 允许的 import 顶层根（emoquant.* 为 SDK；pandas/numpy 服务于指标计算）
ALLOWED_IMPORT_ROOTS = {
    "emoquant", "math", "statistics", "datetime", "collections", "itertools",
    "decimal", "functools", "pandas", "numpy",
}

# 禁止调用的内建名（getattr/setattr/delattr 一并封堵，切断属性链绕过）
BANNED_CALLS = {
    "eval", "exec", "compile", "open", "__import__", "globals", "locals",
    "vars", "getattr", "setattr", "delattr", "breakpoint", "input", "super",
}

# 必备生命周期函数
REQUIRED_FUNCTIONS = ("initialize", "handle_data")

# STRATEGY_PARAMS 值允许的字面量类型
_PARAM_TYPES = (int, float, bool, str)


def validate_source(source: str, required_functions: Tuple[str, ...] = REQUIRED_FUNCTIONS,
                    require_params: bool = True) -> Tuple[List[str], Dict[str, Any]]:
    """校验代码源码（策略与因子共用同一 ast 白名单）。

    :param source: Python 源码
    :param required_functions: 模块顶层必备函数；策略用默认值，
                               因子库传 ``("compute",)``（D5：compute(df)->Series）
    :param require_params: 是否校验 STRATEGY_PARAMS 字面量 dict；
                           因子源码无此约定，传 False 跳过（FACTOR_PARAMS
                           等自定义常量不受限）
    :return: (errors, param_defaults)。errors 为空表示通过；
             param_defaults 为 STRATEGY_PARAMS 字面量提取的默认参数
            （源码未声明或 require_params=False 时为空 dict）。
    """
    errors: List[str] = []
    defaults: Dict[str, Any] = {}

    if not source or not source.strip():
        return [vmsg("library.sourceEmpty", "策略代码不能为空")], defaults
    if len(source.encode("utf-8")) > MAX_SOURCE_BYTES:
        return [vmsg("library.sourceTooLarge", "策略代码超过大小上限（100KB）")], defaults

    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        return [vmsg("library.sourceSyntaxError", "语法错误（第 {line} 行）: {msg}",
                     line=e.lineno or 0, msg=e.msg)], defaults

    # ---- 生命周期函数与 STRATEGY_PARAMS（仅模块顶层）----
    top_functions = set()
    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            top_functions.add(node.name)
        if require_params and isinstance(node, ast.Assign) and len(node.targets) == 1 \
                and isinstance(node.targets[0], ast.Name) and node.targets[0].id == "STRATEGY_PARAMS":
            ok, val_or_err = _extract_params_literal(node.value)
            if ok:
                defaults = val_or_err
            else:
                errors.append(vmsg(
                    "library.sourceBadParams",
                    "STRATEGY_PARAMS 必须是字面量字典（键为字符串，值为数字/布尔/字符串）"
                    "（第 {line} 行）: {err}",
                    line=getattr(node, "lineno", 0), err=val_or_err,
                ))
    for fn in required_functions:
        if fn not in top_functions:
            errors.append(vmsg("library.sourceMissingFunction",
                               "缺少必备函数 {name}（模块顶层定义）", name=fn))

    # ---- 遍历：import / 危险调用 / dunder 属性 ----
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                if root not in ALLOWED_IMPORT_ROOTS:
                    errors.append(vmsg("library.sourceBannedImport",
                                       "不允许导入模块 {name}（第 {line} 行）",
                                       name=alias.name, line=node.lineno))
        elif isinstance(node, ast.ImportFrom):
            root = (node.module or "").split(".")[0]
            if not node.module or root not in ALLOWED_IMPORT_ROOTS:
                errors.append(vmsg("library.sourceBannedImportFrom",
                                   "不允许从模块 {name} 导入（第 {line} 行）",
                                   name=node.module or "?", line=node.lineno))
            for alias in node.names:
                if alias.name == "*":
                    errors.append(vmsg("library.sourceWildcardImport",
                                       "不允许通配导入（第 {line} 行）", line=node.lineno))
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id in BANNED_CALLS:
                errors.append(vmsg("library.sourceBannedCall",
                                   "不允许调用 {name}()（第 {line} 行）",
                                   name=func.id, line=node.lineno))
        elif isinstance(node, ast.Attribute):
            if node.attr.startswith("__") and node.attr.endswith("__"):
                errors.append(vmsg("library.sourceBannedDunder",
                                   "不允许访问双下划线属性 .{name}（第 {line} 行）",
                                   name=node.attr, line=node.lineno))

    # 去重（同名问题可能在 walk 中重复出现）并保序
    seen, uniq = set(), []
    for e in errors:
        if e not in seen:
            seen.add(e)
            uniq.append(e)
    return uniq, defaults


def _extract_params_literal(node: ast.AST) -> Tuple[bool, Any]:
    """从 AST 字面量提取 STRATEGY_PARAMS 的 dict 值。

    :return: (ok, dict 或错误字符串)
    """
    if not isinstance(node, ast.Dict):
        return False, "必须是字典字面量"
    out: Dict[str, Any] = {}
    for key_node, value_node in zip(node.keys, node.values):
        if not isinstance(key_node, ast.Constant) or not isinstance(key_node.value, str):
            return False, "字典键必须是字符串字面量"
        try:
            value = ast.literal_eval(value_node)
        except (ValueError, SyntaxError):
            return False, f"参数 {key_node.value} 的值必须是字面量"
        if not isinstance(value, _PARAM_TYPES):
            return False, f"参数 {key_node.value} 的值必须是数字/布尔/字符串"
        out[key_node.value] = value
    return True, out
