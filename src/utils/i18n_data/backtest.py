"""回测域文案目录：回测配置页（backtest_form.html）与回测结果页（backtest_result.html）。

「指标键标签」一节（templates 侧消费方式：

    {{ t('metric.' ~ k, k) }}   # k 为 performance_data/metrics 的中文键

``metric.*`` 的 key 段就是 ``backtest_manager._format_metrics_*`` 产出的中文指标名
（键名本身不动，SPA/types.ts 与 localStorage 存档依赖它）；未收录的键会由
``t(key, default)`` 的 default 兜底回中文原键，不会出现空标签。
其余键为表单标签/提示/按钮（``backtestForm.*``）、结果页分区标题（``backtestResult.*``）、
内联脚本文案（``js.backtest.*``）。zh 值必须等于改造前模板的现有中文文案。

**后端数据保持中文原样、不收录进目录**：``strategy_name``、``stock_code``、指标值
（``performance_data`` 的 value）、图表 PNG 本身（由可视化层按语言另出）。

``js.`` 前缀条目由 web_app 注入 ``window.__I18N__``，内联脚本用
``tt('js.backtest.xxx', '中文兜底')`` 读取（tt() 无参数支持，含占位符时用
``.replace('{name}', x)``，本文件暂无此类条目）。
"""

