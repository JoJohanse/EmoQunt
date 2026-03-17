import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import os
import csv
import json
import logging
import sys
import io
import contextlib

logger = logging.getLogger(__name__)

bs_logger = logging.getLogger('baostock')
bs_logger.setLevel(logging.WARNING)

with contextlib.redirect_stdout(io.StringIO()):
    try:
        import baostock as bs
        BAOSTOCK_AVAILABLE = True
    except ImportError:
        BAOSTOCK_AVAILABLE = False
        logger.warning("baostock 未安装，请运行: pip install baostock")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CSV_PATH = os.path.join(BASE_DIR, "stock_data", "沪深300", "沪深300成分股列表.csv")
INDUSTRY_PATH = os.path.join(BASE_DIR, "stock_data", "沪深300", "行业种类.txt")
CACHE_DIR = os.path.join(BASE_DIR, "stock_data", "stock_cache")

STOCK_DATA_CACHE = {}

def ensure_cache_dir():
    if not os.path.exists(CACHE_DIR):
        os.makedirs(CACHE_DIR, exist_ok=True)

ensure_cache_dir()

def get_cached_stock_data(stock_code: str) -> Optional[pd.DataFrame]:
    cache_file = os.path.join(CACHE_DIR, f"{stock_code.replace('.', '_')}.csv")
    if os.path.exists(cache_file):
        try:
            df = pd.read_csv(cache_file, index_col=0)
            df.index = pd.to_datetime(df.index)
            return df
        except Exception as e:
            logger.warning(f"读取缓存文件失败 {cache_file}: {e}")
            return None
    return None

def save_stock_data_to_cache(stock_code: str, df: pd.DataFrame):
    if df is None or len(df) == 0:
        return
    cache_file = os.path.join(CACHE_DIR, f"{stock_code.replace('.', '_')}.csv")
    try:
        df.to_csv(cache_file)
    except:
        pass

HS300_STOCKS = {}
INDUSTRIES = []
SECTOR_STOCKS = {}
SECTOR_SENTIMENT = {}

