import os
from dotenv import load_dotenv
import re
from typing import List, Dict, Tuple
from datetime import datetime
import numpy as np
from sector import StockSectorMapper
# llm #
from openai import OpenAI
# 加载环境变量
load_dotenv()


class SentimentAnalyzer:
    """
    情绪分析器 - 基于关键词的情感分析
    """
    
    def __init__(self, debug: bool = False, model: str = "Qwen/Qwen3-235B-A22B-Instruct-2507", base_url: str = "https://api.siliconflow.cn/v1", api_key: str = os.environ["DASHSCOPE_API_KEY"]):
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
        self.stock_mapper = StockSectorMapper()
        
        # 初始化llm
        self.client = OpenAI(
            # 示例为阿里云，根据实际情况更改
            api_key=api_key,
            # base_url="https://dashscope.aliyuncs.com/api/v2/apps/protocols/compatible-mode/v1",
            base_url=base_url
        )
        self.model = model
        self.debug = debug
    
    def analyze_sentiment(self, text: str) -> float:
        """
        分析文本的情感倾向
        
        Args:
            text: 分析的新闻文本
            stock_code: 股票代码
            
        Returns:
            float: 该股票对于输入新闻的情绪得分，范围从 -1（极度负面）到 1（极度正面）
        """
        # 获取股票信息
        # stock_info = self.stock_mapper.get_info_by_code(stock_code)
        # stock_name = stock_info.get("name")
        # sector = stock_info.get("sector")
        prompt = f"""
        新闻文本：{text}
        行业种类：
        '装修建材','能源金属','石油行业','消费电子','电力行业','小金属','电池','工程建设',
        '燃气','银行','航运港口','家电行业','通信设备','汽车零部件','航天航空','文化传媒',
        '纺织服装','汽车整车','煤炭行业','交运设备','化学原料','化纤行业','电网设备','软件开发',
        '行业','光伏设备','医疗器械','有色金属','通信服务','多元金融','医药商业','美容护理',
        '橡胶制品','食品饮料','中药','贵金属','证券','商业百货','化肥行业','电子元件','化学制品',
        '铁路公路','医疗服务','家用轻工','水泥建材','半导体','农牧饲渔','酿酒行业','工程机械',
        '房地产开发','非金属材料','船舶制造','计算机设备','玻璃玻纤','化学制药','电源设备',
        '航空机场','钢铁行业','旅游酒店','物流行业','保险','生物制品','光学光电子','互联网服务'
        请返回一个浮点数列表，每个浮点数范围从 -1（极度负面）到 1（极度正面），列表长度总是为64。表示输入新闻对上列64个行业种类的情绪影响，
        你只需返回列表，不需要其他解释。
        """
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "你是一个专业的金融情绪分析器，你的任务是根据提供的股票以及其所属行业，分析以下新闻文本对该股票的情感倾向。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.75
        )
        # 解析llm返回的结果
        content = response.choices[0].message.content.strip()
        if self.debug:
            print(content)
        try:
            # 提取列表中的浮点数
            scores = [float(x) for x in content.strip('[]').split(',')]
            scores = [max(-1.0, min(1.0, score)) for score in scores]
            # 确保列表长度为64
            if len(scores) != 64:
                if len(scores) > 64:
                    scores = scores[:64]
                else:
                    scores.extend([0.0] * (64 - len(scores)))
        except ValueError:
            scores = [0.0] * 64
        
        return scores
        
    def analyze_news_list(self, news_list: List[Dict]) -> Tuple[List[float], Dict]:
        """
        分析新闻列表的整体情感倾向，按行业计算情感得分
        
        Args:
            news_list: 新闻数据列表，每个元素包含 'title' 和 'content' 字段
            
        Returns:
            Tuple[list[float], Dict]: 
                - list[float]: 整体各行业的平均情感得分列表（每个元素范围从 -1 到 1）
                - Dict: 详细分析结果，包含以下字段：
                    - total_news: 处理的总新闻数
                    - positive_industry_count: 正面行业数（得分>0.1）
                    - negative_industry_count: 负面行业数（得分<-0.1）
                    - neutral_industry_count: 中性行业数（得分在-0.1到0.1之间）
                    - average_score: 整体平均得分
                    - score_distribution: 情感分布比例
                        - positive: 正面行业占比
                        - negative: 负面行业占比
                        - neutral: 中性行业占比
                    - industry_details: 各行业详细分析列表，每个元素包含：
                        - industry: 行业名称
                        - score: 该行业的情感得分（-1到1之间）
                        - sentiment: 情感分类（'positive'/'negative'/'neutral'）
        """
        if not news_list:
            return [0.0] * 64, {
                'total_news': 0,
                'positive_industry_count': 0,
                'negative_industry_count': 0,
                'neutral_industry_count': 64,
                'average_score': 0.0,
                'score_distribution': {
                    'positive': 0.0,
                    'negative': 0.0,
                    'neutral': 1.0
                },
                'industry_details': []
            }
        
        industry_names = [
            '装修建材','能源金属','石油行业','消费电子','电力行业','小金属','电池','工程建设',
            '燃气','银行','航运港口','家电行业','通信设备','汽车零部件','航天航空','文化传媒',
            '纺织服装','汽车整车','煤炭行业','交运设备','化学原料','化纤行业','电网设备','软件开发',
            '行业','光伏设备','医疗器械','有色金属','通信服务','多元金融','医药商业','美容护理',
            '橡胶制品','食品饮料','中药','贵金属','证券','商业百货','化肥行业','电子元件','化学制品',
            '铁路公路','医疗服务','家用轻工','水泥建材','半导体','农牧饲渔','酿酒行业','工程机械',
            '房地产开发','非金属材料','船舶制造','计算机设备','玻璃玻纤','化学制药','电源设备',
            '航空机场','钢铁行业','旅游酒店','物流行业','保险','生物制品','光学光电子','互联网服务'
        ]
        
        total_scores = [0.0] * 64
        total_news = len(news_list)
        for news in news_list:
            text = news.get('title', '') + ' ' + news.get('content', '')
            scores = self.analyze_sentiment(text)
            for i in range(64):
                total_scores[i] += scores[i]
            if self.debug:
                print(scores)
                break
        avg_scores = [score / total_news for score in total_scores]
        
        positive_count = sum(1 for score in avg_scores if score > 0.1)
        negative_count = sum(1 for score in avg_scores if score < -0.1)
        neutral_count = 64 - positive_count - negative_count
        
        average_score = sum(avg_scores) / 64
        
        industry_details = []
        for i, score in enumerate(avg_scores):
            if score > 0.1:
                sentiment = 'positive'
            elif score < -0.1:
                sentiment = 'negative'
            else:
                sentiment = 'neutral'
            
            industry_details.append({
                'industry': industry_names[i],
                'score': score,
                'sentiment': sentiment
            })
        
        analysis_result = {
            'total_news': total_news,
            'positive_industry_count': positive_count,
            'negative_industry_count': negative_count,
            'neutral_industry_count': neutral_count,
            'average_score': average_score,
            'score_distribution': {
                'positive': positive_count / 64,
                'negative': negative_count / 64,
                'neutral': neutral_count / 64
            },
            'industry_details': industry_details
        }
        
        return avg_scores, analysis_result
    

def calculate_sentiment_factor(news_list: List[Dict]) -> Dict:
    """
    计算情绪因子
    
    Args:
        news_list: 新闻数据列表
        
    Returns:
        Dict: 情绪因子结果
    """
    analyzer = SentimentAnalyzer()
    sentiment_scores, analysis_result = analyzer.analyze_news_list(news_list)
    
    # 使用整体平均得分生成交易信号
    average_score = analysis_result['average_score']
    
    # 生成情绪因子
    sentiment_factor = {
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'sentiment_scores': sentiment_scores,
        'average_score': average_score,
        'analysis_result': analysis_result,
        'signal': generate_trading_signal(average_score)
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