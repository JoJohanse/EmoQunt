"""错误文案目录（``tr_error`` 专用）：HTTP 边界的中文原文 → 英文译文。

给两类「无法改成 vmsg（消息在服务层早已拼好、且路由层还要对中文子串做状态码
判定）」的文案兜底：
    - ``ERROR_MESSAGES``：精确匹配的整句；
    - ``ERROR_TEMPLATES``：带 ``{param}`` 占位符的句子（正则化后匹配），
      例如 ``策略 {name} 不存在或不是用户策略``。

维护约定：新增条目时 zh 原文必须与源码中的字符串逐字一致（含全角标点与空格），
否则 ``tr_error`` 不命中、英文界面会漏译。zh 语言下本模块完全不生效。
"""

# 精确匹配：中文原文 → 英文
ERROR_MESSAGES = {
    # ---- web_app.py 路由层字面量 ----
    "获取策略列表失败": "Failed to load the strategy list",
    "策略不存在": "Strategy not found",
    "获取策略详情失败": "Failed to load strategy details",
    "获取策略模板失败": "Failed to load strategy templates",
    "创建策略失败": "Failed to create the strategy",
    "更新策略失败": "Failed to update the strategy",
    "删除策略失败": "Failed to delete the strategy",
    "回测失败，请稍后重试": "Backtest failed. Please try again later.",
    "策略对比失败，请稍后重试": "Strategy comparison failed. Please try again later.",
    "factor_type 必须是 momentum/rsi/volatility/volume_ratio":
        "factor_type must be one of momentum / rsi / volatility / volume_ratio",
    "因子分析失败，请稍后重试": "Factor analysis failed. Please try again later.",
    "获取K线数据失败，请稍后重试": "Failed to load K-line data. Please try again later.",
    "获取舆情数据失败，请稍后重试": "Failed to load sentiment data. Please try again later.",
    "获取舆情数据失败": "Failed to load sentiment data",
    "获取板块行情失败，请稍后重试": "Failed to load sector quotes. Please try again later.",
    "获取市场宽度失败，请稍后重试": "Failed to load market breadth. Please try again later.",
    "获取数据源健康失败": "Failed to load data source health",
    "消息不能为空": "Messages cannot be empty",
    "AI 助手服务异常，请稍后重试": "The AI assistant is temporarily unavailable. Please try again later.",
    "对话失败，请稍后重试": "The conversation failed. Please try again later.",

    # ---- src/services/strategies.py CRUD ----
    "策略名称已存在": "A strategy with this name already exists",
    "自定义参数不能为空": "Custom parameters cannot be empty",
    "保存策略失败": "Failed to save the strategy",
}

# 参数化匹配：中文模板（{param} 占位）→ 英文模板（同名占位）
ERROR_TEMPLATES = {
    "模板 {template} 不存在": "Template {template} does not exist",
    "策略 {name} 不存在或不是用户策略": "Strategy {name} does not exist or is not a user strategy",
    "删除策略 {name} 失败": "Failed to delete strategy {name}",
    "股票 {stock_code} 不是沪深300成分股，暂时只支持沪深300成分股的舆情分析":
        "Stock {stock_code} is not a CSI 300 constituent; sentiment analysis currently supports "
        "CSI 300 constituents only",
}
