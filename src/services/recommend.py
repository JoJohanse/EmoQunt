"""每日推荐服务：推荐数据获取/刷新的业务编排。

统一了原 /daily_recommend (HTML)、/api/daily-recommend (JSON)、
/refresh_recommend (HTML)、/api/daily-recommend/refresh (JSON) 的业务逻辑。
"""
import logging
from typing import Dict

logger = logging.getLogger(__name__)


def get_recommendation() -> Dict:
    """获取缓存的每日推荐。"""
    from src.factor.daily_recommend import get_cached_recommendation
    return get_cached_recommendation()


def refresh_recommendation() -> Dict:
    """强制刷新每日推荐（重新加载情绪 + 重新打分）。"""
    from src.factor.daily_recommend import refresh_recommendation, reload_sentiment
    reload_sentiment()
    return refresh_recommendation()
