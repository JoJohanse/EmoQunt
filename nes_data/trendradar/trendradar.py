import os
import sys
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional

from dotenv import load_dotenv

# 加载项目根目录的 .env
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(dotenv_path=str(_PROJECT_ROOT / ".env"))

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# TrendRadar 项目路径
TRENDRADAR_BASE_DIR = str(_PROJECT_ROOT / "nes_data" / "trendradar")

# 设置工作目录，确保加载正确的配置文件
os.chdir(TRENDRADAR_BASE_DIR)

# 爬取器状态
_crawler_initialized = False
_data_fetcher = None
_config = None

def _init_crawler():
    """初始化 TrendRadar 爬取器"""
    global _crawler_initialized, _data_fetcher, _config
    
    if _crawler_initialized:
        return True
    
    try:
        sys.path.insert(0, TRENDRADAR_BASE_DIR)
        
        # 直接导入 DataFetcher 类
        from main import DataFetcher, CONFIG
        
        _config = CONFIG
        _data_fetcher = DataFetcher()
        _crawler_initialized = True
        logger.info("TrendRadar 爬取器初始化成功")
        return True
    except Exception as e:
        logger.warning(f"TrendRadar 爬取器初始化失败: {e}")
        import traceback
        logger.warning(f"详细错误: {traceback.format_exc()}")
        _crawler_initialized = False
        return False


def _load_config():
    """加载 TrendRadar 配置"""
    global _config
    if _config is not None:
        return _config
    
    try:
        sys.path.insert(0, TRENDRADAR_BASE_DIR)
        from main import load_config, CONFIG
        _config = CONFIG
        return _config
    except Exception as e:
        logger.warning(f"加载 TrendRadar 配置失败: {e}")
        return None


def crawl_and_get_news() -> List[Dict]:
    """
    爬取最新新闻并返回
        
    Returns:
        新闻列表
    """
    if not _init_crawler():
        logger.warning("爬取器未初始化，返回空列表")
        return []
    
    try:
        config = _load_config()
        if not config:
            return []
        
        # 获取配置的监控平台
        ids = []
        for platform in config.get("PLATFORMS", []):
            if "name" in platform:
                ids.append((platform["id"], platform["name"]))
            else:
                ids.append(platform["id"])
        
        logger.info(f"开始爬取 {len(ids)} 个平台的新闻")
        
        # 执行爬取
        results, id_to_name, failed_ids = _data_fetcher.crawl_websites(
            ids, 
            request_interval=config.get("REQUEST_INTERVAL", 500)
        )
        
        # 转换结果为新闻列表
        news_list = []
        for platform_id, titles_data in results.items():
            platform_name = id_to_name.get(platform_id, platform_id)
            for title, info in titles_data.items():
                news_item = {
                    "id": f"trendradar_{len(news_list)}_{int(datetime.now().timestamp())}",
                    "title": title,
                    "content": title,
                    "date": datetime.now().strftime("%Y-%m-%d"),
                    "source": platform_name,
                    "url": info.get("url", ""),
                    "mobile_url": info.get("mobileUrl", ""),
                    "platform": platform_id
                }
                news_list.append(news_item)
        
        logger.info(f"爬取完成，共获取 {len(news_list)} 条新闻")
        return news_list
        
    except Exception as e:
        logger.error(f"爬取新闻时出错: {e}")
        return []


def get_latest_trendradar_data(force_crawl=True):
    """
    获取 trendradar 最新的新闻数据
    
    Args:
        force_crawl: 是否强制爬取新数据，True 则实时爬取，False 则读取已保存的数据
        
    Returns:
        新闻数据列表
    """
    # 优先尝试爬取新数据
    if force_crawl:
        news_list = crawl_and_get_news()
        if news_list:
            logger.info(f"实时爬取获取到 {len(news_list)} 条新闻")
            return news_list
        logger.warning("实时爬取失败，fallback到读取已保存数据")
    
    # Fallback: 读取已保存的文件
    return _get_latest_trendradar_from_file()


