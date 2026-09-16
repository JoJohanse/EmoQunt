"""舆情域文案目录。

覆盖两个消费面：
- ``web/templates/sentiment_analysis.html``（``sentiment.*`` 模板键 + 内联脚本的
  ``js.sentiment.*`` 键）；
- ``web/templates/sentiment_result.html``（结果页指标标签、信号徽章、新闻统计与
  返回链接）。

zh 值逐字照抄改造前的模板。**后端数据保持中文**——新闻标题/来源、板块名、
股票名、情绪分数、分析时间戳都不翻译，只翻译界面外壳。

``js.`` 前缀条目由 web_app 注入 ``window.__I18N__``，内联脚本用
``tt('js.sentiment.xxx', '中文兜底')`` 读取。

注意：结果页的``情绪分布``饼图 PNG 由 ``src/visualization.py``（可视化 Agent）
生成并已本地化，本目录只负责其周边的 HTML（标题、alt、占位文案）。
"""

MESSAGES = {
    # ---- 舆情分析页：页头 ----
    "sentiment.updatedAt": {"zh": "数据更新时间：", "en": "Updated: "},
    # {count}：热门新闻条数
    "sentiment.hotNewsCount": {"zh": "热门新闻：{count} 条", "en": "Hot news: {count}"},
    "sentiment.refresh": {"zh": "刷新数据", "en": "Refresh Data"},

    # ---- 个股情绪分析入口表单 ----
    "sentiment.stockAnalyzeTitle": {"zh": "个股情绪分析", "en": "Single-Stock Sentiment"},
    "sentiment.stockCodeLabel": {"zh": "输入股票代码", "en": "Stock Code"},
    "sentiment.stockCodePlaceholder": {"zh": "如 000001", "en": "e.g. 000001"},
    "sentiment.stockCodeHint": {
        "zh": "查询某只股票的行业情绪得分与交易信号",
        "en": "Look up a stock's sector sentiment score and trading signal",
    },
    "sentiment.weightLabel": {"zh": "情绪权重", "en": "Sentiment Weight"},
    "sentiment.analyze": {"zh": "分析", "en": "Analyze"},

    # ---- 新闻列表 / 板块得分排行 ----
    "sentiment.hotNews": {"zh": "热门新闻", "en": "Hot News"},
    "sentiment.unknownSource": {"zh": "未知来源", "en": "Unknown source"},
    "sentiment.noHotNews": {"zh": "暂无热门新闻", "en": "No hot news yet"},
    "sentiment.sectorRanking": {"zh": "板块得分排行", "en": "Sector Score Ranking"},
    "sentiment.noSectorData": {"zh": "暂无板块得分数据", "en": "No sector score data yet"},

    # ---- 空态说明框 ----
    "sentiment.aboutTitle": {"zh": "说明", "en": "About"},
    "sentiment.aboutDesc": {
        "zh": "该页面展示当天热门新闻和各板块的舆情得分情况。",
        "en": "This page shows today's hot news and the sentiment score of each sector.",
    },
    "sentiment.aboutSourceLabel": {"zh": "数据来源：", "en": "Data source: "},
    "sentiment.aboutSourceValue": {
        "zh": "TrendRadar 实时热点舆论数据",
        "en": "TrendRadar live trending-news data",
    },
    "sentiment.aboutScoringLabel": {"zh": "板块评分说明：", "en": "Sector scoring guide: "},
    "sentiment.scorePositive": {"zh": "得分 ≥ 70：积极情绪", "en": "Score ≥ 70: positive sentiment"},
    "sentiment.scoreNeutral": {"zh": "得分 41–69：中性情绪", "en": "Score 41–69: neutral sentiment"},
    "sentiment.scoreNegative": {"zh": "得分 ≤ 40：消极情绪", "en": "Score ≤ 40: negative sentiment"},

    # ---- 舆情分析结果页：页头与结果指标 ----
    "sentiment.analysisTime": {"zh": "分析时间：", "en": "Analyzed at: "},
    "sentiment.reanalyze": {"zh": "重新分析", "en": "Analyze Again"},
    "sentiment.resultTitle": {"zh": "分析结果", "en": "Analysis Result"},
    "sentiment.stockCode": {"zh": "股票代码", "en": "Stock Code"},
    "sentiment.sector": {"zh": "所属行业", "en": "Sector"},
    "sentiment.unknown": {"zh": "未知", "en": "Unknown"},
    "sentiment.rawScore": {"zh": "原始情绪得分", "en": "Raw Sentiment Score"},
    "sentiment.adjustedScore": {"zh": "调整后得分", "en": "Adjusted Score"},

    # ---- 交易信号徽章（值来自后端 sentiment_result.signal = buy/sell/hold）----
    "sentiment.signal": {"zh": "交易信号", "en": "Trading Signal"},
    "sentiment.signal.buy": {"zh": "买入", "en": "Buy"},
    "sentiment.signal.sell": {"zh": "卖出", "en": "Sell"},
    "sentiment.signal.hold": {"zh": "持有", "en": "Hold"},

    # ---- 情绪分布图（饼图 PNG 由 src/visualization.py 生成，此处只译周边文案）----
    "sentiment.distribution": {"zh": "情绪分布", "en": "Sentiment Distribution"},
    "sentiment.chartAlt": {"zh": "情绪分布图表", "en": "Sentiment distribution chart"},
    "sentiment.chartFailed": {"zh": "图表生成失败", "en": "Chart generation failed"},

    # ---- 新闻统计侧栏 ----
    "sentiment.newsStats": {"zh": "新闻统计", "en": "News Stats"},
    "sentiment.newsAnalyzed": {"zh": "分析新闻数", "en": "News Analyzed"},
    "sentiment.positive": {"zh": "正面", "en": "Positive"},
    "sentiment.neutral": {"zh": "中性", "en": "Neutral"},
    "sentiment.negative": {"zh": "负面", "en": "Negative"},

    # ---- 最新舆情列表与返回链接 ----
    "sentiment.latestSentiment": {"zh": "最新舆情", "en": "Latest Sentiment"},
    "sentiment.noSentimentData": {"zh": "暂无舆情数据", "en": "No sentiment data yet"},
    "sentiment.backToAnalysis": {"zh": "返回分析页面", "en": "Back to Analysis"},

    # ---- 内联脚本（注入 window.__I18N__，模板侧 tt() 消费）----
    "js.sentiment.refreshing": {
        "zh": "正在刷新舆情数据...", "en": "Refreshing sentiment data...",
    },
    "js.sentiment.analyzing": {"zh": "正在分析舆情...", "en": "Analyzing sentiment..."},
}
