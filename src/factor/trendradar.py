import os
import json
import logging
from pathlib import Path
from datetime import datetime
import re
import langchain
from tqdm import tqdm
from langchain_openai import ChatOpenAI
from modelscope.pipelines import pipeline
from modelscope.utils.constant import Tasks

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_latest_trendradar_data(trendradar_path=None):
    """
    获取 trendradar 最新的新闻数据
    
    Args:
        trendradar_path: trendradar 项目路径，如果为 None 则使用默认路径
        
    Returns:
        新闻数据列表
    """
    # 使用默认路径
    if trendradar_path is None:
        trendradar_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "nes_data", "trendradar"
        )
    
    logger.info(f"开始获取 trendradar 数据，路径: {trendradar_path}")
    
    output_path = os.path.join(trendradar_path, "output")
    if not os.path.exists(output_path):
        logger.warning(f"trendradar 输出目录不存在: {output_path}")
        return []
    
    try:
        # 获取最新日期的文件夹
        date_folders = [f for f in os.listdir(output_path) if os.path.isdir(os.path.join(output_path, f))]
        if not date_folders:
            logger.warning("trendradar 没有日期文件夹")
            return []
        
        # 按日期排序，获取最新的
        date_folders.sort(key=lambda x: datetime.strptime(x, "%Y年%m月%d日"), reverse=True)
        latest_date_folder = date_folders[0]
        logger.info(f"最新日期文件夹: {latest_date_folder}")
        
        # 获取当天的 txt 文件
        txt_path = os.path.join(output_path, latest_date_folder, "txt")
        if not os.path.exists(txt_path):
            logger.warning(f"当天的 txt 目录不存在: {txt_path}")
            return []
        
        # 获取最新的 txt 文件
        txt_files = [f for f in os.listdir(txt_path) if f.endswith(".txt")]
        if not txt_files:
            logger.warning("当天没有 txt 文件")
            return []
        
        # 按时间排序，获取最新的
        txt_files.sort(key=lambda x: datetime.strptime(x, "%H时%M分.txt"), reverse=True)
        latest_txt_file = txt_files[0]
        logger.info(f"最新 txt 文件: {latest_txt_file}")
        
        # 解析 txt 文件
        news_data = parse_trendradar_txt(os.path.join(txt_path, latest_txt_file))
        logger.info(f"成功解析 {len(news_data)} 条新闻")
        return news_data
    except Exception as e:
        logger.error(f"获取 trendradar 数据时出错: {e}")
        return []