def load_hs300_stocks():
    global HS300_STOCKS, INDUSTRIES, SECTOR_STOCKS
    
    HS300_STOCKS = {}
    SECTOR_STOCKS = {}
    
    try:
        with open(CSV_PATH, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                code = row['股票代码'].strip()
                name = row['股票简称'].strip()
                industry = row['行业'].strip()
                
                if code.startswith('6'):
                    full_code = f"{code}.SH"
                elif code.startswith(('0', '3')):
                    full_code = f"{code}.SZ"
                else:
                    full_code = f"{code}.SH"
                
                HS300_STOCKS[code] = {
                    'name': name,
                    'industry': industry,
                    'full_code': full_code
                }
                
                if industry not in SECTOR_STOCKS:
                    SECTOR_STOCKS[industry] = []
                SECTOR_STOCKS[industry].append({
                    'code': code,
                    'name': name,
                    'full_code': full_code,
                    'industry': industry
                })
        
        logger.info(f"成功加载 {len(HS300_STOCKS)} 只沪深300成分股")
        logger.info(f"行业数量: {len(SECTOR_STOCKS)}")
    except Exception as e:
        logger.error(f"加载沪深300成分股失败: {e}")

def load_industries():
    global INDUSTRIES
    
    INDUSTRIES = []
    
    try:
        with open(INDUSTRY_PATH, 'r', encoding='utf-8') as f:
            for line in f:
                industry = line.strip()
                if industry and industry != '行业':
                    INDUSTRIES.append(industry)
        
        logger.info(f"成功加载 {len(INDUSTRIES)} 个行业")
    except Exception as e:
        logger.error(f"加载行业列表失败: {e}")

def init_sentiment():
    global SECTOR_SENTIMENT
    
    SECTOR_SENTIMENT = {}
    
    try:
        from .sentiment import get_latest_sentiment_result
        
        sentiment_data = get_latest_sentiment_result()
        
        if sentiment_data and 'top_sectors' in sentiment_data:
            for sector_info in sentiment_data.get('top_sectors', []):
                sector_name = sector_info.get('name', '')
                sentiment = sector_info.get('sentiment', 50)
                if sector_name:
                    SECTOR_SENTIMENT[sector_name] = sentiment
            logger.info(f"从舆情结果加载了 {len(SECTOR_SENTIMENT)} 个板块的舆情评分")
        
        if not SECTOR_SENTIMENT:
            SECTOR_SENTIMENT = _get_default_sentiment()
            logger.info("使用默认舆情评分")
    except Exception as e:
        logger.warning(f"加载舆情结果失败，使用默认评分: {e}")
        SECTOR_SENTIMENT = _get_default_sentiment()

def _get_default_sentiment():
    return {
        "半导体": 85,
        "光伏设备": 82,
        "电池": 80,
        "酿酒行业": 78,
        "医疗服务": 76,
        "医疗器械": 74,
        "软件开发": 82,
        "互联网服务": 80,
        "汽车整车": 75,
        "汽车零部件": 73,
        "通信设备": 70,
        "化学制药": 68,
        "生物制品": 71,
        "电子元件": 76,
        "电力行业": 60,
        "银行": 58,
        "证券": 60,
        "保险": 59,
        "工程建设": 65,
        "房地产": 50,
        "航空机场": 68,
        "航运港口": 63,
        "物流行业": 70,
        "家电行业": 72,
        "食品饮料": 75,
        "旅游酒店": 58,
        "文化传媒": 65,
        "钢铁行业": 55,
        "有色金属": 68,
        "煤炭行业": 58,
        "建筑工程": 63,
        "铁路公路": 60,
        "多元金融": 61,
        "燃气": 62,
        "化学原料": 67,
        "化学制品": 65,
        "化纤行业": 63,
        "非金属材料": 60,
        "玻璃玻纤": 61,
        "水泥建材": 62,
        "装修建材": 63,
        "商业百货": 57,
        "医药商业": 65,
        "中药": 70,
        "美容护理": 68,
        "纺织服装": 59,
        "家用轻工": 62,
        "工程机械": 66,
        "电源设备": 73,
        "电网设备": 69,
        "交运设备": 64,
        "船舶制造": 60,
        "航天航空": 67,
        "农牧饲渔": 53,
        "化肥行业": 61,
        "小金属": 65,
        "贵金属": 63,
        "能源金属": 78,
        "石油行业": 55,
        "光学光电子": 72,
        "计算机设备": 75,
        "消费电子": 78,
        "通信服务": 66,
    }

def reload_sentiment():
    global SECTOR_SENTIMENT
    init_sentiment()

def load_all_data():
    load_hs300_stocks()
    load_industries()
    init_sentiment()

load_all_data()

def get_top_sectors(n: int = 3) -> List[tuple]:
    sorted_sectors = sorted(SECTOR_SENTIMENT.items(), key=lambda x: x[1], reverse=True)
    return sorted_sectors[:n]

def get_sector_stocks(sector: str) -> List[Dict]:
    return SECTOR_STOCKS.get(sector, [])

def get_stock_data(stock_code: str, days: int = 20) -> Optional[pd.DataFrame]:
    if stock_code in STOCK_DATA_CACHE:
        return STOCK_DATA_CACHE[stock_code]
    
    cached_df = get_cached_stock_data(stock_code)
    if cached_df is not None:
        if len(cached_df) > 0:
            latest_date = cached_df.index[-1]
            if isinstance(latest_date, str):
                latest_date = pd.to_datetime(latest_date).date()
            else:
                latest_date = latest_date.date()
            today = datetime.now().date()
            date_diff = (today - latest_date).days
            logger.info(f"股票 {stock_code} 缓存数据最新日期: {latest_date}, 今天: {today}")
            if date_diff <= 1:
                STOCK_DATA_CACHE[stock_code] = cached_df
                return cached_df.tail(days) if len(cached_df) >= days else cached_df
            else:
                logger.info(f"股票 {stock_code} 缓存数据过期，需要重新获取")
    
    if not BAOSTOCK_AVAILABLE:
        logger.warning("baostock 未安装")
        return None
    
    try:
        code = stock_code.split('.')[0]
        if stock_code.endswith('.SH'):
            bs_code = f"sh.{code}"
        elif stock_code.endswith('.SZ'):
            bs_code = f"sz.{code}"
        else:
            bs_code = f"sh.{code}"
        
        with contextlib.redirect_stdout(io.StringIO()):
            lg = bs.login()
            if lg.error_code != '0':
                logger.warning(f"baostock 登录失败: {lg.error_msg}")
                return None
                
            rs = bs.query_history_k_data_plus(
                bs_code,
                "date,code,open,high,low,close,volume,amount",
                start_date=(datetime.now() - timedelta(days=days+20)).strftime("%Y-%m-%d"),
                end_date=datetime.now().strftime("%Y-%m-%d"),
                frequency="d",
                adjustflag="2"
            )
            
            data_list = []
            while (rs.error_code == '0') and rs.next():
                data_list.append(rs.get_row_data())
            
            bs.logout()
        
        if not data_list:
            logger.warning(f"未获取到股票 {stock_code} 的数据")
            return None
        
        df = pd.DataFrame(data_list, columns=rs.fields)
        
        date_col = None
        for col in df.columns:
            if 'date' in col.lower():
                date_col = col
                break
        
        if date_col is None:
            logger.warning(f"未找到日期列，字段: {df.columns.tolist()}")
            return None
        
        col_mapping = {
            'open': '开盘', 'high': '最高', 'low': '最低', 
            'close': '收盘', 'volume': '成交量', 'amount': '成交额'
        }
        
        rename_dict = {}
        for old_col, new_col in col_mapping.items():
            if old_col in df.columns:
                rename_dict[old_col] = new_col
        
        df.rename(columns=rename_dict, inplace=True)
        
        df[date_col] = pd.to_datetime(df[date_col])
        df.set_index(date_col, inplace=True)
        df = df.sort_index()
        
        for col in ['开盘', '最高', '最低', '收盘', '成交量', '成交额']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        STOCK_DATA_CACHE[stock_code] = df
        save_stock_data_to_cache(stock_code, df)
        return df.tail(days)
        
    except Exception as e:
        logger.warning(f"获取股票 {stock_code} 数据失败: {e}")
        return None

def calculate_price_change_score(df: pd.DataFrame) -> float:
    if df is None or len(df) < 5:
        return 50.0
    
    try:
        recent = df.tail(5)
        price_change = (recent['收盘'].iloc[-1] - recent['收盘'].iloc[0]) / recent['收盘'].iloc[0] * 100
        
        if price_change > 10:
            return 100
        elif price_change > 5:
            return 80
        elif price_change > 0:
            return 60
        elif price_change > -5:
            return 40
        else:
            return 20
    except:
        return 50.0

def calculate_volume_score(df: pd.DataFrame) -> float:
    if df is None or len(df) < 20:
        return 50.0
    
    try:
        recent_5 = df.tail(5)['成交量'].mean()
        recent_20 = df['成交量'].mean()
        
        if recent_20 == 0:
            return 50.0
        
        volume_ratio = recent_5 / recent_20
        
        if volume_ratio > 1.5:
            return 100
        elif volume_ratio > 1.2:
            return 80
        elif volume_ratio > 1.0:
            return 60
        elif volume_ratio > 0.8:
            return 40
        else:
            return 20
    except:
        return 50.0

def calculate_technical_score(df: pd.DataFrame) -> float:
    if df is None or len(df) < 10:
        return 50.0
    
    try:
        ma5 = df.tail(5)['收盘'].mean()
        ma10 = df.tail(10)['收盘'].mean()
        current_price = df['收盘'].iloc[-1]
        
        if ma5 > ma10 and current_price > ma5:
            return 100
        elif ma5 > ma10:
            return 70
        elif current_price > ma10:
            return 50
        else:
            return 30
    except:
        return 50.0

def calculate_stock_score(stock_code: str, stock_name: str, sector: str, sector_sentiment: float) -> Dict:
    df = get_stock_data(stock_code)
    
    price_score = calculate_price_change_score(df)
    volume_score = calculate_volume_score(df)
    technical_score = calculate_technical_score(df)
    sentiment_score = sector_sentiment
    
    total_score = (
        price_score * 0.30 +
        volume_score * 0.20 +
        sentiment_score * 0.30 +
        technical_score * 0.20
    )
    
    reason_parts = []
    if price_score >= 60:
        reason_parts.append("近期涨势良好")
    if volume_score >= 70:
        reason_parts.append("成交量放大")
    if sentiment_score >= 80:
        reason_parts.append("板块热度高")
    if technical_score >= 70:
        reason_parts.append("技术形态强势")
    
    reason = "，".join(reason_parts) if reason_parts else "综合考量推荐"
    
    return {
        "code": stock_code,
        "name": stock_name,
        "sector": sector,
        "score": round(total_score, 2),
        "price_score": round(price_score, 2),
        "volume_score": round(volume_score, 2),
        "sentiment_score": round(sentiment_score, 2),
        "technical_score": round(technical_score, 2),
        "reason": reason
    }

def generate_daily_recommend(n: int = 10) -> Dict:
    top_sectors = get_top_sectors(3)
    
    logger.info(f"前3热门板块: {top_sectors}")
    
    all_candidates = []
    for sector, sentiment in top_sectors:
        stocks = get_sector_stocks(sector)
        for stock in stocks:
            all_candidates.append({
                "code": stock['full_code'],
                "short_code": stock['code'],
                "name": stock['name'],
                "sector": sector,
                "sector_sentiment": sentiment
            })
    
    logger.info(f"候选股票总数: {len(all_candidates)}")
    
    scored_stocks = []
    for candidate in all_candidates:
        score_result = calculate_stock_score(
            candidate["code"],
            candidate["name"],
            candidate["sector"],
            candidate["sector_sentiment"]
        )
        scored_stocks.append(score_result)
    
    scored_stocks.sort(key=lambda x: x["score"], reverse=True)
    
    top_n = scored_stocks[:n]
    
    for i, stock in enumerate(top_n, 1):
        stock["rank"] = i
    
    return {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "top_sectors": [{"name": s[0], "sentiment": s[1]} for s in top_sectors],
        "recommendations": top_n
    }

_cache = None
_cache_time = None

def get_cached_recommendation() -> Dict:
    global _cache, _cache_time
    
    now = datetime.now()
    if _cache is None or _cache_time is None or (now - _cache_time).total_seconds() > 3600:
        _cache = generate_daily_recommend()
        _cache_time = now
    
    return _cache

def refresh_recommendation() -> Dict:
    global _cache, _cache_time
    
    _cache = generate_daily_recommend()
    _cache_time = datetime.now()
    
    return _cache

def get_sentiment_data() -> Dict:
    top_sectors = get_top_sectors(10)
    
    result = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "sectors": []
    }
    
    for sector_name, sentiment in top_sectors:
        stocks = get_sector_stocks(sector_name)[:5]
        result["sectors"].append({
            "name": sector_name,
            "sentiment": sentiment,
            "stocks": [{"code": s['code'], "name": s['name']} for s in stocks]
        })
    
    return result


