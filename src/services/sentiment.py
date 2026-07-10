"""舆情服务：舆情数据获取/刷新的业务编排。

统一了原 /sentiment (HTML)、/api/sentiment/data (JSON)、/refresh_sentiment (HTML)
三个路由共享的业务逻辑。
"""
import logging
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)


def get_sentiment_data() -> Dict:
    """获取舆情数据（不强制刷新）。

    统一了原 /sentiment 与 /api/sentiment/data 的业务逻辑。
    :return: {news_list, sectors, news_count, update_time}
    """
    from src.factor.sentiment import get_or_generate_sentiment_data

    sentiment_data, news_data = get_or_generate_sentiment_data()
    sectors = []
    if sentiment_data and 'top_sectors' in sentiment_data:
        sectors = sentiment_data['top_sectors']
    return {
        "news_list": (news_data or [])[:20],
        "sectors": sectors,
        "news_count": len(news_data or []),
        "update_time": sentiment_data.get('timestamp', '') if sentiment_data else '',
    }


def refresh_sentiment() -> Dict:
    """强制刷新舆情数据（重新抓取+分析）。

    统一了原 /refresh_sentiment 的业务逻辑。
    :return: {news_list, sectors, news_count, update_time}
    """
    from src.factor import get_trendradar_sentiment

    sentiment_result = get_trendradar_sentiment()
    sectors = []
    if sentiment_result and 'top_sectors' in sentiment_result:
        sectors = sentiment_result['top_sectors']

    news_list = []
    try:
        from nes_data.trendradar.trendradar import check_recent_txt_exists, parse_trendradar_txt
        has_recent, txt_file = check_recent_txt_exists(max_age_seconds=3600)
        if has_recent:
            news_list = parse_trendradar_txt(txt_file) or []
    except Exception:
        news_list = []

    return {
        "news_list": news_list[:20],
        "sectors": sectors,
        "news_count": len(news_list),
        "update_time": sentiment_result.get('timestamp', '') if sentiment_result else '',
    }
