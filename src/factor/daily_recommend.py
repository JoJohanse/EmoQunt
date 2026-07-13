import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import os
import csv
import json
import logging
import sys

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CSV_PATH = os.path.join(BASE_DIR, "stock_data", "沪深300", "沪深300成分股列表.csv")
INDUSTRY_PATH = os.path.join(BASE_DIR, "stock_data", "沪深300", "行业种类.txt")
CACHE_DIR = os.path.join(BASE_DIR, "stock_data", "stock_cache")

# 导入配置
sys.path.append(BASE_DIR)
from config.config_loader import get_config

_config = get_config()
SCORING_CONFIG = _config.load_scoring_config()

# 从配置中提取评分权重
COMPOSITE_WEIGHTS = SCORING_CONFIG.get('composite_weights', {})
PRICE_WEIGHT = COMPOSITE_WEIGHTS.get('price_score', 0.25)
VOLUME_WEIGHT = COMPOSITE_WEIGHTS.get('volume_score', 0.20)
SENTIMENT_WEIGHT = COMPOSITE_WEIGHTS.get('sentiment_score', 0.30)
TECHNICAL_WEIGHT = COMPOSITE_WEIGHTS.get('technical_score', 0.25)

# 从配置中提取评分阈值
RECOMMENDATION_THRESHOLDS = SCORING_CONFIG.get('recommendation_thresholds', {})
PRICE_HIGH_THRESHOLD = RECOMMENDATION_THRESHOLDS.get('price_score_high', 65)
PRICE_MEDIUM_THRESHOLD = RECOMMENDATION_THRESHOLDS.get('price_score_medium', 55)
VOLUME_HIGH_THRESHOLD = RECOMMENDATION_THRESHOLDS.get('volume_score_high', 65)
VOLUME_MEDIUM_THRESHOLD = RECOMMENDATION_THRESHOLDS.get('volume_score_medium', 55)
SENTIMENT_HIGH_THRESHOLD = RECOMMENDATION_THRESHOLDS.get('sentiment_score_high', 75)
SENTIMENT_MEDIUM_THRESHOLD = RECOMMENDATION_THRESHOLDS.get('sentiment_score_medium', 60)
TECHNICAL_HIGH_THRESHOLD = RECOMMENDATION_THRESHOLDS.get('technical_score_high', 65)
TECHNICAL_MEDIUM_THRESHOLD = RECOMMENDATION_THRESHOLDS.get('technical_score_medium', 55)

# 从配置中提取数据配置
DATA_CONFIG = SCORING_CONFIG.get('data_config', {})
MIN_DATA_DAYS = DATA_CONFIG.get('min_data_days', 30)
PRICE_CHANGE_DAYS = DATA_CONFIG.get('price_change_days', [5, 10, 20])
VOLUME_AVG_PERIODS = DATA_CONFIG.get('volume_avg_periods', [5, 10, 20])
MA_PERIODS = DATA_CONFIG.get('ma_periods', [5, 10, 20, 60])
RSI_PERIOD = DATA_CONFIG.get('rsi_period', 14)
MACD_PARAMS = DATA_CONFIG.get('macd_params', {'fast': 12, 'slow': 26, 'signal': 9})
BOLLINGER_PERIOD = DATA_CONFIG.get('bollinger_period', 20)
BOLLINGER_STD = DATA_CONFIG.get('bollinger_std', 2)
KDJ_PERIOD = DATA_CONFIG.get('kdj_period', 9)
ATR_PERIOD = DATA_CONFIG.get('atr_period', 14)

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
    except Exception:
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
        logger.warning(f"加载舆情结果失败: {e}")

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
    
    # 复用 src.data.data_manager 的 A 股回退链
    # (Tushare → akshare 新浪 → akshare 东财 → baostock)，避免本模块直接登 baostock 造成阻塞。
    try:
        from src.data.data_manager import Stock
        code = stock_code.split('.')[0]
        stock = Stock(code, market='zh_a')
        # 取 days×2 个日历日的数据，确保覆盖足够交易日（评分需 ~30 个交易日）
        end_date = datetime.now().strftime('%Y%m%d')
        start_date = (datetime.now() - timedelta(days=int(days * 2))).strftime('%Y%m%d')
        df, _ = stock.get_stock_data(start_date=start_date, end_date=end_date,
                                     adjust='qfq', type='daily')
        if df is None or df.empty:
            logger.warning(f"未获取到股票 {stock_code} 的数据（所有数据源均失败）")
            return None

        # 适配列契约：data_manager 返回 时间 为普通列，本模块的评分函数依赖 DatetimeIndex 升序
        if '时间' in df.columns:
            df['时间'] = pd.to_datetime(df['时间'])
            df = df.set_index('时间').sort_index()
        else:
            # 无时间列时，按现有顺序作为索引兜底
            df = df.sort_index()

        for col in ['开盘', '最高', '最低', '收盘', '成交量', '成交额']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')

        # 注：成交量单位差异（akshare 源为"手"，旧 baostock 为"股"）不影响评分，
        # 因为 calculate_volume_score 只用比值（5日/20日均量比），全局缩放因子抵消。

        STOCK_DATA_CACHE[stock_code] = df
        save_stock_data_to_cache(stock_code, df)
        return df.tail(days) if len(df) >= days else df

    except Exception as e:
        logger.warning(f"获取股票 {stock_code} 数据失败: {e}")
        return None


