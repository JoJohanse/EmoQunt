import os
import sys

from src.utils.env import load_env
load_env()
from src.utils.paths import get_trendradar_dir

# 将 trendradar 目录添加到路径
TRENDRADAR_DIR = str(get_trendradar_dir())
sys.path.insert(0, TRENDRADAR_DIR)

# 设置配置文件路径（.env 中定义的 CONFIG_PATH 优先）
os.environ.setdefault("CONFIG_PATH", os.path.join(TRENDRADAR_DIR, "config", "config.yaml"))

# 导入 trendradar 模块的功能
from trendradar import (
    get_latest_trendradar_data,
    crawl_and_get_news,
    parse_trendradar_txt,
    convert_to_finance_news_format,
    save_to_finance_news_jsonl,
    get_trendradar_sentiment,
    save_news_to_txt,
    check_recent_txt_exists
)

def get_recent_news(max_age: int = 3600) -> list:
    """获取近期 TrendRadar 新闻（新闻读取编排的单一通道）。

    内部完成完整编排：判定是否存在 max_age 秒内的新鲜 txt 快照，
    有则直接解析返回；无则实时爬取并落盘保存（爬取失败时底层会
    回退读取历史文件，仍无数据则返回空列表）。

    Args:
        max_age: txt 快照的最大新鲜秒数

    Returns:
        新闻列表，无数据时为空列表
    """
    has_recent, txt_file = check_recent_txt_exists(max_age_seconds=max_age)
    if has_recent and txt_file:
        return parse_trendradar_txt(txt_file) or []

    news_data = get_latest_trendradar_data(force_crawl=True)
    if news_data:
        save_news_to_txt(news_data)
    return news_data or []


__all__ = [
    'get_latest_trendradar_data',
    'crawl_and_get_news', 
    'parse_trendradar_txt',
    'convert_to_finance_news_format',
    'save_to_finance_news_jsonl',
    'get_trendradar_sentiment',
    'save_news_to_txt',
    'check_recent_txt_exists',
    'get_recent_news'
]
