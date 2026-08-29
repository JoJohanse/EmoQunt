import os
import json
import re
import logging
from typing import List, Dict, Tuple, Optional
from datetime import datetime
import numpy as np

from src.utils.env import get_env, get_env_float, get_env_int
from src.utils.paths import PROJECT_ROOT, ensure_dir

logger = logging.getLogger(__name__)

from openai import OpenAI

# 导入配置加载器
from config.config_loader import get_config

# 加载情感分析配置
_config = get_config()
SENTIMENT_CONFIG = _config.load_sentiment_config()

# 从配置中获取情感词典
POSITIVE_WORDS = SENTIMENT_CONFIG.get('positive_words', {})
NEGATIVE_WORDS = SENTIMENT_CONFIG.get('negative_words', {})

# 从配置中获取阈值
THRESHOLDS = SENTIMENT_CONFIG.get('sentiment_thresholds', {})
POSITIVE_THRESHOLD = THRESHOLDS.get('positive', 0.1)
NEGATIVE_THRESHOLD = THRESHOLDS.get('negative', -0.1)
BUY_SIGNAL_THRESHOLD = THRESHOLDS.get('buy_signal', 0.3)
SELL_SIGNAL_THRESHOLD = THRESHOLDS.get('sell_signal', -0.3)

# 从配置中获取行业列表
INDUSTRIES = SENTIMENT_CONFIG.get('industries', [])

# LLM 模型配置统一从环境变量（.env）加载
DEFAULT_MODEL = get_env("LLM_MODEL", "mimo-v2.5")
DEFAULT_BASE_URL = get_env("LLM_BASE_URL", "https://token-plan-cn.xiaomimimo.com/v1")
DEFAULT_TEMPERATURE = get_env_float("LLM_TEMPERATURE", 0.75)
DEFAULT_MAX_TOKENS = get_env_int("LLM_MAX_TOKENS", 5120)
DEFAULT_TIMEOUT = get_env_int("LLM_TIMEOUT", 30)

# 从配置中获取缓存配置
CACHE_CONFIG = SENTIMENT_CONFIG.get('cache_config', {})
SENTIMENT_CACHE_TIMEOUT = CACHE_CONFIG.get('sentiment_cache_timeout', 3600)


