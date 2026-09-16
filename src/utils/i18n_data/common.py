"""公共文案目录：导航栏、品牌/页脚、页面标题、通用提示与错误页。

i18n 基础设施自带的文案（base/error/index 三个模板 + web_app.py 路由标题 +
``_handle_error`` 的操作名）都在这里；其余域的文案由对应模板 Agent 追加到各自
的目录模块。

约定：
- zh 值必须与改造前的界面文案逐字一致（zh 语言下界面零变化）；
- 含受信任行内 HTML 的条目在注释中标注，模板需以 ``| safe`` 渲染；
- ``js.`` 前缀的条目会被 web_app 注入 ``window.__I18N__``，供内联脚本用 tt() 读取。
"""

MESSAGES = {
    # ---- 导航栏 ----
    "nav.home": {"zh": "首页", "en": "Home"},
    "nav.backtest": {"zh": "策略回测", "en": "Backtest"},
    "nav.strategies": {"zh": "策略列表", "en": "Strategies"},
    "nav.sentiment": {"zh": "舆情分析", "en": "Sentiment"},
    "nav.recommend": {"zh": "每日推荐", "en": "Daily Picks"},
    "nav.setup": {"zh": "安装引导", "en": "Setup"},
    "nav.switchLang": {"zh": "切换语言", "en": "Switch language"},

    # ---- 品牌与页脚 ----
    "brand.suffix": {"zh": "量化系统", "en": "Quant System"},
    "brand.title": {"zh": "EmoQunt 量化系统", "en": "EmoQunt Quant System"},
    "footer.tagline": {"zh": "让量化投资更简单", "en": "Making quantitative investing simpler"},

    # ---- 页面标题（web_app.py 路由的 title 上下文）----
    "title.home": {"zh": "量化策略回测系统", "en": "Quantitative Strategy Backtesting System"},
    "title.setup": {"zh": "安装引导", "en": "Setup Guide"},
    "title.backtest": {"zh": "策略回测", "en": "Strategy Backtest"},
    "title.backtestResult": {"zh": "回测结果", "en": "Backtest Result"},
    "title.strategies": {"zh": "策略列表", "en": "Strategy List"},
    "title.sentiment": {"zh": "舆情分析", "en": "Sentiment Analysis"},
    "title.sentimentResult": {"zh": "舆情分析结果", "en": "Sentiment Analysis Result"},
    "title.recommend": {"zh": "每日推荐", "en": "Daily Picks"},
    "title.dailyRecommend": {"zh": "每日股票推荐", "en": "Daily Stock Picks"},
    "title.error": {"zh": "错误", "en": "Error"},

    # ---- 通用提示 ----
    "common.loading": {"zh": "加载中...", "en": "Loading..."},
    # {op}：操作名（见下方 common.op.*）
    "common.opFailed": {"zh": "{op}执行失败，请稍后重试", "en": "{op} failed. Please try again later."},

    # ---- 操作名（common.opFailed 的 {op} 参数；web_app._handle_error 调用方）----
    "common.op.操作": {"zh": "操作", "en": "The operation"},
    "common.op.回测参数验证": {"zh": "回测参数验证", "en": "Backtest parameter validation"},
    "common.op.回测执行": {"zh": "回测执行", "en": "Backtest execution"},
    "common.op.策略列表加载": {"zh": "策略列表加载", "en": "Loading the strategy list"},
    "common.op.舆情分析页面加载": {"zh": "舆情分析页面加载", "en": "Loading the sentiment page"},
    "common.op.舆情分析刷新": {"zh": "舆情分析刷新", "en": "Refreshing sentiment data"},
    "common.op.每日推荐页面加载": {"zh": "每日推荐页面加载", "en": "Loading the daily picks page"},
    "common.op.每日推荐刷新": {"zh": "每日推荐刷新", "en": "Refreshing daily picks"},
    "common.op.舆情分析参数验证": {"zh": "舆情分析参数验证", "en": "Sentiment parameter validation"},
    "common.op.舆情分析执行": {"zh": "舆情分析执行", "en": "Sentiment analysis"},
    "common.op.策略创建": {"zh": "策略创建", "en": "Strategy creation"},
    "common.op.策略更新": {"zh": "策略更新", "en": "Strategy update"},
    "common.op.策略删除": {"zh": "策略删除", "en": "Strategy deletion"},
    "common.op.策略对比": {"zh": "策略对比", "en": "Strategy comparison"},
    "common.op.因子分析": {"zh": "因子分析", "en": "Factor analysis"},
    "common.op.K线数据获取": {"zh": "K线数据获取", "en": "Fetching K-line data"},

    # ---- 错误页（web/templates/error.html）----
    "error.heading": {"zh": "发生错误", "en": "Something went wrong"},
    "error.info": {"zh": "错误信息", "en": "Error message"},
    "error.backToBacktest": {"zh": "返回回测页面", "en": "Back to Backtest"},
    "error.backToHome": {"zh": "返回首页", "en": "Back to Home"},

    # ---- 首页（web/templates/index.html）----
    # 含受信任行内 HTML（<code>），模板需以 | safe 渲染
    "index.setupBanner": {
        "zh": "检测到系统尚未完成初始配置（缺少 <code>.env</code> 或 LLM API Key）。",
        "en": "Initial setup looks incomplete (missing <code>.env</code> or an LLM API key).",
    },
    "index.setupBannerAction": {"zh": "查看安装引导", "en": "View Setup Guide"},
    "index.heroTitle": {"zh": "欢迎使用 EmoQunt 量化系统", "en": "Welcome to EmoQunt Quant System"},
    "index.heroSubtitle": {
        "zh": "结合情绪因子的智能量化策略回测平台 · 让数据驱动你的投资决策",
        "en": "A sentiment-aware quantitative backtesting platform · Let data drive your investment decisions",
    },
    "index.featureBacktestTitle": {"zh": "策略回测", "en": "Strategy Backtesting"},
    "index.featureBacktestDesc": {
        "zh": "选择策略运行回测，查看含 Alpha/Beta、最大回撤的详细绩效报告",
        "en": "Run a strategy and review a full performance report with Alpha/Beta and max drawdown",
    },
    "index.featureBacktestAction": {"zh": "开始回测", "en": "Run Backtest"},
    "index.featureStrategiesTitle": {"zh": "策略管理", "en": "Strategy Management"},
    "index.featureStrategiesDesc": {
        "zh": "创建、编辑、查看所有策略及其参数配置",
        "en": "Create, edit, and inspect every strategy and its parameter configuration",
    },
    "index.featureStrategiesAction": {"zh": "查看策略", "en": "View Strategies"},
    "index.featureSentimentTitle": {"zh": "舆情分析", "en": "Sentiment Analysis"},
    "index.featureSentimentDesc": {
        "zh": "基于实时热点舆论数据生成板块情绪与个股交易信号",
        "en": "Turn live news flow into sector sentiment scores and stock-level trading signals",
    },
    "index.featureSentimentAction": {"zh": "分析舆情", "en": "Analyze Sentiment"},
    "index.featureRecommendTitle": {"zh": "每日推荐", "en": "Daily Picks"},
    "index.featureRecommendDesc": {
        "zh": "融合情绪与多因子模型，智能推荐潜力股票",
        "en": "Blend sentiment with multi-factor models to surface promising stocks",
    },
    "index.featureRecommendAction": {"zh": "查看推荐", "en": "View Picks"},
    "index.systemTitle": {"zh": "系统特性", "en": "Platform Highlights"},
    "index.systemSentimentTitle": {"zh": "情绪因子策略", "en": "Sentiment Factor Strategies"},
    "index.systemSentimentDesc": {
        "zh": "将行业情绪快照接入回测信号过滤",
        "en": "Feed industry sentiment snapshots into backtest signal filtering",
    },
    "index.systemFactorTitle": {"zh": "多因子模型", "en": "Multi-Factor Models"},
    "index.systemFactorDesc": {
        "zh": "均线、情绪、基本面多维度打分",
        "en": "Score candidates across moving averages, sentiment, and fundamentals",
    },
    "index.systemCostTitle": {"zh": "真实交易成本", "en": "Realistic Trading Costs"},
    "index.systemCostDesc": {
        "zh": "A股佣金/印花税/过户费/滑点建模",
        "en": "Model A-share commission, stamp duty, transfer fees, and slippage",
    },

    # ---- Vue3 SPA 未构建提示（web_app.py /spa/{path} 的 503 响应体）----
    # 含受信任行内 HTML（<code>），直接拼接为 HTML 响应，不经模板转义
    "spa.notBuiltTitle": {"zh": "Vue3 前端未构建", "en": "Vue3 frontend is not built"},
    "spa.notBuiltBody": {
        "zh": "请在 frontend/ 目录执行 <code>npm install &amp;&amp; npm run build</code>",
        "en": "Run <code>npm install &amp;&amp; npm run build</code> in the frontend/ directory",
    },

    # ---- 注入 window.__I18N__ 的内联脚本文案（js. 前缀）----
    "js.loading": {"zh": "加载中...", "en": "Loading..."},
}
