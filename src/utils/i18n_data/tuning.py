"""参数调优（tuning）后端文案。

消费者：src/services/tuning.py 及 web_app.py 的 /api/v2/tuning/* 路由。
zh 为原文逐字，en 为英译。
"""

MESSAGES = {
    "tuning.taskNotFound": {
        "zh": "调优任务不存在",
        "en": "Tuning task not found",
    },
    "tuning.comboNotFound": {
        "zh": "参数组合不存在",
        "en": "Parameter combination not found",
    },
    "tuning.badStrategyKind": {
        "zh": "strategy_kind 仅支持 template 或 code",
        "en": "strategy_kind must be template or code",
    },
    "tuning.codeStrategyNotFound": {
        "zh": "代码策略不存在（需提供有效的 strategy_id）",
        "en": "Code strategy not found (a valid strategy_id is required)",
    },
    "tuning.templateStrategyNotFound": {
        "zh": "模板策略不存在: {name}",
        "en": "Template strategy not found: {name}",
    },
    "tuning.badParamGrid": {
        "zh": "参数网格必须是非空对象（{参数名: [取值...]}）",
        "en": "param_grid must be a non-empty object ({param: [values...]})",
    },
    "tuning.gridParamUnknown": {
        "zh": "参数 {name} 不在该策略的参数中",
        "en": "Parameter \"{name}\" is not part of this strategy",
    },
    "tuning.gridValuesEmpty": {
        "zh": "参数 {name} 的取值列表为空",
        "en": "Value list for parameter \"{name}\" is empty",
    },
    "tuning.gridValuesTooMany": {
        "zh": "参数 {name} 的取值最多 {max} 个",
        "en": "At most {max} values per parameter (\"{name}\" given)",
    },
    "tuning.gridValuesType": {
        "zh": "参数 {name} 的取值必须是数字或布尔值",
        "en": "Values for parameter \"{name}\" must be numbers or booleans",
    },
    "tuning.gridTooLarge": {
        "zh": "参数组合数 {count} 超过上限 {max}（加基准共 {total} 组）",
        "en": "Parameter combination count {count} exceeds the limit of {max} ({total} including baseline)",
    },
    "tuning.badTargetMetric": {
        "zh": "目标指标仅支持: {names}",
        "en": "Target metric must be one of: {names}",
    },
    "tuning.taskNotFinished": {
        "zh": "调优任务尚未结束，无法应用参数",
        "en": "Tuning task is still running; parameters cannot be applied yet",
    },
    "tuning.comboNotSucceeded": {
        "zh": "该参数组合未成功完成，无法应用",
        "en": "This combination did not finish successfully; cannot apply",
    },
    "tuning.applyFailed": {
        "zh": "应用参数失败: {reason}",
        "en": "Failed to apply parameters: {reason}",
    },
}
