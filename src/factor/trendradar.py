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

__all__ = [
    'get_latest_trendradar_data',
    'crawl_and_get_news', 
    'parse_trendradar_txt',
    'convert_to_finance_news_format',
    'save_to_finance_news_jsonl',
    'get_trendradar_sentiment',
    'save_news_to_txt',
    'check_recent_txt_exists'
]
