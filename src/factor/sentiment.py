import os
import re
from typing import List, Dict, Tuple
from datetime import datetime
import numpy as np
import json


class SentimentAnalyzer:
    """
    情绪分析器 - 基于关键词的情感分析
    """
    
    def __init__(self):
        """
        初始化情绪分析器
        """
        # 正面关键词及其权重
        self.positive_words = {
            '上涨': 0.8,
            '涨停': 1.0,
            '利好': 0.9,
            '增长': 0.7,
            '上升': 0.6,
            '突破': 0.8,
            '创新高': 0.9,
            '强势': 0.7,
            '超预期': 0.8,
            '好转': 0.6,
            '回暖': 0.7,
            '复苏': 0.8,
            '盈利': 0.7,
            '增长': 0.6,
            '机会': 0.5,
            '看好': 0.8,
            '买入': 0.9,
            '持有': 0.4,
            '推荐': 0.8
        }
        
        # 负面关键词及其权重
        self.negative_words = {
            '下跌': 0.8,
            '跌停': 1.0,
            '利空': 0.9,
            '下降': 0.6,
            '下跌': 0.8,
            '跌破': 0.7,
            '创新低': 0.9,
            '弱势': 0.7,
            '低于预期': 0.8,
            '恶化': 0.6,
            '降温': 0.7,
            '衰退': 0.8,
            '亏损': 0.7,
            '减少': 0.6,
            '风险': 0.5,
            '看空': 0.8,
            '卖出': 0.9,
            '减持': 0.7,
            '警告': 0.8
        }
    
    def analyze_sentiment(self, text: str) -> float:
        """
        分析文本的情感倾向
        
        Args:
            text: 要分析的文本
            
        Returns:
            float: 情绪得分，范围从 -1（极度负面）到 1（极度正面）
        """
        if not text:
            return 0.0
        
        # 计算正面得分
        positive_score = 0.0
        for word, weight in self.positive_words.items():
            if word in text:
                positive_score += weight
        
        # 计算负面得分
        negative_score = 0.0
        for word, weight in self.negative_words.items():
            if word in text:
                negative_score += weight
        
        # 计算总得分
        total_score = positive_score - negative_score
        
        # 归一化到 -1 到 1 之间
        max_possible = max(sum(self.positive_words.values()), sum(self.negative_words.values()))
        if max_possible > 0:
            normalized_score = total_score / max_possible
            # 确保在 -1 到 1 之间
            return max(-1.0, min(1.0, normalized_score))
        
        return 0.0
    
    def analyze_news_list(self, news_list: List[Dict]) -> Tuple[float, Dict]:
        """
        分析新闻列表的整体情感倾向
        
        Args:
            news_list: 新闻数据列表，每个元素包含 'title' 和 'content' 字段
            
        Returns:
            Tuple[float, Dict]: (整体情绪得分, 详细分析结果)
        """
        if not news_list:
            return 0.0, {'total_news': 0, 'positive_count': 0, 'negative_count': 0, 'neutral_count': 0}
        
        scores = []
        positive_count = 0
        negative_count = 0
        neutral_count = 0
        
        for news in news_list:
            # 组合标题和内容进行分析
            text = news.get('title', '') + ' ' + news.get('content', '')
            score = self.analyze_sentiment(text)
            scores.append(score)
            
            # 统计情绪分布
            if score > 0.1:
                positive_count += 1
            elif score < -0.1:
                negative_count += 1
            else:
                neutral_count += 1
        
        # 计算平均情绪得分
        if scores:
            average_score = sum(scores) / len(scores)
        else:
            average_score = 0.0
        
        # 确保在 -1 到 1 之间
        average_score = max(-1.0, min(1.0, average_score))
        
        analysis_result = {
            'total_news': len(news_list),
            'positive_count': positive_count,
            'negative_count': negative_count,
            'neutral_count': neutral_count,
            'average_score': average_score,
            'score_distribution': {
                'positive': positive_count / len(news_list) if news_list else 0,
                'negative': negative_count / len(news_list) if news_list else 0,
                'neutral': neutral_count / len(news_list) if news_list else 0
            }
        }
        
        return average_score, analysis_result