def parse_trendradar_txt(file_path):
    """
    解析 trendradar 生成的 txt 文件
    
    Args:
        file_path: txt 文件路径
        
    Returns:
        新闻数据列表
    """
    news_list = []
    current_source = None
    
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # 检查是否是来源行
            if " | " in line:
                # 格式: id | name
                parts = line.split(" | ")
                current_source = parts[1] if len(parts) > 1 else parts[0]
            elif line.startswith("==== 以下ID请求失败 ===="):
                # 跳过失败的 ID
                break
            elif ". " in line and line.split(". ")[0].isdigit():
                # 格式: 1. 标题 [URL:xxx] [MOBILE:xxx]
                parts = line.split(". ", 1)
                if len(parts) < 2:
                    continue
                
                title_part = parts[1]
                url = ""
                mobile_url = ""
                
                # 提取 URL
                if " [URL:" in title_part:
                    title_part, url_part = title_part.rsplit(" [URL:", 1)
                    if url_part.endswith("]"):
                        url = url_part[:-1]
                
                # 提取 MOBILE URL
                if " [MOBILE:" in title_part:
                    title_part, mobile_part = title_part.rsplit(" [MOBILE:", 1)
                    if mobile_part.endswith("]"):
                        mobile_url = mobile_part[:-1]
                
                title = title_part.strip()
                
                # 创建新闻数据
                news_item = {
                    "id": f"trendradar_{len(news_list)}_{int(datetime.now().timestamp())}",
                    "title": title,
                    "content": title,  # 使用标题作为内容
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
    """
    将 trendradar 新闻转换为 Qdt_test 财务新闻格式
    
    Args:
        news_list: trendradar 新闻列表
        
    Returns:
        转换后的新闻列表
    """
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
    """
    保存新闻数据到 finance_news.jsonl 文件
    
    Args:
        news_list: 新闻列表
        output_path: 输出路径
    """
    try:
        with open(output_path, "w", encoding="utf-8") as f:
            for news in news_list:
                f.write(json.dumps(news, ensure_ascii=False) + "\n")
        logger.info(f"成功保存 {len(news_list)} 条新闻到 {output_path}")
    except Exception as e:
        logger.error(f"保存新闻数据时出错: {e}")


def get_trendradar_sentiment():
    """
    获取趋势雷达的情绪分析结果
    
    Returns:
        情绪分析结果
    """
    from .sentiment import calculate_sentiment_factor
    
    # 获取最新的新闻数据
    news_data = get_latest_trendradar_data()
    
    # 计算情绪因子
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

def load_news_list(nes_data_dir):
    """加载新闻列表"""
    with open(os.path.join(nes_data_dir, "finance_news.jsonl"), "r", encoding="utf-8") as f:
        return [json.loads(line) for line in f]

def load_processed_ids(nes_data_dir):
    """加载已处理的新闻ID集合"""
    save_path = os.path.join(nes_data_dir, "finance_news_tagged.jsonl")
    if not os.path.exists(save_path):
        return set()
    processed_ids = set()
    with open(save_path, "r", encoding="utf-8") as f:
        for line in f:
            try:
                news = json.loads(line)
                if 'id' in news:
                    processed_ids.add(news['id'])
            except:
                continue
    return processed_ids

def save_news(news, nes_data_dir):
    """保存新闻到文件"""
    save_path = os.path.join(nes_data_dir, "finance_news_tagged.jsonl")
    with open(save_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(news, ensure_ascii=False) + "\n")

def process_single_news(news, semantic_cls, llm, prompt_template, threshold):
    """处理单条新闻"""
    content = news['content']
    bert_res = semantic_cls(content)
    sentiment_scores = {'positive' if label == '正面' else 'negative': score for label, score in zip(bert_res['labels'], bert_res['scores'])}   
    prompt = prompt_template.format(news=content)
    llm_output = llm.invoke(input=prompt)
    content = llm_output.content.strip()
    if content.startswith('```json'):
        content = content[7:]
    if content.endswith('```'):
        content = content[:-3]
    content = content.strip()
    llm_res = json.loads(content)['category']
    
    if sentiment_scores['positive'] > sentiment_scores['negative'] + threshold:
        news['sentiment'] = 'positive'
    elif sentiment_scores['negative'] > sentiment_scores['positive'] + threshold:
        news['sentiment'] = 'negative'
    else:
        news['sentiment'] = 'neutral'
    news['opinion'] = {'industry': llm_res,'sentiment':{'label':news['sentiment'],'score':sentiment_scores}}

def process_news(news_list, nes_data_dir, semantic_cls, llm, prompt_template, max_news=10000):
    """批量处理新闻"""
    threshold = 0.15
    
    processed_ids = load_processed_ids(nes_data_dir)
    print(f"检测到已处理 {len(processed_ids)} 条新闻")
    
    pbar = tqdm(total=min(max_news, len(news_list)), desc="处理新闻进度", unit="条")
    pbar.set_postfix({"已处理": len(processed_ids)})
    
    for i, news in enumerate(news_list[:max_news]):
        news_id = news.get('id')
        if news_id in processed_ids:
            pbar.update(1)
            continue
        
        try:
            process_single_news(news, semantic_cls, llm, prompt_template, threshold)
        except Exception as e:
            print(f"处理第{i}条新闻时出错: {e}")
            news['opinion'] = {}
        
        save_news(news, nes_data_dir)
        processed_ids.add(news_id)
        pbar.update(1)
        pbar.set_postfix({"已处理": len(processed_ids)})
    
    pbar.close()
    print(f"处理完成！共处理 {min(max_news, len(news_list))} 条新闻")