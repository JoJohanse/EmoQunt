"""输入校验文案目录（``src/utils/validators.py`` 的 vmsg 键）。

en 模板的占位符名与 zh 模板一致，插值参数由 validators.py 传入；zh 模板即
改造前源码中的 f-string，逐字未改。日期/字段名等「本身是中文参数」的取值
另见 ``validator.dateName.*`` / ``validator.fieldName.*``。
"""

MESSAGES = {
    # ---- 股票代码 ----
    "validator.usCodeEmpty": {"zh": "美股代码不能为空", "en": "US ticker cannot be empty"},
    "validator.usCodeFormat": {
        "zh": "美股代码格式错误: {code}，应为1-6位字母/数字（如 AAPL、BRK.B），不能纯数字",
        "en": "Invalid US ticker {code}: expected 1-6 letters/digits (e.g. AAPL, BRK.B) and not all digits",
    },
    "validator.codeEmpty": {"zh": "股票代码不能为空", "en": "Stock code cannot be empty"},
    "validator.codeFormat": {
        "zh": "股票代码格式错误: {code}，应为6位数字",
        "en": "Invalid stock code {code}: expected 6 digits",
    },
    "validator.codeInvalid": {
        "zh": "股票代码 {code} 不是有效的A股代码",
        "en": "Stock code {code} is not a valid A-share code",
    },

    # ---- 日期 ----
    "validator.dateEmpty": {"zh": "{name}不能为空", "en": "{name} cannot be empty"},
    "validator.dateFormat": {
        "zh": "{name}格式错误: {date}，应为 YYYY-MM-DD",
        "en": "Invalid {name} {date}: expected YYYY-MM-DD",
    },
    "validator.dateInvalid": {"zh": "{name}无效: {date}", "en": "Invalid {name}: {date}"},
    "validator.dateTooEarly": {
        "zh": "{name}不能早于 {min}", "en": "{name} cannot be earlier than {min}",
    },
    "validator.dateTooLate": {
        "zh": "{name}不能晚于 {max}", "en": "{name} cannot be later than {max}",
    },
    "validator.dateRangeOrder": {
        "zh": "开始日期 {start} 不能晚于结束日期 {end}",
        "en": "Start date {start} cannot be later than end date {end}",
    },
    "validator.dateRangeTooLong": {
        "zh": "回测时间跨度不能超过5年",
        "en": "The backtest period cannot exceed 5 years",
    },
    "validator.dateRangeTooShort": {
        "zh": "回测时间跨度不能少于30天",
        "en": "The backtest period must cover at least 30 days",
    },

    # ---- 日期名 / 字段名（本身是中文参数，需随语言切换）----
    "validator.dateName.日期": {"zh": "日期", "en": "date"},
    "validator.dateName.开始日期": {"zh": "开始日期", "en": "start date"},
    "validator.dateName.结束日期": {"zh": "结束日期", "en": "end date"},
    "validator.fieldName.值": {"zh": "值", "en": "value"},

    # ---- 初始资金 / 佣金费率 ----
    "validator.capitalNotNumber": {
        "zh": "初始资金必须是数字", "en": "Initial capital must be a number",
    },
    "validator.capitalTooSmall": {
        "zh": "初始资金不能少于 {min} 元",
        "en": "Initial capital cannot be less than CNY {min}",
    },
    "validator.capitalTooLarge": {
        "zh": "初始资金不能超过 {max} 元",
        "en": "Initial capital cannot exceed CNY {max}",
    },
    "validator.commissionNotNumber": {
        "zh": "佣金费率必须是数字", "en": "Commission rate must be a number",
    },
    "validator.commissionNegative": {
        "zh": "佣金费率不能为负数", "en": "Commission rate cannot be negative",
    },
    "validator.commissionTooHigh": {
        "zh": "佣金费率不能超过 {max}%", "en": "Commission rate cannot exceed {max}%",
    },

    # ---- 策略名称 ----
    "validator.nameEmpty": {"zh": "策略名称不能为空", "en": "Strategy name cannot be empty"},
    "validator.nameTooShort": {
        "zh": "策略名称长度不能少于2个字符",
        "en": "Strategy name must be at least 2 characters long",
    },
    "validator.nameTooLong": {
        "zh": "策略名称长度不能超过50个字符",
        "en": "Strategy name cannot exceed 50 characters",
    },
    "validator.nameBadChars": {
        "zh": "策略名称只能包含中文、英文、数字、下划线和连字符",
        "en": "Strategy name may only contain letters, digits, Chinese characters, underscores, and hyphens",
    },

    # ---- API 密钥 ----
    "validator.apiKeyEmpty": {"zh": "API密钥不能为空", "en": "API key cannot be empty"},
    "validator.apiKeyFormat": {"zh": "API密钥格式错误", "en": "Invalid API key format"},

    # ---- 通用数值 ----
    "validator.positiveInt": {
        "zh": "{name}必须是正整数", "en": "{name} must be a positive integer",
    },    "validator.intRequired": {"zh": "{name}必须是整数", "en": "{name} must be an integer"},
    "validator.floatRange": {
        "zh": "{name}必须在 {min} 和 {max} 之间",
        "en": "{name} must be between {min} and {max}",
    },
    "validator.numberRequired": {"zh": "{name}必须是数字", "en": "{name} must be a number"},

    # ---- 策略对比参数（src/services/backtest.py 的本地校验）----
    "validator.compareNamesEmpty": {
        "zh": "strategy_names 必须是非空数组",
        "en": "strategy_names must be a non-empty array",
    },
}