class SentimentAnalyzer:
    """
    情绪分析器 - 基于关键词的情感分析
    """
    
    def __init__(self, debug: bool = False, model: str = None, base_url: str = None, api_key: str = None):
        """
        初始化情绪分析器
        
        :param debug: 是否开启调试模式
        :param model: LLM模型名称，默认从配置读取
        :param base_url: LLM API基础URL，默认从配置读取
        :param api_key: API密钥，默认从环境变量读取
        """
        # 使用配置中的情感词典
        self.positive_words = POSITIVE_WORDS
        self.negative_words = NEGATIVE_WORDS
        
        from src.factor.daily_recommend import StockSectorMapper
        self.stock_mapper = StockSectorMapper()
        
        # 初始化LLM配置
        self.model = model or DEFAULT_MODEL
        self.base_url = base_url or DEFAULT_BASE_URL
        self.api_key = api_key or os.environ.get("API_KEY")
        self.debug = debug
        
        # 初始化OpenAI客户端
        if self.api_key:
            self.client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url
            )
        else:
            logger.warning("API密钥未设置，情感分析功能将受限")
            self.client = None
    
    def analyze_sentiment(self, text: str) -> List[float]:
        """
        分析文本的情感倾向
        
        Args:
            text: 分析的新闻文本
            
        Returns:
            List[float]: 各行业的情感得分列表（范围从 -1 到 1）
        """
        if not self.client:
            logger.warning("LLM客户端未初始化，返回默认得分")
            return [0.0] * len(INDUSTRIES) if INDUSTRIES else [0.0] * 64
        
        # 构建行业列表字符串
        industry_list = '、'.join(INDUSTRIES) if INDUSTRIES else '装修建材、能源金属、石油行业等64个行业'
        
        prompt = f"""
        新闻文本：{text}
        行业种类：{industry_list}
        
        请返回一个浮点数列表，每个浮点数范围从 -1（极度负面）到 1（极度正面），
        列表长度总是为{len(INDUSTRIES) if INDUSTRIES else 64}。
        表示输入新闻对各行业的情绪影响，你只需返回列表，不需要其他解释。
        """
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "你是一个专业的金融情绪分析器，你的任务是根据提供的股票以及其所属行业，分析以下新闻文本对该股票的情感倾向。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=DEFAULT_TEMPERATURE,
                max_tokens=DEFAULT_MAX_TOKENS,
                timeout=DEFAULT_TIMEOUT
            )
            
            # 解析LLM返回的结果
            content = response.choices[0].message.content.strip()
            if self.debug:
                logger.debug(f"LLM响应: {content}")
            
            # 提取列表中的浮点数
            scores = self._parse_sentiment_scores(content)
            return scores
            
        except Exception as e:
            logger.error(f"LLM情感分析失败: {e}")
            return [0.0] * (len(INDUSTRIES) if INDUSTRIES else 64)
    
    def _parse_sentiment_scores(self, content: str) -> List[float]:
        """
        解析LLM返回的情感得分
        
        :param content: LLM返回的文本内容
        :return: 解析后的情感得分列表
        """
        expected_length = len(INDUSTRIES) if INDUSTRIES else 64
        
        try:
            # 提取列表中的浮点数
            scores = [float(x.strip()) for x in content.strip('[]').split(',')]
            scores = [max(-1.0, min(1.0, score)) for score in scores]  # 限制在[-1, 1]范围内
            
            # 确保列表长度正确
            if len(scores) != expected_length:
                if len(scores) > expected_length:
                    scores = scores[:expected_length]
                else:
                    scores.extend([0.0] * (expected_length - len(scores)))
                    
        except (ValueError, AttributeError) as e:
            logger.warning(f"解析情感得分失败: {e}, 使用默认值")
            scores = [0.0] * expected_length
        
        return scores
        
    def analyze_news_list(self, news_list: List[Dict]) -> Tuple[List[float], Dict]:
        """
        分析新闻列表的整体情感倾向，按行业计算情感得分
        
        Args:
            news_list: 新闻数据列表，每个元素包含 'title' 和 'content' 字段
            
        Returns:
            Tuple[List[float], Dict]: 情感得分列表和详细分析结果
        """
        if not news_list:
            return self._get_empty_analysis_result()
        
        # 合并所有新闻文本
        combined_text = self._combine_news_text(news_list)
        
        # 分析情感
        scores = self.analyze_sentiment(combined_text)
        
        # 生成分析结果
        analysis_result = self._generate_analysis_result(scores, news_list)
        
        return scores, analysis_result
    
    def _combine_news_text(self, news_list: List[Dict]) -> str:
        """
        合并新闻列表为单个文本
        
        :param news_list: 新闻列表
        :return: 合并后的文本
        """
        combined_parts = []
        for news in news_list:
            title = news.get('title', '')
            content = news.get('content', '')
            if title or content:
                combined_parts.append(f"标题：{title}\n内容：{content}")
        
        return "\n---\n".join(combined_parts)
    
    def _get_empty_analysis_result(self) -> Tuple[List[float], Dict]:
        """
        获取空的分析结果
        
        :return: 空的情感得分和分析结果
        """
        expected_length = len(INDUSTRIES) if INDUSTRIES else 64
        
        return [0.0] * expected_length, {
            'total_news': 0,
            'positive_industry_count': 0,
            'negative_industry_count': 0,
            'neutral_industry_count': expected_length,
            'average_score': 0.0,
            'score_distribution': {
                'positive': 0.0,
                'negative': 0.0,
                'neutral': 1.0
            },
            'industry_details': []
        }
    
    def _generate_analysis_result(self, scores: List[float], news_list: List[Dict]) -> Dict:
        """
        生成分析结果
        
        :param scores: 情感得分列表
        :param news_list: 新闻列表
        :return: 分析结果字典
        """
        industries = INDUSTRIES if INDUSTRIES else self._get_default_industries()
        
        # 统计正面/负面/中性行业数量
        positive_count = sum(1 for score in scores if score > POSITIVE_THRESHOLD)
        negative_count = sum(1 for score in scores if score < NEGATIVE_THRESHOLD)
        neutral_count = len(scores) - positive_count - negative_count
        
        # 计算平均分
        average_score = sum(scores) / len(scores) if scores else 0.0
        
        # 生成行业详情
        industry_details = []
        for i, score in enumerate(scores):
            if score > POSITIVE_THRESHOLD:
                sentiment = 'positive'
            elif score < NEGATIVE_THRESHOLD:
                sentiment = 'negative'
            else:
                sentiment = 'neutral'
            
            industry_name = industries[i] if i < len(industries) else f"行业{i+1}"
            industry_details.append({
                'industry': industry_name,
                'score': score,
                'sentiment': sentiment
            })
        
        return {
            'total_news': len(news_list),
            'positive_industry_count': positive_count,
            'negative_industry_count': negative_count,
            'neutral_industry_count': neutral_count,
            'average_score': average_score,
            'score_distribution': {
                'positive': positive_count / len(scores) if scores else 0.0,
                'negative': negative_count / len(scores) if scores else 0.0,
                'neutral': neutral_count / len(scores) if scores else 0.0
            },
            'industry_details': industry_details
        }
    
    def _get_default_industries(self) -> List[str]:
        """
        获取默认行业列表
        
        :return: 默认行业列表
        """
        return [
            '装修建材', '能源金属', '石油行业', '消费电子', '电力行业', '小金属', '电池', '工程建设',
            '燃气', '银行', '航运港口', '家电行业', '通信设备', '汽车零部件', '航天航空', '文化传媒',
            '纺织服装', '汽车整车', '煤炭行业', '交运设备', '化学原料', '化纤行业', '电网设备', '软件开发',
            '行业', '光伏设备', '医疗器械', '有色金属', '通信服务', '多元金融', '医药商业', '美容护理',
            '橡胶制品', '食品饮料', '中药', '贵金属', '证券', '商业百货', '化肥行业', '电子元件', '化学制品',
            '铁路公路', '医疗服务', '家用轻工', '水泥建材', '半导体', '农牧饲渔', '酿酒行业', '工程机械',
            '房地产开发', '非金属材料', '船舶制造', '计算机设备', '玻璃玻纤', '化学制药', '电源设备',
            '航空机场', '钢铁行业', '旅游酒店', '物流行业', '保险', '生物制品', '光学光电子', '互联网服务'
        ]


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
    average_score = analysis_result.get('average_score', 0.0)
    
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
    if sentiment_score > BUY_SIGNAL_THRESHOLD:
        return 'buy'
    elif sentiment_score < SELL_SIGNAL_THRESHOLD:
        return 'sell'
    else:
        return 'hold'


