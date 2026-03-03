import pandas as pd
import os
import re

def main():
    # 1. 读取沪深300成分股列表CSV文件
    csv_path = 'd:/workplace/codeplace/junkcode/Qdt_test/stock_data/沪深300/沪深300成分股列表.csv'
    df = pd.read_csv(csv_path)
    
    # 处理股票代码，确保是6位数字格式
    hs300_stocks = []
    for code in df['股票代码']:
        code_str = str(code)
        # 确保是6位数字
        if len(code_str) < 6:
            code_str = code_str.zfill(6)
        hs300_stocks.append(code_str)
    
    print(f'沪深300成分股总数: {len(hs300_stocks)}')
    
    # 2. 获取stock_data/zh_a/目录下的所有股票代码
    zh_a_path = 'd:/workplace/codeplace/junkcode/Qdt_test/stock_data/zh_a'
    existing_stocks = [d for d in os.listdir(zh_a_path) if os.path.isdir(os.path.join(zh_a_path, d)) and d.isdigit()]
    
    print(f'stock_data/zh_a/目录下的股票代码总数: {len(existing_stocks)}')
    
    # 3. 对比两个列表，找出缺失的股票代码
    hs300_set = set(hs300_stocks)
    existing_set = set(existing_stocks)
    
    # 找出在沪深300列表中但不在现有目录中的股票
    missing_stocks = sorted(list(hs300_set - existing_set))
    
    # 找出在现有目录中但不在沪深300列表中的股票
    extra_stocks = sorted(list(existing_set - hs300_set))
    
    print(f'\n缺失的股票代码数量: {len(missing_stocks)}')
    if missing_stocks:
        print('缺失的股票代码:')
        for stock in missing_stocks:
            print(f'  {stock}')
    
    print(f'\n多余的股票代码数量: {len(extra_stocks)}')
    if extra_stocks:
        print('多余的股票代码:')
        for stock in extra_stocks[:10]:  # 只显示前10个
            print(f'  {stock}')
        if len(extra_stocks) > 10:
            print(f'  ... 还有 {len(extra_stocks) - 10} 个多余股票')
    
    # 4. 保存缺失的股票列表到文件
    if missing_stocks:
        missing_path = 'd:/workplace/codeplace/junkcode/Qdt_test/missing_stocks.txt'
        with open(missing_path, 'w') as f:
            for stock in missing_stocks:
                f.write(f'{stock}\n')
        print(f'\n缺失的股票列表已保存到: {missing_path}')
    
    # 5. 检查是否有重复的股票代码
    duplicates = [code for code in set(hs300_stocks) if hs300_stocks.count(code) > 1]
    if duplicates:
        print(f'\n沪深300列表中重复的股票代码: {duplicates}')

if __name__ == '__main__':
    main()