def _get_score_from_thresholds(value: float, thresholds: List[Dict]) -> int:
    """
    根据阈值列表获取评分
    
    :param value: 要评分的值
    :param thresholds: 阈值列表，每个元素包含 limit 和 score
    :return: 对应的评分
    """
    for threshold in thresholds:
        if value >= threshold['limit']:
            return threshold['score']
    return thresholds[-1]['score'] if thresholds else 50


def calculate_price_change_score(df: pd.DataFrame) -> float:
    """
    计算价格变化评分
    
    :param df: 股票数据DataFrame
    :return: 价格变化评分 (0-100)
    """
    if df is None or len(df) < 20:
        return 50.0
    
    try:
        scores = []
        price_config = SCORING_CONFIG.get('price_change_scoring', {})
        
        # 获取不同周期的数据
        recent_5 = df.tail(5)
        recent_10 = df.tail(10)
        recent_20 = df.tail(20) if len(df) >= 20 else df
        
        # 获取价格数据
        price_5_start = recent_5['收盘'].iloc[0]
        price_10_start = recent_10['收盘'].iloc[0]
        price_20_start = recent_20['收盘'].iloc[0]
        current_price = df['收盘'].iloc[-1]
        
        # 计算均线
        ma5 = recent_5['收盘'].mean()
        ma10 = recent_10['收盘'].mean()
        ma20 = recent_20['收盘'].mean()
        
        # 5日价格变化评分
        change_5d = (current_price - price_5_start) / price_5_start * 100 if price_5_start > 0 else 0
        change_5d_config = price_config.get('change_5d', {})
        change_5d_thresholds = change_5d_config.get('thresholds', [
            {'limit': 10, 'score': 100}, {'limit': 7, 'score': 90}, {'limit': 5, 'score': 80},
            {'limit': 3, 'score': 70}, {'limit': 1, 'score': 60}, {'limit': -1, 'score': 50},
            {'limit': -3, 'score': 40}, {'limit': -5, 'score': 30}, {'limit': -7, 'score': 20},
            {'limit': -999, 'score': 10}
        ])
        score_5d = _get_score_from_thresholds(change_5d, change_5d_thresholds)
        scores.append(score_5d * change_5d_config.get('weight', 0.35))
        
        # 10日价格变化评分
        change_10d = (current_price - price_10_start) / price_10_start * 100 if price_10_start > 0 else 0
        change_10d_config = price_config.get('change_10d', {})
        change_10d_thresholds = change_10d_config.get('thresholds', [
            {'limit': 15, 'score': 100}, {'limit': 10, 'score': 85}, {'limit': 5, 'score': 70},
            {'limit': 0, 'score': 55}, {'limit': -5, 'score': 40}, {'limit': -10, 'score': 25},
            {'limit': -999, 'score': 10}
        ])
        score_10d = _get_score_from_thresholds(change_10d, change_10d_thresholds)
        scores.append(score_10d * change_10d_config.get('weight', 0.25))
        
        # 20日价格变化评分
        change_20d = (current_price - price_20_start) / price_20_start * 100 if price_20_start > 0 else 0
        change_20d_config = price_config.get('change_20d', {})
        change_20d_thresholds = change_20d_config.get('thresholds', [
            {'limit': 20, 'score': 100}, {'limit': 15, 'score': 85}, {'limit': 10, 'score': 70},
            {'limit': 5, 'score': 55}, {'limit': 0, 'score': 45}, {'limit': -5, 'score': 35},
            {'limit': -10, 'score': 25}, {'limit': -999, 'score': 10}
        ])
        score_20d = _get_score_from_thresholds(change_20d, change_20d_thresholds)
        scores.append(score_20d * change_20d_config.get('weight', 0.20))
        
        # 均线趋势评分
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
        
        ma_trend_config = price_config.get('ma_trend', {})
        scores.append(trend_score * ma_trend_config.get('weight', 0.20))
        
        return sum(scores)
        
    except Exception as e:
        logger.warning(f"计算价格变化得分失败: {e}")
        return 50.0