# Z-score标准化
def z_score_normalize(values):
    """
    Z-score标准化
    
    :param values: 数值列表
    :return: 标准化后的数值列表
    """
    if len(values) == 0:
        return []
    
    mean_val = np.mean(values)
    std_val = np.std(values)
    
    if std_val == 0:
        return [0.0] * len(values)
    
    return [(x - mean_val) / std_val for x in values]


# 舆情结果持久化
SENTIMENT_SAVE_DIR = str(PROJECT_ROOT / "nes_data" / "sentiment_results")


def _ensure_sentiment_save_dir():
    """确保舆情结果保存目录存在"""
    ensure_dir(SENTIMENT_SAVE_DIR)
    logger.info(f"确保舆情结果保存目录存在: {SENTIMENT_SAVE_DIR}")


def save_sentiment_result(data: Dict) -> str:
    """
    保存舆情分析结果
    
    :param data: 舆情分析数据
    :return: 保存的文件路径
    """
    _ensure_sentiment_save_dir()
    
    date_str = datetime.now().strftime("%Y%m%d")
    file_path = os.path.join(SENTIMENT_SAVE_DIR, f"{date_str}.json")
    
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"舆情分析结果已保存: {file_path}")
        return file_path
    except Exception as e:
        logger.error(f"保存舆情分析结果失败: {e}")
        raise


def load_sentiment_result(date_str: str = None) -> Optional[Dict]:
    """
    加载舆情分析结果
    
    :param date_str: 日期字符串，格式为YYYYMMDD，默认为今天
    :return: 舆情分析数据
    """
    if date_str is None:
        date_str = datetime.now().strftime("%Y%m%d")
    
    file_path = os.path.join(SENTIMENT_SAVE_DIR, f"{date_str}.json")
    
    if not os.path.exists(file_path):
        logger.warning(f"舆情结果文件不存在: {file_path}")
        return None
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        logger.info(f"加载舆情分析结果: {file_path}")
        return data
    except json.JSONDecodeError as e:
        logger.error(f"解析舆情结果文件失败: {e}")
        return None
    except Exception as e:
        logger.error(f"加载舆情分析结果失败: {e}")
        return None


