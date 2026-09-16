"""
agent 工具文案目录

src/agent/tools.py 的 @tool 在请求上下文里经 vmsg() 发射错误/提示文案；
zh 模板必须与改造前的字符串逐字一致（含标点与空格），en 为自然英文。
动态部分（异常文本、股票代码）走 {param} 插值。
"""

MESSAGES = {
    # get_stock_quote
    "agentTool.noQuoteData": {
        "zh": "无法获取 {code} 的行情数据",
        "en": "Unable to fetch quote data for {code}",
    },
    "agentTool.quoteFailed": {
        "zh": "行情查询失败: {err}",
        "en": "Quote lookup failed: {err}",
    },
    # get_index_quote
    "agentTool.noIndexData": {
        "zh": "无法获取指数 {code} 的数据",
        "en": "Unable to fetch data for index {code}",
    },
    "agentTool.indexFailed": {
        "zh": "指数查询失败: {err}",
        "en": "Index lookup failed: {err}",
    },
    # run_backtest
    "agentTool.backtestFailed": {
        "zh": "回测失败: {err}",
        "en": "Backtest failed: {err}",
    },
    # get_sentiment
    "agentTool.noSentimentData": {
        "zh": "暂无舆情数据（可能需要联网抓取新闻）",
        "en": "No sentiment data yet (news fetching may require network access)",
    },
    "agentTool.sentimentFailed": {
        "zh": "舆情查询失败: {err}",
        "en": "Sentiment lookup failed: {err}",
    },
    # get_stock_signal
    "agentTool.noSector": {
        "zh": "无法定位 {code} 的行业（可能非沪深300成分股）",
        "en": "Cannot determine the sector of {code} (it may not be a CSI 300 constituent)",
    },
    "agentTool.noSnapshots": {
        "zh": "无历史情绪快照",
        "en": "No historical sentiment snapshots",
    },
    "agentTool.noSectorSnapshot": {
        "zh": "快照中无该行业数据",
        "en": "No data for this sector in the snapshots",
    },
    "agentTool.signalFailed": {
        "zh": "个股信号查询失败: {err}",
        "en": "Stock signal lookup failed: {err}",
    },
    # get_daily_recommendations
    "agentTool.recommendFailed": {
        "zh": "推荐查询失败: {err}",
        "en": "Recommendation lookup failed: {err}",
    },
    # list_strategies
    "agentTool.strategiesFailed": {
        "zh": "策略列表查询失败: {err}",
        "en": "Strategy list lookup failed: {err}",
    },
}
