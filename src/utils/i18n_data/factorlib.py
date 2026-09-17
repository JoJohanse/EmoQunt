"""因子库（factorlib）后端文案。

消费者：src/services/factor_library.py 及 web_app.py 的 /api/v2/factors/* 路由。
zh 为原文逐字，en 为英译。
"""

MESSAGES = {
    "factorlib.notFound": {
        "zh": "因子不存在",
        "en": "Factor not found",
    },
    "factorlib.versionNotFound": {
        "zh": "因子版本不存在",
        "en": "Factor version not found",
    },
    "factorlib.nameEmpty": {
        "zh": "因子名称不能为空",
        "en": "Factor name cannot be empty",
    },
    "factorlib.nameTooShort": {
        "zh": "因子名称长度不能少于 2 个字符",
        "en": "Factor name must be at least 2 characters",
    },
    "factorlib.nameTooLong": {
        "zh": "因子名称最长 {max} 个字符",
        "en": "Factor name is limited to {max} characters",
    },
    "factorlib.duplicateName": {
        "zh": "因子名称已存在: {name}",
        "en": "Factor name already exists: {name}",
    },
    "factorlib.badMarket": {
        "zh": "因子库仅支持 A 股（zh_a）",
        "en": "The factor library only supports A-shares (zh_a)",
    },
    "factorlib.sourceEmpty": {
        "zh": "因子代码不能为空",
        "en": "Factor source code cannot be empty",
    },
    "factorlib.sourceTooLarge": {
        "zh": "因子代码超过大小上限（100KB）",
        "en": "Factor source exceeds the 100KB size limit",
    },
    "factorlib.compileFailed": {
        "zh": "因子代码执行失败: {err}",
        "en": "Factor code failed to execute: {err}",
    },
    "factorlib.computeFailed": {
        "zh": "因子计算失败: {err}",
        "en": "Factor computation failed: {err}",
    },
    "factorlib.badReturnType": {
        "zh": "compute 必须返回 pandas Series（实际返回 {t}）",
        "en": "compute must return a pandas Series (got {t})",
    },
    "factorlib.emptyResult": {
        "zh": "compute 返回的因子值全为空（请检查窗口长度或 dropna）",
        "en": "compute returned all-empty factor values (check the lookback window or dropna)",
    },
    "factorlib.indexMismatch": {
        "zh": "返回 Series 的索引必须是输入 DataFrame 日期索引的子集",
        "en": "The returned Series index must be a subset of the input DataFrame's date index",
    },
    "factorlib.analyzeFailed": {
        "zh": "因子分析失败，请稍后重试",
        "en": "Factor analysis failed, please try again later",
    },
}
