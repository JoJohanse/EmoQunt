# 从各个子模块导入功能
from .sentiment import (
    SentimentAnalyzer,
    calculate_sentiment_factor,
    generate_trading_signal,
    z_score_normalize,
    analyze_industry_sentiment,
    save_sentiment_result,
    load_sentiment_result,
    get_latest_sentiment_result
)
from .market import get_market_value
from .technical import calculate_factor
from .daily_recommend import (
    StockSectorMapper,
    stock_sector_mapper,
    get_stock_sector,
    is_hs300_stock
)
from .trendradar import (
    get_latest_trendradar_data,
    parse_trendradar_txt,
    convert_to_finance_news_format,
    save_to_finance_news_jsonl,
    get_trendradar_sentiment,
    crawl_and_get_news,
    save_news_to_txt,
    check_recent_txt_exists
)

# 导出所有功能
__all__ = [
    # 情绪分析模块
    'SentimentAnalyzer',
    'calculate_sentiment_factor',
    'generate_trading_signal',
    'z_score_normalize',
    'analyze_industry_sentiment',
    'save_sentiment_result',
    'load_sentiment_result',
    'get_latest_sentiment_result',
    # 市场数据模块
    'get_market_value',
    # 技术因子模块
    'calculate_factor',
    # 行业映射模块
    'StockSectorMapper',
    'stock_sector_mapper',
    'get_stock_sector',
    'is_hs300_stock',
    # 趋势雷达模块
    'get_latest_trendradar_data',
    'parse_trendradar_txt',
    'convert_to_finance_news_format',
    'save_to_finance_news_jsonl',
    'get_trendradar_sentiment',
    'crawl_and_get_news',
    'save_news_to_txt',
    'check_recent_txt_exists'
]
