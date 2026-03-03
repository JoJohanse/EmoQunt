# 计算每只股票历史数据（日线）的基础技术指标：MA, MACD, RSI等
import akshare as ak
import pandas as pd
import numpy as np
import os

# 数据路径： Qdt_test\stock_data\zh_a\000001\hfq\daily\000001_hfq_daily_20200101_20241231.csv
# 000001 股票代码;hfq 复权类型，hfq-后复权，nfq-不复权，qfq-前复权;daily 数据类型，daily-日线;20200101 开始日期;20241231 结束日期

def calculate_factor(stock_code, datatype='daily',fq='hfq',market='zh_a'):
    """
    计算股票的因子值 ma-均线，macd-移动平均线差，rsi-相对强弱指标
    :param stock_code: 股票代码
    :param datatype: 数据类型，默认为'daily'（日线）
    :param fq: 复权类型，默认为'hfq'（后复权）
    :return: 包含因子值的DataFrame
    """
    # 读取股票数据
    # 字符化代码若code为int类型，若已经为str类型，直接使用
    if isinstance(stock_code, int):
        stock_code = str(stock_code).zfill(6)
    stock_data_path = r'Qdt_test\stock_data\{market}'.format(market=market)
    stock_path = os.path.join(stock_data_path, stock_code, fq, datatype)
    stock_data_file = os.path.join(stock_path, os.listdir(stock_path)[0])
    df = pd.read_csv(stock_data_file)
    if datatype == 'daily':
        # daily
        '''
        时间,开盘,最高,最低,收盘,成交量,成交额,流通股数,换手率
        2020-01-02,1971.89,2007.42,1960.04,1997.94,153023187.0,2571196482.0,19405752680.0,0.0078854548712098
        '''
        # 计算均线
        df['ma5(五日均线)'] = df['收盘'].rolling(window=5).mean()
        df['ma10(十日均线)'] = df['收盘'].rolling(window=10).mean()
        df['ma20(二十日均线)'] = df['收盘'].rolling(window=20).mean()
        # 计算RSI
        # 1. 计算每日收盘价的变动额
        delta = df['收盘'].diff()
        # 2. 分离上涨和下跌的变动额
        gain = np.where(delta > 0, delta, 0)
        loss = np.where(delta < 0, -delta, 0)
        # 3. 计算平均上涨和平均下跌
        avg_gain = pd.Series(gain).rolling(window=14).mean()
        avg_loss = pd.Series(loss).rolling(window=14).mean()
        # 4. 计算RS和RSI
        rs = avg_gain / avg_loss
        df['rsi(相对强弱指标)'] = 100 - (100 / (1 + rs))
        # 计算MACD指标
        # 1. 计算12日和26日EMA
        ema12 = df['收盘'].ewm(span=12, adjust=False).mean()
        ema26 = df['收盘'].ewm(span=26, adjust=False).mean()
        # 2. 计算DIF (差离值)
        df['dif(差离值)'] = ema12 - ema26
        # 3. 计算DEA (异同平均数)
        df['dea(异同平均数)'] = df['dif(差离值)'].ewm(span=9, adjust=False).mean()
        # 4. 计算MACD柱状图
        df['macd_hist(柱状图)'] = df['dif(差离值)'] - df['dea(异同平均数)']
        # 计算K线
        df['k值'] = (df['收盘'] - df['最低']) / (df['最高'] - df['最低'])
        # 计算ATR
        # 1. 计算真实范围(True Range)
        df['tr1'] = df['最高'] - df['最低']
        df['tr2'] = abs(df['最高'] - df['收盘'].shift(1))
        df['tr3'] = abs(df['最低'] - df['收盘'].shift(1))
        df['tr(真实范围)'] = df[['tr1', 'tr2', 'tr3']].max(axis=1)
        # 2. 计算平均真实范围(ATR)
        df['atr(平均真实价格波幅)'] = df['tr(真实范围)'].rolling(window=14).mean()
        # 清理临时列
        df.drop(['tr1', 'tr2', 'tr3', 'tr(真实范围)'], axis=1, inplace=True)
        # 保留需要的列
        keep_columns = ['时间', '开盘', '最高', '最低', '收盘', '成交量', 
                        'ma5(五日均线)', 'ma10(十日均线)', 'ma20(二十日均线)',
                        'rsi(相对强弱指标)','dif(差离值)', 'dea(异同平均数)',
                        'macd_hist(柱状图)','k值','atr(平均真实价格波幅)']
        df = df[keep_columns]

    elif datatype == 'minute':
        # minute
        '''
        时间,开盘,最高,最低,收盘,成交量
        2025-11-20 13:53:00,1730.659240506329,1732.118481012658,1730.659240506329,1730.659240506329,365100
        '''
        # 使用短期指标
        # 1. 短期均线（适合分钟级的短期均线）
        df['ma3(三分钟均线)'] = df['收盘'].rolling(window=3).mean()
        df['ma5(五分钟均线)'] = df['收盘'].rolling(window=5).mean()
        df['ma10(十分钟均线)'] = df['收盘'].rolling(window=10).mean()
        
        # 2. 布林带指标（Bollinger Bands）
        bb_window = 20
        df['bb_middle(布林带中线)'] = df['收盘'].rolling(window=bb_window).mean()
        df['bb_std(布林带标准差)'] = df['收盘'].rolling(window=bb_window).std()
        df['bb_upper(布林带上限)'] = df['bb_middle(布林带中线)'] + 2 * df['bb_std(布林带标准差)']
        df['bb_lower(布林带下限)'] = df['bb_middle(布林带中线)'] - 2 * df['bb_std(布林带标准差)']
        
        # 3. 成交量加权平均价（VWAP）- 日内交易重要指标
        df['vwap(成交量加权平均价)'] = (df['成交量'].cumsum() * df['收盘'].cumsum()) / df['成交量'].cumsum()
        
        # 4. 短期RSI（相对强弱指标）
        delta = df['收盘'].diff()
        gain = np.where(delta > 0, delta, 0)
        loss = np.where(delta < 0, -delta, 0)
        avg_gain = pd.Series(gain).rolling(window=6).mean()  # 短期RSI常用6或9周期
        avg_loss = pd.Series(loss).rolling(window=6).mean()
        rs = avg_gain / avg_loss
        df['rsi_6(短期相对强弱指标)'] = 100 - (100 / (1 + rs))
        
        # 5. 短期MACD指标
        ema5 = df['收盘'].ewm(span=5, adjust=False).mean()
        ema13 = df['收盘'].ewm(span=13, adjust=False).mean()
        df['dif_short(短期差离值)'] = ema5 - ema13
        df['dea_short(短期异同平均数)'] = df['dif_short(短期差离值)'].ewm(span=6, adjust=False).mean()
        df['macd_short_hist(短期柱状图)'] = df['dif_short(短期差离值)'] - df['dea_short(短期异同平均数)']
        
        # 6. 随机指标（KDJ）
        low_min = df['最低'].rolling(window=9).min()
        high_max = df['最高'].rolling(window=9).max()
        df['k值'] = (df['收盘'] - low_min) / (high_max - low_min) * 100
        
        # 7. 平均真实波动范围（ATR）- 衡量波动率
        df['tr1'] = df['最高'] - df['最低']
        df['tr2'] = abs(df['最高'] - df['收盘'].shift(1))
        df['tr3'] = abs(df['最低'] - df['收盘'].shift(1))
        df['tr'] = df[['tr1', 'tr2', 'tr3']].max(axis=1)
        df['atr(平均真实价格波幅)'] = df['tr'].rolling(window=14).mean()
        
        # 8. 价格动量指标（Momentum）
        df['momentum(价格动量指标)'] = df['收盘'] - df['收盘'].shift(4)
        # 保留需要的列
        keep_columns = ['时间', '开盘', '最高', '最低', '收盘', '成交量', 
                        'ma3(三分钟均线)', 'ma5(五分钟均线)', 'ma10(十分钟均线)',
                        'bb_upper(布林带上限)', 'bb_lower(布林带下限)',
                        'vwap(成交量加权平均价)', 'rsi_6(短期相对强弱指标)',
                        'macd_short_hist(短期柱状图)',
                        'k值', 'atr(平均真实价格波幅)', 'momentum(价格动量指标)']
        df = df[keep_columns]

    # 写入新的csv文件
    new_csv_file = os.path.join(stock_path, f'{stock_code}_{fq}_{datatype}_factor.csv')
    df.to_csv(new_csv_file, index=False)
    return df