# 股票行业映射器
class StockSectorMapper:
    """股票行业映射器 - 根据股票代码查找所属行业"""
    
    def __init__(self):
        self.stock_sector_map = self._load_stock_sector_map()
    
    def _load_stock_sector_map(self):
        stock_sector_map = {}
        csv_path = os.path.join(BASE_DIR, "stock_data", "沪深300", "沪深300成分股列表.csv")
        
        try:
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    stock_code = row['股票代码'].strip()
                    stock_name = row['股票简称'].strip()
                    sector = row['行业'].strip()
                    stock_sector_map[stock_code] = {"name": stock_name, "sector": sector}
        except Exception as e:
            logger.warning(f"加载股票行业映射失败: {e}")
        
        return stock_sector_map
    
    def get_info_by_code(self, stock_code: str) -> Optional[Dict]:
        stock_code = stock_code.split('.')[0]
        return self.stock_sector_map.get(stock_code)
    
    def get_sector_by_code(self, stock_code: str) -> Optional[str]:
        stock_info = self.get_info_by_code(stock_code)
        return stock_info.get("sector") if stock_info else None
    
    def is_hs300_stock(self, stock_code: str) -> bool:
        stock_code = stock_code.split('.')[0]
        return stock_code in self.stock_sector_map


stock_sector_mapper = StockSectorMapper()

def get_stock_sector(stock_code: str) -> Optional[str]:
    """获取股票所属行业"""
    return stock_sector_mapper.get_sector_by_code(stock_code)

def is_hs300_stock(stock_code: str) -> bool:
    """检查股票是否为沪深300成分股"""
    return stock_sector_mapper.is_hs300_stock(stock_code)
