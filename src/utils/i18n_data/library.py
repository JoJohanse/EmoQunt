"""策略库（代码策略/运行历史）后端文案。

消费者：src/Strategy/code_validator.py、src/services/strategy_library.py、
src/services/backtest_runs.py 及 web_app.py 的 /api/v2/* 路由。
zh 为原文逐字，en 为英译。
"""

MESSAGES = {
    # ---- 代码校验（code_validator）----
    "library.sourceEmpty": {
        "zh": "策略代码不能为空",
        "en": "Strategy source code cannot be empty",
    },
    "library.sourceTooLarge": {
        "zh": "策略代码超过大小上限（100KB）",
        "en": "Strategy source exceeds the 100KB size limit",
    },
    "library.sourceSyntaxError": {
        "zh": "语法错误（第 {line} 行）: {msg}",
        "en": "Syntax error (line {line}): {msg}",
    },
    "library.sourceBannedImport": {
        "zh": "不允许导入模块 {name}（第 {line} 行）",
        "en": "Import of module \"{name}\" is not allowed (line {line})",
    },
    "library.sourceBannedImportFrom": {
        "zh": "不允许从模块 {name} 导入（第 {line} 行）",
        "en": "Import from module \"{name}\" is not allowed (line {line})",
    },
    "library.sourceWildcardImport": {
        "zh": "不允许通配导入（第 {line} 行）",
        "en": "Wildcard imports are not allowed (line {line})",
    },
    "library.sourceBannedCall": {
        "zh": "不允许调用 {name}()（第 {line} 行）",
        "en": "Call to {name}() is not allowed (line {line})",
    },
    "library.sourceBannedDunder": {
        "zh": "不允许访问双下划线属性 .{name}（第 {line} 行）",
        "en": "Access to dunder attribute .{name} is not allowed (line {line})",
    },
    "library.sourceMissingFunction": {
        "zh": "缺少必备函数 {name}（模块顶层定义）",
        "en": "Missing required function {name} (define it at module top level)",
    },
    "library.sourceBadParams": {
        "zh": "STRATEGY_PARAMS 必须是字面量字典（键为字符串，值为数字/布尔/字符串）（第 {line} 行）: {err}",
        "en": "STRATEGY_PARAMS must be a literal dict (string keys, number/bool/string values) (line {line}): {err}",
    },
    # ---- 策略库服务 ----
    "library.nameExists": {
        "zh": "策略名称已存在",
        "en": "Strategy name already exists",
    },
    "library.strategyNotFound": {
        "zh": "策略不存在",
        "en": "Strategy not found",
    },
    "library.codeStrategyNotFound": {
        "zh": "代码策略不存在（需提供有效的 strategy_id）",
        "en": "Code strategy not found (a valid strategy_id is required)",
    },
    "library.marketInvalid": {
        "zh": "market 仅支持 zh_a 或 us",
        "en": "market must be zh_a or us",
    },
    "library.paramsInvalid": {
        "zh": "params 必须是键值参数对象",
        "en": "params must be a flat key-value object",
    },
    "library.versionNotFound": {
        "zh": "版本不存在",
        "en": "Version not found",
    },
    "library.runNotFound": {
        "zh": "运行记录不存在",
        "en": "Run not found",
    },
    "library.badStrategyKind": {
        "zh": "strategy_kind 仅支持 template 或 code",
        "en": "strategy_kind must be template or code",
    },
    "library.badStatus": {
        "zh": "status 取值非法",
        "en": "Invalid status value",
    },
}
