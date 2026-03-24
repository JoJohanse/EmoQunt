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
        
    except Exception as e:
        logger.warning(f"加载舆情结果失败")

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

def get_stock_data(stock_code: str, days: int = 30) -> Optional[pd.DataFrame]:
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
                # 获取最近30天数据,起始日期为30天前，days=30
                start_date=(datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d"),
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
    if df is None or len(df) < 20:
        return 50.0
    
    try:
        scores = []
        
        recent_5 = df.tail(5)
        recent_10 = df.tail(10)
        recent_20 = df.tail(20) if len(df) >= 20 else df
        
        price_5 = recent_5['收盘'].iloc[-1]
        price_10 = recent_10['收盘'].iloc[-1]
        price_20 = recent_20['收盘'].iloc[-1]
        current_price = df['收盘'].iloc[-1]
        
        ma5 = recent_5['收盘'].mean()
        ma10 = recent_10['收盘'].mean()
        ma20 = recent_20['收盘'].mean()
        
        change_5d = (price_5 - recent_5['收盘'].iloc[0]) / recent_5['收盘'].iloc[0] * 100
        change_10d = (price_10 - recent_10['收盘'].iloc[0]) / recent_10['收盘'].iloc[0] * 100
        change_20d = (price_20 - recent_20['收盘'].iloc[0]) / recent_20['收盘'].iloc[0] * 100
        
        if change_5d > 10:
            score_5d = 100
        elif change_5d > 7:
            score_5d = 90
        elif change_5d > 5:
            score_5d = 80
        elif change_5d > 3:
            score_5d = 70
        elif change_5d > 1:
            score_5d = 60
        elif change_5d > -1:
            score_5d = 50
        elif change_5d > -3:
            score_5d = 40
        elif change_5d > -5:
            score_5d = 30
        elif change_5d > -7:
            score_5d = 20
        else:
            score_5d = 10
        scores.append(score_5d * 0.35)
        
        if change_10d > 15:
            score_10d = 100
        elif change_10d > 10:
            score_10d = 85
        elif change_10d > 5:
            score_10d = 70
        elif change_10d > 0:
            score_10d = 55
        elif change_10d > -5:
            score_10d = 40
        elif change_10d > -10:
            score_10d = 25
        else:
            score_10d = 10
        scores.append(score_10d * 0.25)
        
        if change_20d > 20:
            score_20d = 100
        elif change_20d > 15:
            score_20d = 85
        elif change_20d > 10:
            score_20d = 70
        elif change_20d > 5:
            score_20d = 55
        elif change_20d > 0:
            score_20d = 45
        elif change_20d > -5:
            score_20d = 35
        elif change_20d > -10:
            score_20d = 25
        else:
            score_20d = 10
        scores.append(score_20d * 0.20)
        
        if ma5 > ma10 > ma20:
            trend_score = 100
        elif ma5 > ma10:
            trend_score = 75
        elif ma5 > ma20:
            trend_score = 60
        elif ma10 > ma20:
            trend_score = 45
        else:
            trend_score = 25
        scores.append(trend_score * 0.20)
        
        return sum(scores)
        
    except Exception as e:
        logger.warning(f"计算价格变化得分失败: {e}")
        return 50.0

def calculate_volume_score(df: pd.DataFrame) -> float:
    if df is None or len(df) < 20:
        return 50.0
    
    try:
        scores = []
        
        recent_5 = df.tail(5)
        recent_10 = df.tail(10)
        recent_20 = df.tail(20) if len(df) >= 20 else df
        
        vol_5_mean = recent_5['成交量'].mean()
        vol_10_mean = recent_10['成交量'].mean()
        vol_20_mean = recent_20['成交量'].mean()
        
        current_vol = df['成交量'].iloc[-1]
        avg_vol = df['成交量'].mean()
        
        if avg_vol == 0:
            return 50.0
        
        vol_ratio_5 = vol_5_mean / vol_20_mean if vol_20_mean > 0 else 1.0
        vol_ratio_10 = vol_10_mean / vol_20_mean if vol_20_mean > 0 else 1.0
        
        if vol_ratio_5 > 2.0:
            score_vol_5 = 100
        elif vol_ratio_5 > 1.8:
            score_vol_5 = 90
        elif vol_ratio_5 > 1.5:
            score_vol_5 = 80
        elif vol_ratio_5 > 1.3:
            score_vol_5 = 70
        elif vol_ratio_5 > 1.1:
            score_vol_5 = 60
        elif vol_ratio_5 > 0.9:
            score_vol_5 = 50
        elif vol_ratio_5 > 0.7:
            score_vol_5 = 40
        elif vol_ratio_5 > 0.5:
            score_vol_5 = 30
        else:
            score_vol_5 = 20
        scores.append(score_vol_5 * 0.30)
        
        if vol_ratio_10 > 1.5:
            score_vol_10 = 100
        elif vol_ratio_10 > 1.3:
            score_vol_10 = 85
        elif vol_ratio_10 > 1.1:
            score_vol_10 = 70
        elif vol_ratio_10 > 0.9:
            score_vol_10 = 55
        elif vol_ratio_10 > 0.7:
            score_vol_10 = 40
        else:
            score_vol_10 = 25
        scores.append(score_vol_10 * 0.20)
        
        current_vs_avg = current_vol / avg_vol
        if current_vs_avg > 2.5:
            score_current = 100
        elif current_vs_avg > 2.0:
            score_current = 90
        elif current_vs_avg > 1.5:
            score_current = 75
        elif current_vs_avg > 1.2:
            score_current = 60
        elif current_vs_avg > 0.9:
            score_current = 50
        elif current_vs_avg > 0.7:
            score_current = 40
        elif current_vs_avg > 0.5:
            score_current = 30
        else:
            score_current = 20
        scores.append(score_current * 0.25)
        
        vol_5_recent = df.tail(5)['成交量']
        vol_trend = (vol_5_recent.iloc[-1] - vol_5_recent.iloc[0]) / vol_5_recent.iloc[0] * 100 if vol_5_recent.iloc[0] > 0 else 0
        
        if vol_trend > 50:
            score_trend = 100
        elif vol_trend > 30:
            score_trend = 85
        elif vol_trend > 15:
            score_trend = 70
        elif vol_trend > 5:
            score_trend = 60
        elif vol_trend > -5:
            score_trend = 50
        elif vol_trend > -15:
            score_trend = 40
        elif vol_trend > -30:
            score_trend = 30
        else:
            score_trend = 20
        scores.append(score_trend * 0.25)
        
        return sum(scores)
        
    except Exception as e:
        logger.warning(f"计算成交量得分失败: {e}")
        return 50.0

def calculate_technical_score(df: pd.DataFrame) -> float:
    if df is None or len(df) < 30:
        return 50.0
    
    try:
        scores = []
        
        close_prices = df['收盘']
        high_prices = df['最高']
        low_prices = df['最低']
        
        ma5 = close_prices.rolling(window=5).mean()
        ma10 = close_prices.rolling(window=10).mean()
        ma20 = close_prices.rolling(window=20).mean()
        ma60 = close_prices.rolling(window=60).mean() if len(df) >= 60 else ma20
        
        current_price = close_prices.iloc[-1]
        
        if pd.isna(ma5.iloc[-1]) or pd.isna(ma10.iloc[-1]) or pd.isna(ma20.iloc[-1]):
            return 50.0
        
        if current_price > ma5.iloc[-1] > ma10.iloc[-1] > ma20.iloc[-1]:
            score_ma = 100
        elif current_price > ma5.iloc[-1] > ma10.iloc[-1]:
            score_ma = 85
        elif ma5.iloc[-1] > ma10.iloc[-1] > ma20.iloc[-1]:
            score_ma = 75
        elif current_price > ma5.iloc[-1]:
            score_ma = 65
        elif ma5.iloc[-1] > ma10.iloc[-1]:
            score_ma = 55
        elif current_price > ma20.iloc[-1]:
            score_ma = 45
        else:
            score_ma = 30
        scores.append(score_ma * 0.20)
        
        ema12 = close_prices.ewm(span=12, adjust=False).mean()
        ema26 = close_prices.ewm(span=26, adjust=False).mean()
        dif = ema12 - ema26
        dea = dif.ewm(span=9, adjust=False).mean()
        macd_hist = dif - dea
        
        current_dif = dif.iloc[-1]
        current_dea = dea.iloc[-1]
        current_hist = macd_hist.iloc[-1]
        
        if current_dif > current_dea and current_hist > 0:
            if current_hist > current_hist.shift(1).iloc[-1]:
                score_macd = 100
            else:
                score_macd = 80
        elif current_dif > current_dea:
            score_macd = 70
        elif current_hist > 0:
            score_macd = 55
        elif current_hist > current_hist.shift(1).iloc[-1]:
            score_macd = 45
        else:
            score_macd = 30
        scores.append(score_macd * 0.20)
        
        delta = close_prices.diff()
        gain = delta.where(delta > 0, 0)
        loss = (-delta).where(delta < 0, 0)
        avg_gain = gain.rolling(window=14).mean()
        avg_loss = loss.rolling(window=14).mean()
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        current_rsi = rsi.iloc[-1]
        
        if current_rsi > 80:
            score_rsi = 100
        elif current_rsi > 70:
            score_rsi = 85
        elif current_rsi > 60:
            score_rsi = 70
        elif current_rsi > 50:
            score_rsi = 60
        elif current_rsi > 40:
            score_rsi = 50
        elif current_rsi > 30:
            score_rsi = 40
        elif current_rsi > 20:
            score_rsi = 30
        else:
            score_rsi = 20
        scores.append(score_rsi * 0.15)
        
        bb_middle = close_prices.rolling(window=20).mean()
        bb_std = close_prices.rolling(window=20).std()
        bb_upper = bb_middle + 2 * bb_std
        bb_lower = bb_middle - 2 * bb_std
        
        if pd.isna(bb_upper.iloc[-1]) or pd.isna(bb_lower.iloc[-1]):
            score_bb = 50
        else:
            bb_position = (current_price - bb_lower.iloc[-1]) / (bb_upper.iloc[-1] - bb_lower.iloc[-1])
            
            if bb_position > 0.9:
                score_bb = 100
            elif bb_position > 0.8:
                score_bb = 85
            elif bb_position > 0.6:
                score_bb = 70
            elif bb_position > 0.4:
                score_bb = 55
            elif bb_position > 0.2:
                score_bb = 45
            else:
                score_bb = 30
        scores.append(score_bb * 0.15)
        
        low_n = low_prices.rolling(window=9).min()
        high_n = high_prices.rolling(window=9).max()
        k_value = (close_prices - low_n) / (high_n - low_n) * 100
        
        current_k = k_value.iloc[-1]
        prev_k = k_value.iloc[-2] if len(k_value) >= 2 else current_k
        
        if current_k > 80:
            score_kdj = 100
        elif current_k > 70:
            score_kdj = 85
        elif current_k > 60:
            score_kdj = 70
        elif current_k > 50:
            score_kdj = 60
        elif current_k > 40:
            score_kdj = 50
        elif current_k > 30:
            score_kdj = 40
        elif current_k > 20:
            score_kdj = 30
        else:
            score_kdj = 20
        
        if current_k > prev_k and current_k < 80:
            score_kdj = min(score_kdj + 10, 100)
        
        scores.append(score_kdj * 0.15)
        
        tr1 = high_prices - low_prices
        tr2 = abs(high_prices - close_prices.shift(1))
        tr3 = abs(low_prices - close_prices.shift(1))
        tr = tr1.where(tr1 > tr2, tr2).where(tr1 > tr3, tr3)
        atr = tr.rolling(window=14).mean()
        
        current_atr = atr.iloc[-1]
        avg_atr = atr.mean()
        
        if avg_atr > 0:
            atr_ratio = current_atr / avg_atr
            if atr_ratio > 1.5:
                score_atr = 100
            elif atr_ratio > 1.3:
                score_atr = 85
            elif atr_ratio > 1.1:
                score_atr = 70
            elif atr_ratio > 0.9:
                score_atr = 55
            elif atr_ratio > 0.7:
                score_atr = 45
            else:
                score_atr = 35
        else:
            score_atr = 50
        scores.append(score_atr * 0.15)
        
        return sum(scores)
        
    except Exception as e:
        logger.warning(f"计算技术得分失败: {e}")
        return 50.0

def calculate_stock_score(stock_code: str, stock_name: str, sector: str, sector_sentiment: float) -> Dict:
    df = get_stock_data(stock_code)
    
    price_score = calculate_price_change_score(df)
    volume_score = calculate_volume_score(df)
    technical_score = calculate_technical_score(df)
    sentiment_score = sector_sentiment
    
    total_score = (
        price_score * 0.25 +
        volume_score * 0.20 +
        sentiment_score * 0.30 +
        technical_score * 0.25
    )
    
    reason_parts = []
    if price_score >= 65:
        reason_parts.append("价格走势强劲")
    elif price_score >= 55:
        reason_parts.append("价格趋势向好")
    
    if volume_score >= 65:
        reason_parts.append("成交量活跃")
    elif volume_score >= 55:
        reason_parts.append("成交量较大")
    
    if sentiment_score >= 75:
        reason_parts.append("板块热度高")
    elif sentiment_score >= 60:
        reason_parts.append("板块关注度较好")
    
    if technical_score >= 65:
        reason_parts.append("技术形态强势")
    elif technical_score >= 55:
        reason_parts.append("技术面支撑良好")
    
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
