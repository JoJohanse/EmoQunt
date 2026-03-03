from akshare.stock_feature.stock_zh_valuation_baidu import stock_zh_valuation_baidu
import os
import time
import pandas as pd

# 获取股票的总市值（目前仅支持a股）
def get_market_value(stock_code,period='近五年',market='zh_a'):
    if isinstance(stock_code, int):
        stock_code = str(stock_code).zfill(6)
    save_dir = fr'Qdt_test\stock_data\{market}\{stock_code}'
    # 先检查是否存在文件
    file_path = os.path.join(save_dir, f'{stock_code}_{period}市值变化.csv')
    if os.path.exists(file_path):
        print(f"文件已存在：{file_path}")
        return pd.read_csv(file_path)
    df = pd.DataFrame()
    for indicator in ["总市值", "市盈率(TTM)", "市盈率(静)", "市净率", "市现率"]:
        df_indicator = stock_zh_valuation_baidu(symbol=stock_code, indicator=indicator, period=period)
        # 将value列重命名为对应的指标名
        df_indicator = df_indicator.rename(columns={'value': indicator})
        if df.empty:
            df = df_indicator
        else:
            # 基于date列合并数据
            df = pd.merge(df, df_indicator, on='date', how='outer')
    # 存入对应路径
    if not os.path.exists(save_dir):
        os.makedirs(save_dir)
    df.to_csv(os.path.join(save_dir, f'{stock_code}_{period}市值变化.csv'), index=False)
    return df