def calculate_volume_score(df: pd.DataFrame) -> float:
    """
    计算成交量评分
    
    :param df: 股票数据DataFrame
    :return: 成交量评分 (0-100)
    """
    if df is None or len(df) < 20:
        return 50.0
    
    try:
        scores = []
        volume_config = SCORING_CONFIG.get('volume_scoring', {})
        
        # 获取不同周期的成交量数据
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
        
        # 5日均量/20日均量比率评分
        vol_ratio_5 = vol_5_mean / vol_20_mean if vol_20_mean > 0 else 1.0
        vol_ratio_5_config = volume_config.get('vol_ratio_5', {})
        vol_ratio_5_thresholds = vol_ratio_5_config.get('thresholds', [
            {'limit': 2.0, 'score': 100}, {'limit': 1.8, 'score': 90}, {'limit': 1.5, 'score': 80},
            {'limit': 1.3, 'score': 70}, {'limit': 1.1, 'score': 60}, {'limit': 0.9, 'score': 50},
            {'limit': 0.7, 'score': 40}, {'limit': 0.5, 'score': 30}, {'limit': -999, 'score': 20}
        ])
        score_vol_5 = _get_score_from_thresholds(vol_ratio_5, vol_ratio_5_thresholds)
        scores.append(score_vol_5 * vol_ratio_5_config.get('weight', 0.30))
        
        # 10日均量/20日均量比率评分
        vol_ratio_10 = vol_10_mean / vol_20_mean if vol_20_mean > 0 else 1.0
        vol_ratio_10_config = volume_config.get('vol_ratio_10', {})
        vol_ratio_10_thresholds = vol_ratio_10_config.get('thresholds', [
            {'limit': 1.5, 'score': 100}, {'limit': 1.3, 'score': 85}, {'limit': 1.1, 'score': 70},
            {'limit': 0.9, 'score': 55}, {'limit': 0.7, 'score': 40}, {'limit': -999, 'score': 25}
        ])
        score_vol_10 = _get_score_from_thresholds(vol_ratio_10, vol_ratio_10_thresholds)
        scores.append(score_vol_10 * vol_ratio_10_config.get('weight', 0.20))
        
        # 当前成交量/平均成交量比率评分
        current_vs_avg = current_vol / avg_vol
        current_vs_avg_config = volume_config.get('current_vs_avg', {})
        current_vs_avg_thresholds = current_vs_avg_config.get('thresholds', [
            {'limit': 2.5, 'score': 100}, {'limit': 2.0, 'score': 90}, {'limit': 1.5, 'score': 75},
            {'limit': 1.2, 'score': 60}, {'limit': 0.9, 'score': 50}, {'limit': 0.7, 'score': 40},
            {'limit': 0.5, 'score': 30}, {'limit': -999, 'score': 20}
        ])
        score_current = _get_score_from_thresholds(current_vs_avg, current_vs_avg_thresholds)
        scores.append(score_current * current_vs_avg_config.get('weight', 0.25))
        
        # 成交量趋势评分
        vol_5_recent = df.tail(5)['成交量']
        vol_trend = ((vol_5_recent.iloc[-1] - vol_5_recent.iloc[0]) / vol_5_recent.iloc[0] * 100 
                     if vol_5_recent.iloc[0] > 0 else 0)
        
        vol_trend_config = volume_config.get('vol_trend', {})
        vol_trend_thresholds = vol_trend_config.get('thresholds', [
            {'limit': 50, 'score': 100}, {'limit': 30, 'score': 85}, {'limit': 15, 'score': 70},
            {'limit': 5, 'score': 60}, {'limit': -5, 'score': 50}, {'limit': -15, 'score': 40},
            {'limit': -30, 'score': 30}, {'limit': -999, 'score': 20}
        ])
        score_trend = _get_score_from_thresholds(vol_trend, vol_trend_thresholds)
        scores.append(score_trend * vol_trend_config.get('weight', 0.25))
        
        return sum(scores)
        
    except Exception as e:
        logger.warning(f"计算成交量得分失败: {e}")
        return 50.0


