import akshare as ak
import pandas as pd
import os
import time

# 导入沪深300股票列表
stock_list_file = r'D:\workplace\codeplace\junkcode\Qdt_test\stock_data\沪深300'
stock_list = os.path.join(stock_list_file, '沪深300成分股列表_cleaned.csv')
# 读取CSV文件时将股票代码列指定为字符串类型，避免前导零丢失
df_stock_list = pd.read_csv(stock_list, dtype={'股票代码': str})

# 获取股票行业信息
'''
    code_name_map = {
        "f57": "股票代码",
        "f58": "股票简称",
        "f84": "总股本",
        "f85": "流通股",
        "f127": "行业",
        "f116": "总市值",
        "f117": "流通市值",
        "f189": "上市时间",
        "f43": "最新",
    }
'''
for i, stock_code in enumerate(df_stock_list['股票代码']):
    # 从第250个股票开始获取行业信息
    if i < 250:
        continue
    stock_info = ak.stock_individual_info_em(symbol=stock_code)
    stock_industry = stock_info[stock_info['item'] == '行业']['value'].values[0]
    stock_name = stock_info[stock_info['item'] == '股票简称']['value'].values[0]
    # 仅将行业和股票简称加入新列，其他列保持不变
    df_stock_list.loc[i, '股票简称'] = stock_name
    df_stock_list.loc[i, '行业'] = stock_industry

    # 打印进度
    print(f'已处理股票代码: {stock_code}，所属行业: {stock_industry}，当前进度: {i + 1}/{len(df_stock_list)}')
    # 暂停1秒，避免频繁请求
    time.sleep(2)

    # 每50个股票保存一次
    if (i + 1) % 50 == 0:
        df_stock_list.to_csv(os.path.join(stock_list_file, '沪深300成分股列表_行业.csv'), index=False, encoding='utf-8')
        print(f'已保存 {i + 1} 条股票数据')

# 保存最终结果
df_stock_list.to_csv(os.path.join(stock_list_file, '沪深300成分股列表_行业.csv'), index=False, encoding='utf-8')
