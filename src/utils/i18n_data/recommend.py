"""每日推荐域文案目录。

覆盖两个消费面：
- ``web/templates/daily_recommend.html``（``recommend.*`` 模板键 + 内联脚本的
  ``js.recommend.*`` 键），zh 值逐字照抄改造前的模板；
- ``src/factor/daily_recommend.py:calculate_stock_score`` 的推荐理由产出点
  （``recommend.reason.*``，经 ``vmsg(key, 中文模板)`` 翻译）——zh 下 vmsg 返回
  调用方传入的原始中文模板，因此这些条目的 zh 值与源码里的中文字面量完全一致。

推荐理由的**数据**部分（股票名/板块名）保持中文不动，只有模板生成的 ``reason``
文本随语言切换。
"""

MESSAGES = {
    # ---- 页头与刷新 ----
    # 页头标题与页面标题同文案，复用 common 的 title.dailyRecommend（模板里以
    # t('title.dailyRecommend', '每日股票推荐') 消费），此处不重复收录。
    "recommend.refresh": {"zh": "刷新推荐", "en": "Refresh Picks"},

    # ---- 推荐日期提示条 ----
    "recommend.dateLabel": {"zh": "推荐日期：", "en": "Pick date: "},

    # ---- 热门板块 TOP 3 ----
    "recommend.topSectors": {"zh": "热门板块 TOP 3", "en": "Top 3 Hot Sectors"},
    "recommend.heatLabel": {"zh": "热度：", "en": "Heat: "},

    # ---- 推荐股票列表 ----
    "recommend.stockList": {"zh": "推荐股票列表", "en": "Recommended Stocks"},
    "recommend.col.rank": {"zh": "排名", "en": "Rank"},
    "recommend.col.code": {"zh": "股票代码", "en": "Code"},
    "recommend.col.name": {"zh": "股票名称", "en": "Name"},
    "recommend.col.sector": {"zh": "所属板块", "en": "Sector"},
    "recommend.col.score": {"zh": "综合评分", "en": "Overall Score"},
    "recommend.col.reason": {"zh": "推荐理由", "en": "Reason"},

    # ---- 评分说明 ----
    "recommend.scoringTitle": {"zh": "评分说明", "en": "Scoring Guide"},
    "recommend.metric.price": {"zh": "近期涨跌幅 (30%)", "en": "Recent Price Change (30%)"},
    "recommend.metric.priceHint": {
        "zh": "基于近 5 日价格变化计算",
        "en": "Based on the last 5 days of price movement",
    },
    "recommend.metric.volume": {"zh": "成交量变化 (20%)", "en": "Volume Change (20%)"},
    "recommend.metric.volumeHint": {
        "zh": "近 5 日均量对比 30 日均量",
        "en": "5-day average volume vs the 30-day average",
    },
    "recommend.metric.sentiment": {"zh": "舆情热度 (30%)", "en": "Sentiment Heat (30%)"},
    "recommend.metric.sentimentHint": {
        "zh": "基于板块新闻舆情分析",
        "en": "Derived from sector news sentiment analysis",
    },
    "recommend.metric.technical": {"zh": "技术形态 (20%)", "en": "Technical Pattern (20%)"},
    "recommend.metric.technicalHint": {
        "zh": "基于 MA 均线走势判断",
        "en": "Judged from moving-average (MA) trend direction",
    },

    # ---- 推荐理由（src/factor/daily_recommend.py 的 vmsg 产出点）----
    "recommend.reason.priceStrong": {"zh": "价格走势强劲", "en": "Strong price momentum"},
    "recommend.reason.priceUp": {"zh": "价格趋势向好", "en": "Positive price trend"},
    "recommend.reason.volumeActive": {"zh": "成交量活跃", "en": "Active volume"},
    "recommend.reason.volumeHigh": {"zh": "成交量较大", "en": "Elevated volume"},
    "recommend.reason.sectorHot": {"zh": "板块热度高", "en": "Hot sector"},
    "recommend.reason.sectorWatch": {"zh": "板块关注度较好", "en": "Good sector attention"},
    "recommend.reason.technicalStrong": {"zh": "技术形态强势", "en": "Strong technical pattern"},
    "recommend.reason.technicalSupport": {"zh": "技术面支撑良好", "en": "Solid technical support"},
    "recommend.reason.fallback": {"zh": "综合考量推荐", "en": "Recommended on balance"},
    # reason_parts 之间的连接符：zh 全角逗号，en 西文逗号+空格
    "recommend.reason.separator": {"zh": "，", "en": ", "},

    # ---- 内联脚本（注入 window.__I18N__，模板侧 tt() 消费）----
    "js.recommend.refreshing": {"zh": "正在刷新推荐...", "en": "Refreshing picks..."},
}