def _get_latest_trendradar_from_file():
    """从已保存的文件读取数据（fallback方式）"""
    trendradar_path = TRENDRADAR_BASE_DIR
    
    logger.info(f"从文件读取 trendradar 数据，路径: {trendradar_path}")
    
    output_path = os.path.join(trendradar_path, "output")
    if not os.path.exists(output_path):
        logger.warning(f"trendradar 输出目录不存在: {output_path}")
        return []
    
    try:
        date_folders = [f for f in os.listdir(output_path) if os.path.isdir(os.path.join(output_path, f))]
        if not date_folders:
            logger.warning("trendradar 没有日期文件夹")
            return []
        
        date_folders.sort(key=lambda x: datetime.strptime(x, "%Y年%m月%d日"), reverse=True)
        latest_date_folder = date_folders[0]
        logger.info(f"最新日期文件夹: {latest_date_folder}")
        
        txt_path = os.path.join(output_path, latest_date_folder, "txt")
        if not os.path.exists(txt_path):
            logger.warning(f"当天的 txt 目录不存在: {txt_path}")
            return []
        
        txt_files = [f for f in os.listdir(txt_path) if f.endswith(".txt")]
        if not txt_files:
            logger.warning("当天没有 txt 文件")
            return []
        
        txt_files.sort(key=lambda x: datetime.strptime(x, "%H时%M分.txt"), reverse=True)
        latest_txt_file = txt_files[0]
        logger.info(f"最新 txt 文件: {latest_txt_file}")
        
        news_data = parse_trendradar_txt(os.path.join(txt_path, latest_txt_file))
        return news_data
    except Exception as e:
        logger.error(f"读取 trendradar 数据时出错: {e}")
        return []


def check_recent_txt_exists(max_age_seconds=3600):
    """检查是否存在1小时内的txt文件"""
    trendradar_path = TRENDRADAR_BASE_DIR
    output_path = os.path.join(trendradar_path, "output")
    
    if not os.path.exists(output_path):
        return False, None
    
    try:
        date_folders = [f for f in os.listdir(output_path) if os.path.isdir(os.path.join(output_path, f))]
        if not date_folders:
            return False, None
        
        date_folders.sort(key=lambda x: datetime.strptime(x, "%Y年%m月%d日"), reverse=True)
        
        now = datetime.now()
        
        for date_folder in date_folders:
            txt_path = os.path.join(output_path, date_folder, "txt")
            if not os.path.exists(txt_path):
                continue
            
            txt_files = [f for f in os.listdir(txt_path) if f.endswith(".txt")]
            if not txt_files:
                continue
            
            txt_files.sort(key=lambda x: datetime.strptime(x, "%H时%M分.txt"), reverse=True)
            
            for txt_file in txt_files:
                try:
                    file_time = datetime.strptime(txt_file, "%H时%M分.txt")
                    file_time = file_time.replace(year=now.year, month=now.month, day=now.day)
                    
                    if file_time > now:
                        file_time = file_time.replace(day=now.day - 1)
                    
                    time_diff = (now - file_time).total_seconds()
                    
                    if time_diff <= max_age_seconds:
                        return True, os.path.join(txt_path, txt_file)
                except:
                    continue
        
        return False, None
    except Exception as e:
        logger.error(f"检查最近txt文件时出错: {e}")
        return False, None


def parse_trendradar_txt(file_path):
    """解析 trendradar 生成的 txt 文件"""
    news_list = []
    current_source = None
    
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            if " | " in line:
                parts = line.split(" | ")
                current_source = parts[1] if len(parts) > 1 else parts[0]
            elif line.startswith("==== 以下ID请求失败 ===="):
                break
            elif ". " in line and line.split(". ")[0].isdigit():
                parts = line.split(". ", 1)
                if len(parts) < 2:
                    continue
                
                title_part = parts[1]
                url = ""
                mobile_url = ""
                
                if " [URL:" in title_part:
                    title_part, url_part = title_part.rsplit(" [URL:", 1)
                    if url_part.endswith("]"):
                        url = url_part[:-1]
                
                if " [MOBILE:" in title_part:
                    title_part, mobile_part = title_part.rsplit(" [MOBILE:", 1)
                    if mobile_part.endswith("]"):
                        mobile_url = mobile_part[:-1]
                
                title = title_part.strip()
                
                news_item = {
                    "id": f"trendradar_{len(news_list)}_{int(datetime.now().timestamp())}",
                    "title": title,
                    "content": title,
                    "date": datetime.now().strftime("%Y-%m-%d"),
                    "source": current_source,
                    "url": url,
                    "mobile_url": mobile_url
                }
                news_list.append(news_item)
    except Exception as e:
        logger.error(f"解析 txt 文件时出错: {e}")
    
    return news_list


