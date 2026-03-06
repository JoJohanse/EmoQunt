import os

# 提取'沪深300成分股列表.csv'中出现的行业种类（去重）
def extract_sectors_from_csv(csv_file_path: str) -> list[str]:
    """
    从CSV文件中提取行业种类（去重）
    '''
    股票代码,股票简称,行业
    601298,青岛港,航运港口
    '''
    :param csv_file_path: CSV文件路径
    :return: 行业种类列表（去重）
    """
    sectors = set()
    with open(csv_file_path, 'r', encoding='utf-8') as file:
        for line in file:
            line = line.strip()
            if line:
                _, _, sector = line.split(',')
                sectors.add(sector)
    return list(sectors)    

if __name__ == '__main__':
    csv_file_path = 'stock_data\沪深300\沪深300成分股列表.csv'
    sectors = extract_sectors_from_csv(csv_file_path)
    # 统计行业种类数量
    print(f'行业种类数量: {len(sectors)}')
    # 保存
    with open('stock_data\沪深300\行业种类.txt', 'w', encoding='utf-8') as file:
        for sector in sectors:
            file.write(sector + '\n')