def calculate_technical_score(df: pd.DataFrame) -> float:
    """
    计算技术指标评分
    
    :param df: 股票数据DataFrame
    :return: 技术指标评分 (0-100)
    """
    if df is None or len(df) < MIN_DATA_DAYS:
        return 50.0
    
    try:
        scores = []
        technical_config = SCORING_CONFIG.get('technical_scoring', {})
        
        close_prices = df['收盘']
        high_prices = df['最高']
        low_prices = df['最低']
        
        # 计算均线
        ma_periods = MA_PERIODS
        ma5 = close_prices.rolling(window=ma_periods[0]).mean()
        ma10 = close_prices.rolling(window=ma_periods[1]).mean()
        ma20 = close_prices.rolling(window=ma_periods[2]).mean()
        ma60 = close_prices.rolling(window=ma_periods[3]).mean() if len(df) >= ma_periods[3] else ma20
        
        current_price = close_prices.iloc[-1]
        
        if pd.isna(ma5.iloc[-1]) or pd.isna(ma10.iloc[-1]) or pd.isna(ma20.iloc[-1]):
            return 50.0
        
        # 均线系统评分
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
        
        ma_system_config = technical_config.get('ma_system', {})
        scores.append(score_ma * ma_system_config.get('weight', 0.20))
        
        # MACD评分
        macd_params = MACD_PARAMS
        ema12 = close_prices.ewm(span=macd_params['fast'], adjust=False).mean()
        ema26 = close_prices.ewm(span=macd_params['slow'], adjust=False).mean()
        dif = ema12 - ema26
        dea = dif.ewm(span=macd_params['signal'], adjust=False).mean()
        macd_hist = dif - dea
        
        current_dif = dif.iloc[-1]
        current_dea = dea.iloc[-1]
        current_hist = macd_hist.iloc[-1]
        prev_hist = macd_hist.iloc[-2] if len(macd_hist) >= 2 else current_hist
        
        if current_dif > current_dea and current_hist > 0:
            if current_hist > prev_hist:
                score_macd = 100
            else:
                score_macd = 80
        elif current_dif > current_dea:
            score_macd = 70
        elif current_hist > 0:
            score_macd = 55
        elif current_hist > prev_hist:
            score_macd = 45
        else:
            score_macd = 30
        
        macd_config = technical_config.get('macd', {})
        scores.append(score_macd * macd_config.get('weight', 0.20))
        
        # RSI评分
        rsi_period = RSI_PERIOD
        delta = close_prices.diff()
        gain = delta.where(delta > 0, 0)
        loss = (-delta).where(delta < 0, 0)
        avg_gain = gain.rolling(window=rsi_period).mean()
        avg_loss = loss.rolling(window=rsi_period).mean()
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        current_rsi = rsi.iloc[-1]
        
        rsi_config = technical_config.get('rsi', {})
        rsi_thresholds = rsi_config.get('thresholds', [
            {'limit': 80, 'score': 100}, {'limit': 70, 'score': 85}, {'limit': 60, 'score': 70},
            {'limit': 50, 'score': 60}, {'limit': 40, 'score': 50}, {'limit': 30, 'score': 40},
            {'limit': 20, 'score': 30}, {'limit': -999, 'score': 20}
        ])
        score_rsi = _get_score_from_thresholds(current_rsi, rsi_thresholds)
        scores.append(score_rsi * rsi_config.get('weight', 0.15))
        
        # 布林带评分
        bb_period = BOLLINGER_PERIOD
        bb_std = BOLLINGER_STD
        bb_middle = close_prices.rolling(window=bb_period).mean()
        bb_std_val = close_prices.rolling(window=bb_period).std()
        bb_upper = bb_middle + bb_std * bb_std_val
        bb_lower = bb_middle - bb_std * bb_std_val
        
        if pd.isna(bb_upper.iloc[-1]) or pd.isna(bb_lower.iloc[-1]):
            score_bb = 50
        else:
            bb_range = bb_upper.iloc[-1] - bb_lower.iloc[-1]
            if bb_range > 0:
                bb_position = (current_price - bb_lower.iloc[-1]) / bb_range
            else:
                bb_position = 0.5
            
            bollinger_config = technical_config.get('bollinger', {})
            bollinger_thresholds = bollinger_config.get('thresholds', [
                {'limit': 0.9, 'score': 100}, {'limit': 0.8, 'score': 85}, {'limit': 0.6, 'score': 70},
                {'limit': 0.4, 'score': 55}, {'limit': 0.2, 'score': 45}, {'limit': -999, 'score': 30}
            ])
            score_bb = _get_score_from_thresholds(bb_position, bollinger_thresholds)
        
        scores.append(score_bb * technical_config.get('bollinger', {}).get('weight', 0.15))
        
        # KDJ评分
        kdj_period = KDJ_PERIOD
        low_n = low_prices.rolling(window=kdj_period).min()
        high_n = high_prices.rolling(window=kdj_period).max()
        k_value = (close_prices - low_n) / (high_n - low_n) * 100
        
        current_k = k_value.iloc[-1]
        prev_k = k_value.iloc[-2] if len(k_value) >= 2 else current_k
        
        kdj_config = technical_config.get('kdj', {})
        kdj_thresholds = kdj_config.get('thresholds', [
            {'limit': 80, 'score': 100}, {'limit': 70, 'score': 85}, {'limit': 60, 'score': 70},
            {'limit': 50, 'score': 60}, {'limit': 40, 'score': 50}, {'limit': 30, 'score': 40},
            {'limit': 20, 'score': 30}, {'limit': -999, 'score': 20}
        ])
        score_kdj = _get_score_from_thresholds(current_k, kdj_thresholds)
        
        # K值上升且未超买时加分
        if current_k > prev_k and current_k < 80:
            bonus = kdj_config.get('bonus', {}).get('increasing_not_overbought', 10)
            score_kdj = min(score_kdj + bonus, 100)
        
        scores.append(score_kdj * kdj_config.get('weight', 0.15))
        
        # ATR评分
        atr_period = ATR_PERIOD
        tr1 = high_prices - low_prices
        tr2 = abs(high_prices - close_prices.shift(1))
        tr3 = abs(low_prices - close_prices.shift(1))
        tr = tr1.where(tr1 > tr2, tr2).where(tr1 > tr3, tr3)
        atr = tr.rolling(window=atr_period).mean()
        
        current_atr = atr.iloc[-1]
        avg_atr = atr.mean()
        
        if avg_atr > 0:
            atr_ratio = current_atr / avg_atr
            atr_config = technical_config.get('atr', {})
            atr_thresholds = atr_config.get('thresholds', [
                {'limit': 1.5, 'score': 100}, {'limit': 1.3, 'score': 85}, {'limit': 1.1, 'score': 70},
                {'limit': 0.9, 'score': 55}, {'limit': 0.7, 'score': 45}, {'limit': -999, 'score': 35}
            ])
            score_atr = _get_score_from_thresholds(atr_ratio, atr_thresholds)
        else:
            score_atr = 50
        
        scores.append(score_atr * technical_config.get('atr', {}).get('weight', 0.15))
        
        return sum(scores)
        
    except Exception as e:
        logger.warning(f"计算技术得分失败: {e}")
        return 50.0