def calculate_sentiment_factor(news_list: List[Dict]) -> Dict:
    """
    计算情绪因子
    
    Args:
        news_list: 新闻数据列表
        
    Returns:
        Dict: 情绪因子结果
    """
    analyzer = SentimentAnalyzer()
    sentiment_score, analysis_result = analyzer.analyze_news_list(news_list)
    
    # 生成情绪因子
    sentiment_factor = {
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'sentiment_score': sentiment_score,
        'analysis_result': analysis_result,
        'signal': generate_trading_signal(sentiment_score)
    }
    
    return sentiment_factor


def generate_trading_signal(sentiment_score: float) -> str:
    """
    基于情绪得分生成交易信号
    
    Args:
        sentiment_score: 情绪得分
        
    Returns:
        str: 交易信号 ('buy', 'sell', 'hold')
    """
    if sentiment_score > 0.3:
        return 'buy'
    elif sentiment_score < -0.3:
        return 'sell'
    else:
        return 'hold'

# 18类国民经济分类标准
NATIONAL_ECONOMY_CATEGORIES = [
    '农、林、牧、渔业','采矿业','制造业','电力、热力、燃气及水生产和供应业','建筑业','批发和零售业','交通运输、仓储和邮政业','住宿和餐饮业','信息传输、软件和信息技术服务业',
    '金融业','房地产业','租赁和商务服务业','科学研究和技术服务业','水利、环境和公共设施管理业','居民服务、修理和其他服务业','教育','卫生和社会工作','文化、体育和娱乐业'
]

# Z-score标准化
def z_score_normalize(values):
    if len(values) == 0:
        return []
    
    mean_val = np.mean(values)
    std_val = np.std(values)
    
    if std_val == 0:
        return [0.0] * len(values)
    
    return [(x - mean_val) / std_val for x in values]

# 新闻已按时间顺序排列，将同一天的新闻分组，按天分析当天各行业的舆情
# 按行业分析舆情倾向
def analyze_industry_sentiment(news_list):
    sentiment_list = {}
    '''
    新闻数据示例：
    {"id": "BkKujE_xK7ICqmropAK1", "content": "XXXXX", "title": "XXXX", "language": "zh", "date": "2022-08-18", "num_words": 1083, "max_word_length": 12, "frac_chars_non_alphanumeric": 0.10963793982661907, "frac_chars_dupe_5grams": 0.004410143329658167, "frac_chars_dupe_9grams": 0.0, "keywords": ["券商", "行情", "利率", "贸易", "投资", "消费", "合资", "上市"], "sentiment": "positive", "opinion": {"industry": "制造业", "sentiment": {"label": "positive", "score": {"positive": 0.7087072134017944, "negative": 0.29129278659820557}}}}
    '''
    for news in news_list:
        try:
            if 'opinion' not in news:
                continue
            # 划分日期，若不存在以该日期为键创建空字典以存放分析结果
            date_str = news['date']
            if date_str not in sentiment_list:
                sentiment_list[date_str] = {}
            industry = news['opinion']['industry']
            if industry not in sentiment_list[date_str]:
                sentiment_list[date_str][industry] = {
                    'avg_positive': 0,
                    'avg_negative': 0,
                    'news_count': 0
                }
            # 更新平均分数
            total_pos = sentiment_list[date_str][industry]['avg_positive'] * sentiment_list[date_str][industry]['news_count'] + news['opinion']['sentiment']['score']['positive']
            total_neg = sentiment_list[date_str][industry]['avg_negative'] * sentiment_list[date_str][industry]['news_count'] + news['opinion']['sentiment']['score']['negative']
            sentiment_list[date_str][industry]['news_count'] += 1
            sentiment_list[date_str][industry]['avg_positive'] = total_pos / sentiment_list[date_str][industry]['news_count']
            sentiment_list[date_str][industry]['avg_negative'] = total_neg / sentiment_list[date_str][industry]['news_count']
        except Exception as e:
            print(f"处理{news['id']}新闻时出错: {e}")
            continue

    return sentiment_list