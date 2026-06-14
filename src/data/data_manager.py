import akshare as ak
import pandas as pd
import re
import os
import traceback
from datetime import datetime

class Stock:
    def __init__(self, stock_code, market='zh_a'):
        """
        初始化Stock类
        :param stock_code: 股票代码
        :param market: 股票市场: 默认A股
        """
        self.stock_code = stock_code
        self.market = market
        
        # 为中国A股股票代码添加市场前缀
        if self.market == 'zh_a':
            # 若不是字符串类型，转换为字符串
            if not isinstance(self.stock_code, str):
                self.stock_code = str(self.stock_code)
                # 若转换后股票代码长度不是6位，添加前导0
                self.stock_code = self.stock_code.zfill(6)
            # 检查股票代码是否已经带有前缀
            if not (self.stock_code.startswith('sh') or self.stock_code.startswith('sz')):
                # 根据股票代码添加前缀
                # 上海证券交易所：6开头的股票代码
                # 深圳证券交易所：0或3开头的股票代码
                if len(self.stock_code) == 6:
                    if self.stock_code.startswith('6'):
                        self.stock_code = 'sh' + self.stock_code
                    elif self.stock_code.startswith(('0', '3')):
                        self.stock_code = 'sz' + self.stock_code
                    else:
                        print(f"警告：股票代码{self.stock_code}可能不是有效的A股代码")
        
        self.stock_name = ''
        # 设置股票数据目录
        self.stock_data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'stock_data', self.market)
    
    def get_code_without_prefix(self):
        """
        获取不带市场前缀的股票代码
        :return: 不带前缀的股票代码
        """
        if self.stock_code.startswith('sh') or self.stock_code.startswith('sz'):
            return self.stock_code[2:]
        return self.stock_code

    def get_stock_name(self):
        """
        先查找本地股票数据文件， 若不存在则使用akshare获取
        """
        try:
            # 检查本地股票数据文件是否存在
            file_path = os.path.join(self.stock_data_dir,'stocks.csv')
            if os.path.exists(file_path):
                # 读取本地股票数据文件
                name_list = pd.read_csv(file_path)
                # 查找匹配的股票名称
                stock_name = name_list[name_list['code'] == self.stock_code]
                if not stock_name.empty:
                    return stock_name.iloc[0]['name']
                else:
                    return None
            else:
                # 使用akshare获取股票代码和名称的映射
                stock_code_name = ak.stock_info_a_code_name()
                # 保存到本地文件
                stock_code_name.to_csv(file_path, index=False)
        except Exception as e:
            print(f"获取股票名称失败: {e}")
            return None
    
    def get_stock_data(self, start_date='', end_date=None, adjust='nfq', type='daily', period='1') -> tuple[pd.DataFrame, str]:
        """
        先查找本地股票数据文件， 若不存在则使用akshare获取
        使用akshare获取股票历史数据（支持日线和分钟级数据）
        :param start_date: 开始日期，格式为'YYYYMMDD'（仅日线数据有效）
        :param end_date: 结束日期，格式为'YYYYMMDD'，默认使用当前日期（仅日线数据有效）
        :param adjust: 复权类型，可选值为：默认'nfq'(不复权), 'qfq'(前复权), 'hfq'(后复权)
        :param type: 数据类型，可选值为：'daily'(日线数据), 'minute'(分钟级数据)
        :param period: 数据周期，可选值为：'1', '5', '15', '30', '60' 分钟的数据 (仅分钟级数据有效)
        :return: 股票历史数据DataFrame, 保存的数据文件名
        """
        try:
            # 检查本地股票数据文件是否存在
            # 两种情况，daily和minute
            # 1. sz000001_hfq_minute.csv 这是分钟级，文件名无日期范围
            # 2. sz000001_hfq_daily_210104_241231.csv 这是日线级，文件名包含日期范围
            # 构建文件路径
            code_without_prefix = self.get_code_without_prefix()
            if type == 'daily':
                file_name = f"{code_without_prefix}_{adjust}_{type}_{start_date}_{end_date}.csv"
            elif type == 'minute':
                file_name = f"{code_without_prefix}_{adjust}_{type}.csv"
            file_path = os.path.join(self.stock_data_dir, code_without_prefix, adjust, type, file_name)

            if os.path.exists(file_path):
                # 读取本地股票数据文件
                stock_data = pd.read_csv(file_path)
                return stock_data, file_name
            else:
                # 定义复权类型映射
                adjust_map = {
                    'nfq': '',
                    'qfq': 'qfq',
                    'hfq': 'hfq'
                }
                
                if type == 'daily':
                    # 获取日线数据
                    if end_date is None:
                        # 使用当前日期作为结束日期
                        end_date = datetime.now().strftime('%Y%m%d')
                    print(f"正在获取{self.stock_code}的历史数据（日线），日期范围: {start_date}至{end_date}")
                    stock_data = ak.stock_zh_a_daily(
                        symbol=self.stock_code,
                        start_date=start_date,
                        end_date=end_date,
                        adjust=adjust_map[adjust]
                    )
                elif type == 'minute':
                    # 获取分钟级数据
                    print(f"正在获取{self.stock_code}的历史数据（分钟级）")
                    stock_data = ak.stock_zh_a_minute(
                        symbol=self.stock_code,
                        period=period,
                        adjust=adjust_map[adjust]
                    )
                else:
                    # 处理无效的type参数
                    print(f"错误：无效的数据类型 {type}，请使用 'daily' 或 'minute'")
                    return pd.DataFrame(), ''
            
            # 检查返回的数据是否为空
            if stock_data is None or stock_data.empty:
                print(f"akshare返回空数据，检查股票代码或日期范围")
                return pd.DataFrame(), ''
            
            print(f"成功获取数据，数据行数: {len(stock_data)}")
            print(f"数据列名: {stock_data.columns.tolist()}")
            
            # 处理数据：删除可能存在的不需要的'index'列
            if 'index' in stock_data.columns:
                stock_data = stock_data.drop('index', axis=1)
            
            # 初始化默认的重命名映射
            rename_map = {
                'open': '开盘',
                'high': '最高',
                'low': '最低',
                'close': '收盘',
                'volume': '成交量'
            }
            
            # 根据实际列名调整重命名映射
            if 'date' in stock_data.columns:
                rename_map['date'] = '时间'
                rename_map['amount'] = '成交额'
                rename_map['turnover'] = '换手率'
                rename_map['outstanding_share'] = '流通股数'
            elif 'day' in stock_data.columns:
                rename_map['day'] = '时间'
            
            # 只保留存在于stock_data.columns中的映射键
            rename_map = {k: v for k, v in rename_map.items() if k in stock_data.columns}
            
            # 重命名列
            stock_data = stock_data.rename(columns=rename_map)
            return stock_data, file_name
        except Exception as e:
            print(f"获取股票历史数据失败: {e}")
            traceback.print_exc()
            return pd.DataFrame(), ''
    
    def get_stock_info(self):
        """
        使用akshare获取股票详细信息
        """
        try:
            # 使用akshare的stock_individual_info_em获取股票基本信息
            # 此函数需要股票代码不带交易所前缀
            if self.stock_code.startswith('sh') or self.stock_code.startswith('sz'):
                code_only = self.stock_code[2:]
            else:
                code_only = self.stock_code
            
            stock_info_df = ak.stock_individual_info_em(symbol=code_only)
            
            # 将DataFrame转换为字典格式
            stock_info_dict = {}
            for index, row in stock_info_df.iterrows():
                stock_info_dict[row['item']] = row['value']
                
            return stock_info_dict
        except Exception as e:
            print(f"使用akshare获取股票详细信息失败: {e}")
            return None
    
    def save_data(self, stock_data=None, file_name=None)->bool:
        """
        保存股票数据到CSV文件,保存成功返回True,失败返回False
        :参数 stock_data: 股票数据(DataFrame)
        :参数 file_name: 保存文件名,默认为对应股票的CSV文件,例如:sz000001_hfq_minute.csv, 前缀含义：
            - sz000001:股票代码
            - hfq:复权类型
            - minute:数据精度
        """
        try:
            if stock_data is None or stock_data.empty:
                print("没有股票数据可保存")
                return False
            # 检查是否包含时间列
            if '时间' not in stock_data.columns:
                print("股票数据必须包含'时间'列")
                return False
            # 先解析文件名获取股票代码、复权类型、数据精度
            # 有两种格式：
            # 1. sz000001_hfq_minute.csv 这是分钟级，文件名无日期范围
            # 2. sz000001_hfq_daily_210104_241231.csv 这是日线级，文件名包含日期范围
            # 3. sz000002__daily_20230101_20230105.csv 这是不复权的日线数据
            
            # 定义正则表达式模式
            # 支持带前缀和不带前缀的股票代码
            # 分组1: 股票代码 (?:(sh|sz))?\d{6} - 前缀可选
            # 分组2: 交易所前缀 (sh|sz) - 可选
            # 分组3: 复权类型 ([a-z]*) - 可能为空
            # 分组4: 数据类型 (daily|minute)
            # 分组5: 开始日期 (可选，6或8位数字)
            # 分组6: 结束日期 (可选，6或8位数字)
            pattern = r'^((?:(sh|sz))?\d{6})_([a-z]*)_(daily|minute)(?:_(\d{6}|\d{8})_(\d{6}|\d{8}))?\.csv$'
            match = re.match(pattern, file_name)
            
            if not match:
                print("文件名格式错误，示例：sz000001_hfq_minute.csv 或 sz000001_hfq_daily_210104_241231.csv")
                print(f"当前文件名: {file_name}")
                return False
            
            # 提取匹配的组
            stock_code, _, fq_type, time_type, start_date, end_date = match.groups()
            
            # 处理复权类型为空的情况
            if fq_type is None:
                fq_type = 'nfq'
            # 保存的文件路径应该为：stock_data/市场类型/股票代码/复权类型/数据精度/文件名
            # 移除股票代码中的市场前缀（如果有）
            code_without_prefix = stock_code[2:] if stock_code.startswith('sh') or stock_code.startswith('sz') else stock_code
            file_path = os.path.join(self.stock_data_dir, f"{code_without_prefix}", f"{fq_type}", f"{time_type}", f"{file_name}")
            # 确保目录存在
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            # 保存数据前先检查是否已存在
            if os.path.exists(file_path):
                print(f"文件 {file_path} 已存在，将覆盖")
            stock_data.to_csv(file_path, index=False, encoding='utf-8-sig')
            print(f"股票数据已成功保存到 {file_path}")
            return True
        except Exception as e:
            print(f"保存股票数据到 {file_path} 失败: {e}")
            return False

