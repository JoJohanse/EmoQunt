import sentiment,trendradar
import os

analyzer = sentiment.SentimentAnalyzer()
news_list = trendradar.get_latest_trendradar_data()
if news_list:
    # 分析新闻列表
    sentiment_scores, analysis_result = analyzer.analyze_news_list(news_list)
    print(f"各行业情感得分: {sentiment_scores}")
    print(f"分析结果: {analysis_result}")
else:
    print("没有获取到新闻数据")
