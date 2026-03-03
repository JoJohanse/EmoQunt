# 从各个子模块导入功能
from .sentiment import (
    SentimentAnalyzer,
    calculate_sentiment_factor,
    generate_trading_signal,
    NATIONAL_ECONOMY_CATEGORIES,
    z_score_normalize,
    analyze_industry_sentiment
)
from .market import get_market_value
from .technical import calculate_factor
from .sector import (
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
    load_news_list,
    load_processed_ids,
    save_news,
    process_single_news,
    process_news
)

# 导出所有功能，保持向后兼容性
__all__ = [
    # 情绪分析模块
    'SentimentAnalyzer',
    'calculate_sentiment_factor',
    'generate_trading_signal',
    'NATIONAL_ECONOMY_CATEGORIES',
    'z_score_normalize',
    'analyze_industry_sentiment',
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
    'load_news_list',
    'load_processed_ids',
    'save_news',
    'process_single_news',
    'process_news'
]

# 确保旧的导入路径仍然可用
# 这样现有的代码仍然可以直接从factor模块导入这些函数
# 例如：from src.factor import get_market_value