def get_hs300_stocks():
    """
    获取沪深300成分股列表
    :return: 沪深300成分股代码列表
    """
    try:
        save_path = "d:/workplace/codeplace/junkcode/Qdt_test/stock_data/沪深300"
        
        # 创建保存路径（如果不存在）
        if not os.path.exists(save_path):
            os.makedirs(save_path)
            print(f"创建保存路径: {save_path}")
        
        # 获取沪深300成分股列表，先看本地是否有缓存文件
        cache_file = os.path.join(save_path, '沪深300成分股列表.csv')
        if os.path.exists(cache_file):
            print(f"发现本地缓存文件: {cache_file}")
            hs300_df = pd.read_csv(cache_file, encoding='utf-8')
            
            # 处理股票代码格式
            stock_list = hs300_df['股票代码'].tolist()
            
            print(f"从缓存文件加载沪深300成分股，共{len(stock_list)}只股票")
            return stock_list
        else:
            # 如果缓存文件不存在，直接使用akshare获取沪深300成分股列表
            print("本地缓存文件不存在，正在从akshare获取沪深300成分股列表")
            hs300_df = ak.index_stock_info(index_code="000300")
            
            # 处理股票代码格式
            stock_list = hs300_df['成分券代码'].tolist()
            
            # 保存到缓存文件
            hs300_df.to_csv(cache_file, encoding='utf-8', index=False)
            print(f"已获取并保存沪深300成分股列表到{cache_file}，共{len(stock_list)}只股票")
            return stock_list
    except Exception as e:
        print(f"获取沪深300成分股列表时发生错误: {e}")
        raise e