def convert_to_finance_news_format(news_list):
    """将 trendradar 新闻转换为系统所需格式"""
    finance_news = []
    for news in news_list:
        finance_news_item = {
            "id": news["id"],
            "title": news["title"],
            "content": news["content"],
            "date": news["date"],
            "source": news["source"],
            "url": news.get("url", ""),
            "mobile_url": news.get("mobile_url", "")
        }
        finance_news.append(finance_news_item)
    return finance_news


def save_to_finance_news_jsonl(news_list, output_path):
    """保存新闻数据到文件"""
    try:
        with open(output_path, "w", encoding="utf-8") as f:
            for news in news_list:
                f.write(json.dumps(news, ensure_ascii=False) + "\n")
        logger.info(f"成功保存 {len(news_list)} 条新闻到 {output_path}")
    except Exception as e:
        logger.error(f"保存新闻数据时出错: {e}")


def save_news_to_txt(news_list, output_dir=None):
    """
    将新闻列表保存为 txt 文件
    
    Args:
        news_list: 新闻列表
        output_dir: 输出目录（可选，默认使用 trendradar/output）
        
    Returns:
        保存的文件路径
    """
    if not news_list:
        logger.warning("没有新闻数据可保存")
        return None
    
    if output_dir is None:
        output_dir = TRENDRADAR_BASE_DIR
    
    now = datetime.now()
    date_folder = now.strftime("%Y年%m月%d日")
    time_file = now.strftime("%H时%M分")
    
    output_path = os.path.join(output_dir, "output", date_folder, "txt")
    os.makedirs(output_path, exist_ok=True)
    
    file_path = os.path.join(output_path, f"{time_file}.txt")
    
    source_news = {}
    for news in news_list:
        source = news.get("source", "未知来源")
        if source not in source_news:
            source_news[source] = []
        source_news[source].append(news)
    
    with open(file_path, "w", encoding="utf-8") as f:
        for source, items in source_news.items():
            f.write(f"{source}\n")
            for i, news in enumerate(items, 1):
                title = news.get("title", "")
                url = news.get("url", "")
                mobile_url = news.get("mobile_url", "")
                
                line = f"{i}. {title}"
                if url:
                    line += f" [URL:{url}]"
                if mobile_url:
                    line += f" [MOBILE:{mobile_url}]"
                f.write(line + "\n")
    
    logger.info(f"已将 {len(news_list)} 条新闻保存到 {file_path}")
    return file_path


def get_trendradar_sentiment():
    """获取情绪分析结果"""
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    
    from src.factor.sentiment import calculate_sentiment_factor
    
    has_recent, txt_file = check_recent_txt_exists(max_age_seconds=3600)
    if has_recent and txt_file:
        news_data = parse_trendradar_txt(txt_file)
    else:
        logger.info("没有1小时内的txt文件，需要重新爬取")
        news_data = get_latest_trendradar_data(force_crawl=True)
        if news_data:
            save_news_to_txt(news_data)
    
    if news_data:
        sentiment_result = calculate_sentiment_factor(news_data)
        logger.info(f"情绪分析结果: {sentiment_result}")
        return sentiment_result
    else:
        logger.warning("没有获取到新闻数据，无法进行情绪分析")
        return {
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'sentiment_scores': [0.0] * 64,
            'average_score': 0.0,
            'analysis_result': {
                'total_news': 0,
                'positive_industry_count': 0,
                'negative_industry_count': 0,
                'neutral_industry_count': 64,
                'average_score': 0.0,
                'score_distribution': {
                    'positive': 0,
                    'negative': 0,
                    'neutral': 1.0
                },
                'industry_details': []
            },
            'signal': 'hold'
        }