def calculate_stock_score(stock_code: str, stock_name: str, sector: str, sector_sentiment: float) -> Dict:
    """
    计算股票综合评分
    
    :param stock_code: 股票代码
    :param stock_name: 股票名称
    :param sector: 所属行业
    :param sector_sentiment: 行业舆情得分
    :return: 股票评分结果字典
    """
    df = get_stock_data(stock_code)
    
    price_score = calculate_price_change_score(df)
    volume_score = calculate_volume_score(df)
    technical_score = calculate_technical_score(df)
    sentiment_score = sector_sentiment
    
    # 使用配置中的权重计算综合得分
    total_score = (
        price_score * PRICE_WEIGHT +
        volume_score * VOLUME_WEIGHT +
        sentiment_score * SENTIMENT_WEIGHT +
        technical_score * TECHNICAL_WEIGHT
    )
    
    # 生成推荐理由
    reason_parts = []
    if price_score >= PRICE_HIGH_THRESHOLD:
        reason_parts.append("价格走势强劲")
    elif price_score >= PRICE_MEDIUM_THRESHOLD:
        reason_parts.append("价格趋势向好")
    
    if volume_score >= VOLUME_HIGH_THRESHOLD:
        reason_parts.append("成交量活跃")
    elif volume_score >= VOLUME_MEDIUM_THRESHOLD:
        reason_parts.append("成交量较大")
    
    if sentiment_score >= SENTIMENT_HIGH_THRESHOLD:
        reason_parts.append("板块热度高")
    elif sentiment_score >= SENTIMENT_MEDIUM_THRESHOLD:
        reason_parts.append("板块关注度较好")
    
    if technical_score >= TECHNICAL_HIGH_THRESHOLD:
        reason_parts.append("技术形态强势")
    elif technical_score >= TECHNICAL_MEDIUM_THRESHOLD:
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
    """
    生成每日股票推荐
    
    :param n: 推荐股票数量
    :return: 推荐结果字典
    """
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