# 常用指数代码（akshare stock_zh_index_daily 的 symbol 形如 sh000300 / sz399001）
INDEX_SYMBOLS = {
    '000300': 'sh000300',   # 沪深300
    '399300': 'sz399300',
    '000001': 'sh000001',   # 上证指数
    '399001': 'sz399001',   # 深证成指
    '399006': 'sz399006',   # 创业板指
}


def get_index_data(index_code: str = '000300', start_date: str = '', end_date: str = '') -> pd.DataFrame:
    """
    获取A股指数日线数据，用于回测基准（Alpha/Beta/信息比率）。

    :param index_code: 指数代码（不带前缀），默认 '000300'（沪深300）
    :param start_date: 开始日期 'YYYYMMDD'
    :param end_date: 结束日期 'YYYYMMDD'，默认今天
    :return: 与 Stock.get_stock_data 列名一致的 DataFrame
             （开盘/最高/最低/收盘/成交量/时间，'时间' 为列而非 index）。
             失败时返回空 DataFrame。
    """
    try:
        if not end_date:
            end_date = datetime.now().strftime('%Y%m%d')

        symbol = INDEX_SYMBOLS.get(index_code)
        if symbol is None:
            # 兜底：6 开头归上交所，0/3 开头归深交所
            symbol = ('sh' if str(index_code).startswith('6') else 'sz') + str(index_code)

        print(f"正在获取指数 {index_code} 的日线数据，日期范围: {start_date} 至 {end_date}")
        df = ak.stock_zh_index_daily(symbol=symbol)

        if df is None or df.empty:
            print(f"指数 {index_code} 返回空数据")
            return pd.DataFrame()

        # stock_zh_index_daily 通常含列: date, open, high, low, close, volume, amount
        rename_map = {
            'date': '时间', 'open': '开盘', 'high': '最高',
            'low': '最低', 'close': '收盘', 'volume': '成交量', 'amount': '成交额',
        }
        rename_map = {k: v for k, v in rename_map.items() if k in df.columns}
        df = df.rename(columns=rename_map)

        # 按日期过滤（akshare 的 stock_zh_index_daily 不接受 start/end，需本地过滤）
        if '时间' in df.columns:
            df['时间'] = pd.to_datetime(df['时间'])
            if start_date:
                df = df[df['时间'] >= pd.to_datetime(start_date)]
            if end_date:
                df = df[df['时间'] <= pd.to_datetime(end_date)]
            df = df.sort_values('时间').reset_index(drop=True)

        print(f"成功获取指数数据，数据行数: {len(df)}")
        return df
    except Exception as e:
        print(f"获取指数数据失败: {e}")
        traceback.print_exc()
        return pd.DataFrame()


