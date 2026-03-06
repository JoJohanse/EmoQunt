import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 直接导入sentiment模块
from src.factor import sentiment

print('模块导入成功')

# 测试 SentimentAnalyzer
analyzer = sentiment.SentimentAnalyzer()

# 测试 analyze_sentiment (单条新闻)
print("\n测试 analyze_sentiment:")
test_text = "今日A股市场大涨，银行股表现强劲，利好消息频传"
scores = analyzer.analyze_sentiment(test_text)
print(f"返回类型: {type(scores)}")
print(f"返回长度: {len(scores)}")
print(f"前5个得分: {scores[:5]}")
print(f"平均得分: {sum(scores)/len(scores):.4f}")

# 测试空列表
print("\n测试 analyze_news_list (空列表):")
avg_score, result = analyzer.analyze_news_list([])
print(f"平均得分: {avg_score}")
print(f"分析结果: {result}")

# 测试有新闻的情况
print("\n测试 analyze_news_list (有新闻):")
test_news_list = [
    {'title': '银行股大涨', 'content': '银行板块今日表现强劲，多家银行涨停'},
    {'title': '科技股下跌', 'content': '科技股今日走弱，半导体板块跌幅较大'},
    {'title': '消费股回暖', 'content': '消费板块今日有所回暖，食品饮料表现不错'}
]
avg_score, result = analyzer.analyze_news_list(test_news_list)
print(f"平均得分: {avg_score:.4f}")
print(f"处理新闻数: {result['total_news']}")
print(f"正性行业数: {result['positive_industry_count']}")
print(f"负性行业数: {result['negative_industry_count']}")
print(f"中性行业数: {result['neutral_industry_count']}")
print(f"情感分布: {result['score_distribution']}")
print(f"前5个行业详情:")
for i, detail in enumerate(result['industry_details'][:5]):
    print(f"  {detail['industry']}: 得分={detail['score']:.4f}, 情感={detail['sentiment']}")

print("\n测试完成！")