MESSAGES = {
    # ---- 指标键标签（backtest_result.html / SPA 指标卡片）----
    "metric.总收益率": {"zh": "总收益率", "en": "Total Return"},
    "metric.年化收益率": {"zh": "年化收益率", "en": "Annualized Return"},
    "metric.年化波动率": {"zh": "年化波动率", "en": "Annualized Volatility"},
    "metric.夏普比率": {"zh": "夏普比率", "en": "Sharpe Ratio"},
    "metric.最大回撤": {"zh": "最大回撤", "en": "Max Drawdown"},
    "metric.最大回撤开始时间": {"zh": "最大回撤开始时间", "en": "Drawdown Start"},
    "metric.最大回撤结束时间": {"zh": "最大回撤结束时间", "en": "Drawdown End"},
    "metric.卡玛比率": {"zh": "卡玛比率", "en": "Calmar Ratio"},
    "metric.胜率": {"zh": "胜率", "en": "Win Rate"},
    "metric.盈亏比": {"zh": "盈亏比", "en": "Profit/Loss Ratio"},
    "metric.信息比率": {"zh": "信息比率", "en": "Information Ratio"},
    "metric.下行标准差": {"zh": "下行标准差", "en": "Downside Deviation"},
    "metric.交易次数": {"zh": "交易次数", "en": "# Trades"},
    "metric.盈利交易数": {"zh": "盈利交易数", "en": "Winning Trades"},
    "metric.亏损交易数": {"zh": "亏损交易数", "en": "Losing Trades"},
    "metric.平均盈利": {"zh": "平均盈利", "en": "Avg Profit"},
    "metric.平均亏损": {"zh": "平均亏损", "en": "Avg Loss"},

    # ---- 回测配置页（backtest_form.html）----
    # 注意：键名后缀 ``Zh`` / ``Us`` 指**市场**（zh_a / us，A 股 / 美股），不是语言；
    # HTML 静态文案只有 A 股默认值，美股市值由内联脚本的 js.backtest.*Us 键替换。
    "backtestForm.heading": {"zh": "策略回测配置", "en": "Backtest Configuration"},
    "backtestForm.subtitle": {
        "zh": "选择市场、策略与标的，运行回测查看含 Alpha/Beta、最大回撤的详细绩效",
        "en": "Pick a market, strategy, and symbol, then run a backtest for a detailed performance report with Alpha/Beta and max drawdown",
    },
    "backtestForm.paramsTitle": {"zh": "回测参数", "en": "Backtest Parameters"},
    "backtestForm.market": {"zh": "市场", "en": "Market"},
    "backtestForm.marketZhA": {"zh": "A 股", "en": "A-shares"},
    "backtestForm.marketUs": {"zh": "美股", "en": "US Stocks"},
    "backtestForm.strategy": {"zh": "选择策略", "en": "Select Strategy"},
    "backtestForm.strategyPlaceholder": {"zh": "-- 请选择策略 --", "en": "-- Select a strategy --"},
    "backtestForm.stockCode": {"zh": "股票代码", "en": "Stock Code"},
    "backtestForm.stockCodePlaceholder": {"zh": "如 000001", "en": "e.g. 000001"},
    "backtestForm.stockHintZh": {
        "zh": "不带前缀的 6 位 A 股代码",
        "en": "6-digit A-share code without prefix",
    },
    "backtestForm.capitalZh": {"zh": "初始资金（元）", "en": "Initial Capital (CNY)"},
    "backtestForm.startDate": {"zh": "开始日期", "en": "Start Date"},
    "backtestForm.endDate": {"zh": "结束日期", "en": "End Date"},
    "backtestForm.commissionRate": {"zh": "佣金费率（双边）", "en": "Commission Rate (both sides)"},
    "backtestForm.commissionHintZh": {
        "zh": "A 股已自动叠加印花税（卖出 0.05%）与过户费（双边 0.001%）",
        "en": "A-share costs already include stamp duty (0.05% on sells) and transfer fee (0.001% both sides)",
    },
    "backtestForm.backHome": {"zh": "返回首页", "en": "Back to Home"},
    "backtestForm.run": {"zh": "运行回测", "en": "Run Backtest"},
    "backtestForm.instructions": {"zh": "使用说明", "en": "How to Use"},
    "backtestForm.howtoMarket": {"zh": "选择市场（A股 / 美股）", "en": "Choose a market (A-shares / US stocks)"},
    "backtestForm.howtoStrategy": {"zh": "选择已创建的策略", "en": "Choose an existing strategy"},
    "backtestForm.howtoCode": {
        "zh": "输入股票代码（A股如 000001，美股如 AAPL）",
        "en": "Enter a stock code (A-shares: 000001; US: AAPL)",
    },
    "backtestForm.howtoRun": {
        "zh": "运行后查看绩效指标与图表",
        "en": "Review performance metrics and charts after the run",
    },
    "backtestForm.benchmarkHint": {
        "zh": "A 股基准为沪深300；美股基准为标普500。美股仅佣金，无印花税/过户费。",
        "en": "The A-share benchmark is the CSI 300; the US benchmark is the S&P 500. US stocks incur commission only, with no stamp duty or transfer fee.",
    },

    # ---- 回测结果页（backtest_result.html）----
    # 标题形如「回测结果 · {{ strategy_name }}」，策略名为后端数据保持原样
    "backtestResult.heading": {"zh": "回测结果", "en": "Backtest Result"},
    "backtestResult.rerun": {"zh": "重新回测", "en": "Run Again"},
    "backtestResult.metricsTitle": {"zh": "绩效指标", "en": "Performance Metrics"},
    "backtestResult.equityTitle": {"zh": "累计收益曲线", "en": "Cumulative Return Curve"},
    "backtestResult.equityAlt": {"zh": "收益曲线", "en": "Equity curve"},
    "backtestResult.equityMissing": {
        "zh": "收益曲线图表未生成",
        "en": "The equity curve chart was not generated",
    },
    "backtestResult.drawdownTitle": {"zh": "最大回撤曲线", "en": "Max Drawdown Curve"},
    "backtestResult.drawdownAlt": {"zh": "回撤曲线", "en": "Drawdown curve"},
    "backtestResult.drawdownMissing": {
        "zh": "回撤曲线图表未生成",
        "en": "The drawdown chart was not generated",
    },
    "backtestResult.dashboardTitle": {"zh": "绩效仪表板", "en": "Performance Dashboard"},
    "backtestResult.dashboardAlt": {"zh": "绩效仪表板", "en": "Performance dashboard"},
    "backtestResult.dashboardMissing": {
        "zh": "绩效仪表板未生成",
        "en": "The performance dashboard was not generated",
    },

    # ---- 回测配置页内联脚本文案（js. 前缀，供 tt() 读取）----
    "js.backtest.codePlaceholderZh": {"zh": "如 000001", "en": "e.g. 000001"},
    "js.backtest.stockHintZh": {
        "zh": "不带前缀的 6 位 A 股代码",
        "en": "6-digit A-share code without prefix",
    },
    "js.backtest.capitalZh": {"zh": "初始资金（元）", "en": "Initial Capital (CNY)"},
    "js.backtest.commissionHintZh": {
        "zh": "A 股已自动叠加印花税（卖出 0.05%）与过户费（双边 0.001%）",
        "en": "A-share costs already include stamp duty (0.05% on sells) and transfer fee (0.001% both sides)",
    },
    "js.backtest.codePlaceholderUs": {"zh": "如 AAPL", "en": "e.g. AAPL"},
    "js.backtest.stockHintUs": {
        "zh": "美股字母代码，如 AAPL、MSFT、BRK.B",
        "en": "US ticker symbols, e.g. AAPL, MSFT, BRK.B",
    },
    "js.backtest.capitalUs": {"zh": "初始资金（美元）", "en": "Initial Capital (USD)"},
    "js.backtest.commissionHintUs": {
        "zh": "美股仅佣金（双边），无印花税/过户费",
        "en": "US stocks charge commission only (both sides); no stamp duty or transfer fee",
    },
    "js.backtest.running": {"zh": "正在运行回测，请稍候...", "en": "Running backtest, please wait..."},
}