def load_sentiment_snapshots(snapshots_dir: str = None) -> pd.DataFrame:
    """
    扫描本地历史情绪快照，构建"快照日期 × 行业"的情绪分数面板。

    用于回测中的情绪过滤：某回测日只能使用"截至该日最近的历史快照"，
    以避免未来函数（lookahead bias）。

    快照文件位于 nes_data/sentiment_results/{YYYYMMDD}.json，结构为：
        {
          'date': 'YYYY-MM-DD',
          'timestamp': 'YYYY-MM-DD HH:MM:SS',
          'all_sectors': [ {'name': '石油行业', 'sentiment': 60, 'stocks': [...]}, ... 64 个 ],
          ...
        }
    其中 ``sentiment`` 为 0-100 量表（50 为中性）。本函数归一化到 -1..1：(s-50)/50。

    :param snapshots_dir: 快照目录，默认为项目根下 nes_data/sentiment_results
    :return: DataFrame，index=快照日期（DatetimeIndex, name='日期'），
             columns=行业名称（如"石油行业"），值为归一化情绪分数(-1..1)。
             无快照时返回空 DataFrame。
    """
    try:
        import glob
        import json

        if snapshots_dir is None:
            # __file__ = <root>/src/data/data_manager.py -> 需回溯 3 层到项目根
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            snapshots_dir = os.path.join(project_root, 'nes_data', 'sentiment_results')

        files = sorted(glob.glob(os.path.join(snapshots_dir, '*.json')))
        if not files:
            return pd.DataFrame()

        records = []  # list of dict {行业名: 归一化分数}
        dates = []
        for fp in files:
            try:
                with open(fp, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            except Exception:
                continue

            # 日期优先用文件名，其次 date 字段，再次 timestamp
            stem = os.path.splitext(os.path.basename(fp))[0]
            try:
                snap_date = pd.to_datetime(stem, format='%Y%m%d')
            except Exception:
                snap_date = pd.to_datetime(data.get('date') or data.get('timestamp'))

            sectors = data.get('all_sectors')
            if not sectors:
                continue
            row = {}
            for sec in sectors:
                name = sec.get('name')
                if name is None:
                    continue
                raw = sec.get('sentiment')
                # 0-100 -> -1..1，越界时裁剪；缺失/不可解析时记为中性 0.0，
                # 避免不同快照间因某行业缺失而产生 NaN 列。
                try:
                    norm = (float(raw) - 50.0) / 50.0
                except (TypeError, ValueError):
                    norm = 0.0
                row[name] = max(-1.0, min(1.0, norm))
            if row:
                records.append(row)
                dates.append(snap_date)

        if not records:
            return pd.DataFrame()

        panel = pd.DataFrame(records, index=pd.DatetimeIndex(dates, name='日期'))
        panel = panel.sort_index()
        # 不同快照间行业集合可能不一致（个别快照缺某行业），缺失填中性 0.0
        panel = panel.fillna(0.0)
        return panel
    except Exception as e:
        print(f"加载情绪快照失败: {e}")
        return pd.DataFrame()


def build_stock_sentiment_series(panel: pd.DataFrame, stock_code: str) -> 'tuple[pd.Series, object]':
    """
    从情绪面板中提取某只股票所属行业的情绪时间序列。

    通过各快照 all_sectors[i]['stocks'] 中的成分代码定位行业。若同一股票在多个
    行业出现，取第一个匹配。返回的序列可直接用于回测过滤：某回测日取"截至该日
    最近的快照值"，避免未来函数。

    :param panel: load_sentiment_snapshots() 返回的面板（index=日期, columns=行业名）
    :param stock_code: 不带前缀的 6 位股票代码，如 '000001'
    :return: (series, sector_name)。series 的 index 为快照日期，值为归一化情绪分数；
             若无法定位行业，series 为空、sector_name 为 None。
    """
    try:
        import glob
        import json

        code = str(stock_code).zfill(6)
        # 去掉可能的 sh/sz 前缀
        if code.startswith(('sh', 'sz')):
            code = code[2:]
        code = code.zfill(6)

        if panel is None or panel.empty:
            return pd.Series(dtype=float), None

        # 优先通过行业映射器定位行业（覆盖快照未显式列出的股票），
        # 失败时回退到扫描快照的成分股代码。
        sector_name = None
        try:
            from src.factor.daily_recommend import StockSectorMapper
            mapper = StockSectorMapper()
            sector_name = mapper.get_sector_by_code(code)
        except Exception:
            sector_name = None

        # 若映射器没结果或映射出的行业不在面板里，回退到成分股扫描
        if not sector_name or sector_name not in panel.columns:
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            snapshots_dir = os.path.join(project_root, 'nes_data', 'sentiment_results')
            files = sorted(glob.glob(os.path.join(snapshots_dir, '*.json')))
            found = None
            for fp in files:
                try:
                    with open(fp, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                except Exception:
                    continue
                for sec in data.get('all_sectors', []):
                    for st in sec.get('stocks', []):
                        if str(st.get('code', '')).zfill(6) == code:
                            found = sec.get('name')
                            break
                    if found:
                        break
                if found:
                    break
            if found and found in panel.columns:
                sector_name = found
            elif sector_name not in panel.columns:
                sector_name = None

        if not sector_name or sector_name not in panel.columns:
            return pd.Series(dtype=float), None

        series = panel[sector_name].copy()
        series.name = sector_name
        return series, sector_name
    except Exception as e:
        print(f"构建股票情绪序列失败: {e}")
        return pd.Series(dtype=float), None