def get_latest_sentiment_result() -> Optional[Dict]:
    """
    获取最新的舆情分析结果
    
    :return: 最新的舆情分析数据
    """
    if not os.path.exists(SENTIMENT_SAVE_DIR):
        return None
    
    try:
        files = [f for f in os.listdir(SENTIMENT_SAVE_DIR) if f.endswith('.json')]
        if not files:
            return None
        
        files.sort(reverse=True)
        latest_file = files[0]
        
        file_date_str = latest_file.replace('.json', '')
        today_str = datetime.now().strftime("%Y%m%d")
        
        if file_date_str != today_str:
            return None
        
        file_path = os.path.join(SENTIMENT_SAVE_DIR, latest_file)
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data
    except Exception as e:
        logger.error(f"加载最新舆情结果失败: {e}")
        return None


def process_industry_details(industry_details: List[Dict], top_n: int = 10) -> Tuple[List[Dict], List[Dict]]:
    """
    处理行业详情，返回所有板块和前N名板块
    
    Args:
        industry_details: 行业详情列表
        top_n: 返回前N名板块
        
    Returns:
        (all_sectors_list, top_sectors_list)
    """
    from src.factor.daily_recommend import get_sector_stocks
    
    sorted_industries = sorted(industry_details, key=lambda x: x.get('score', 0), reverse=True)
    
    all_sectors_list = []
    for item in sorted_industries:
        sector_name = item.get('industry', '')
        sentiment = int(item.get('score', 0) * 100)
        stocks = get_sector_stocks(sector_name)[:5]
        all_sectors_list.append({
            "name": sector_name,
            "sentiment": sentiment,
            "stocks": [{"code": s['code'], "name": s['name']} for s in stocks]
        })
    
    top_sectors_list = all_sectors_list[:top_n]
    
    return all_sectors_list, top_sectors_list


def get_or_generate_sentiment_data(force_refresh: bool = False) -> Tuple[Optional[Dict], Optional[List[Dict]]]:
    """
    一站式获取舆情数据，自动处理缓存、检查和更新
    
    Args:
        force_refresh: 是否强制刷新
        
    Returns:
        (sentiment_data, news_data)
    """
    from src.factor.trendradar import get_recent_news
    
    news_data = None
    sentiment_data = None
    
    if force_refresh:
        news_data = get_recent_news(max_age=SENTIMENT_CACHE_TIMEOUT)
        
        logger.info("强制刷新舆情数据，生成新的分析结果...")
        sentiment_result = calculate_sentiment_factor(news_data)
        
        if sentiment_result:
            industry_details = sentiment_result.get('analysis_result', {}).get('industry_details', [])
            all_sectors_list, top_sectors_list = process_industry_details(industry_details)
            
            sentiment_data = {
                "date": datetime.now().strftime("%Y-%m-%d"),
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "all_sectors": all_sectors_list,
                "top_sectors": top_sectors_list,
                "news_count": len(news_data) if news_data else 0
            }
            save_sentiment_result(sentiment_data)
    else:
        sentiment_data = get_latest_sentiment_result()
        
        if sentiment_data is not None:
            news_data = get_recent_news(max_age=SENTIMENT_CACHE_TIMEOUT)
        else:
            logger.info("没有今天的舆情结果，正在生成新的分析...")
            
            news_data = get_recent_news(max_age=SENTIMENT_CACHE_TIMEOUT)
            
            sentiment_result = calculate_sentiment_factor(news_data)
            
            if sentiment_result:
                industry_details = sentiment_result.get('analysis_result', {}).get('industry_details', [])
                all_sectors_list, top_sectors_list = process_industry_details(industry_details)
                
                sentiment_data = {
                    "date": datetime.now().strftime("%Y-%m-%d"),
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "all_sectors": all_sectors_list,
                    "top_sectors": top_sectors_list,
                    "news_count": len(news_data) if news_data else 0
                }
                save_sentiment_result(sentiment_data)
    
    return sentiment_data, news_data
