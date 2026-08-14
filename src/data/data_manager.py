import akshare as ak
import pandas as pd
import re
import os
import traceback
import logging
from src.utils.paths import PROJECT_ROOT, ensure_dir
from src.utils.env import get_env
from datetime import datetime

logger = logging.getLogger(__name__)

# Tushare Pro token（可选 A 股数据源；留空则该层静默跳过，回退到免费链）
_TUSHARE_TOKEN = get_env("TUSHARE_TOKEN", "")

class Stock:
    def __init__(self, stock_code, market='zh_a'):
        """
        初始化Stock类
        :param stock_code: 股票代码（A股为6位数字代码；美股为字母代码如 AAPL）
        :param market: 股票市场: 默认A股('zh_a')，美股为 'us'
        """
        self.stock_code = stock_code
        self.market = market

        # 美股：统一大写，不做 sh/sz 前缀处理
        if self.market == 'us':
            if not isinstance(self.stock_code, str):
                self.stock_code = str(self.stock_code)
            self.stock_code = self.stock_code.strip().upper()
        # 为中国A股股票代码添加市场前缀
        elif self.market == 'zh_a':
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
        :return: 不带前缀的股票代码（A股去掉 sh/sz；美股原样返回大写 ticker）
        """
        if self.market == 'us':
            return self.stock_code
        if self.stock_code.startswith('sh') or self.stock_code.startswith('sz'):
            return self.stock_code[2:]
        return self.stock_code

    @staticmethod
    def _filter_us_daily_by_date(df: pd.DataFrame, start_date: str, end_date: str) -> pd.DataFrame:
        """
        本地过滤美股日线数据日期范围（ak.stock_us_daily 不支持 start/end 参数）。

        :param df: stock_us_daily 返回的 DataFrame（含 date 列）
        :param start_date: 起始日期 'YYYYMMDD'
        :param end_date: 结束日期 'YYYYMMDD'
        :return: 过滤后的 DataFrame
        """
        if df is None or df.empty or 'date' not in df.columns:
            return df
        try:
            dates = pd.to_datetime(df['date'])
            start = pd.to_datetime(start_date, format='%Y%m%d')
            end = pd.to_datetime(end_date, format='%Y%m%d')
            mask = (dates >= start) & (dates <= end)
            return df[mask].reset_index(drop=True)
        except Exception:
            return df

    def _fetch_ashare_hist_em(self, start_date: str, end_date: str, adjust_str: str) -> pd.DataFrame:
        """通过 akshare 东方财富源 (stock_zh_a_hist) 获取 A 股个股日线（回退源1）。

        akshare 官方推荐此接口（数据质量高、访问无限制）。
        symbol 用纯 6 位代码（不带 sh/sz 前缀），与 stock_zh_a_daily 不同。
        返回中文列名，这里统一转为小写英文列名，以便复用 get_stock_data 的 rename_map。

        :param start_date: 'YYYYMMDD'
        :param end_date: 'YYYYMMDD'
        :param adjust_str: '' 不复权 / 'qfq' 前复权 / 'hfq' 后复权
        :return: 小写列名 (date/open/high/low/close/volume/amount) DataFrame；失败返回空
        """
        try:
            em_symbol = self.get_code_without_prefix()
            logger.info(f"akshare 东财源: 获取 {em_symbol} 日线 ({start_date} ~ {end_date}, adjust={adjust_str or 'nfq'})")
            df = ak.stock_zh_a_hist(
                symbol=em_symbol,
                period="daily",
                start_date=start_date,
                end_date=end_date,
                adjust=adjust_str,
            )
            if df is None or df.empty:
                return pd.DataFrame()
            # 东财源返回中文列名，统一转为小写英文以复用下游 rename_map
            col_map = {
                '日期': 'date', '开盘': 'open', '最高': 'high', '最低': 'low',
                '收盘': 'close', '成交量': 'volume', '成交额': 'amount',
            }
            col_map = {k: v for k, v in col_map.items() if k in df.columns}
            df = df.rename(columns=col_map)
            return df
        except Exception as e:
            logger.warning(f"akshare 东财源获取 {self.stock_code} 失败: {e}")
            return pd.DataFrame()

    def _fetch_ashare_tushare(self, start_date: str, end_date: str, adjust_str: str) -> pd.DataFrame:
        """通过 Tushare Pro 获取 A 股个股日线（可选首选源，需 TUSHARE_TOKEN）。

        无 token 或 tushare 未安装时静默跳过（返回空 DataFrame），由调用方回退到免费链。
        Tushare ts_code 格式 '600938.SH'；volume 单位为手（与 akshare 一致，无需换算）；
        amount 单位为千元（需 ×1000 转为元，与 akshare 对齐）。

        :param start_date: 'YYYYMMDD'
        :param end_date: 'YYYYMMDD'
        :param adjust_str: '' 不复权 / 'qfq' 前复权 / 'hfq' 后复权
        :return: 小写列名 (date/open/high/low/close/volume/amount) DataFrame；失败/无 token 返回空
        """
        if not _TUSHARE_TOKEN:
            return pd.DataFrame()
        try:
            import tushare as ts
        except ImportError:
            logger.warning("tushare 未安装，跳过 Tushare 源（pip install tushare）")
            return pd.DataFrame()
        try:
            # sh600938 / sz000001 → 600938.SH / 000001.SZ
            bare = self.get_code_without_prefix()
            ts_code = f"{bare}.SH" if self.stock_code.startswith('sh') else f"{bare}.SZ"
            ts.set_token(_TUSHARE_TOKEN)
            pro = ts.pro_api()
            adj = adjust_str if adjust_str in ('qfq', 'hfq') else None
            if adj:
                # 复权需用 pro_bar（pro.daily 仅返回不复权）
                df = ts.pro_bar(ts_code=ts_code, start_date=start_date, end_date=end_date, adj=adj)
            else:
                df = pro.daily(ts_code=ts_code, start_date=start_date, end_date=end_date)
            if df is None or df.empty:
                return pd.DataFrame()
            # Tushare 列：trade_date(YYYYMMDD)/open/high/low/close/vol(手)/amount(千元)/...
            # 归一化到下游统一的小写英文列名
            col_map = {'trade_date': 'date', 'vol': 'volume'}
            col_map = {k: v for k, v in col_map.items() if k in df.columns}
            df = df.rename(columns=col_map)
            # amount: 千元 → 元（与 akshare 单位对齐）
            if 'amount' in df.columns:
                df['amount'] = pd.to_numeric(df['amount'], errors='coerce') * 1000.0
            for col in ('open', 'high', 'low', 'close', 'volume'):
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            return df
        except Exception as e:
            logger.warning(f"Tushare 获取 {self.stock_code} 失败: {e}")
            return pd.DataFrame()

    def _fetch_ashare_baostock(self, start_date: str, end_date: str, adjust_str: str) -> pd.DataFrame:
        """通过 baostock 获取 A 股个股日线（回退源2，独立数据服务器）。

        baostock code 格式 'sh.600000'，日期 'YYYY-MM-DD'，adjustflag 1/2/3（与 akshare 相反）。
        volume 单位是股（需 /100 转手），数值字段全是字符串（需转 float）。

        :param start_date: 'YYYYMMDD'
        :param end_date: 'YYYYMMDD'
        :param adjust_str: '' 不复权 / 'qfq' 前复权 / 'hfq' 后复权
        :return: 小写列名 (date/open/high/low/close/volume/amount) DataFrame；失败返回空
        """
        try:
            df = _baostock_query(
                self.stock_code, start_date, end_date, adjust_str,
                fields="date,open,high,low,close,volume,amount",
            )
            if df is None or df.empty:
                return pd.DataFrame()
            # baostock volume 单位是股，转为手（与 akshare 一致）
            for col in ('open', 'high', 'low', 'close', 'volume', 'amount'):
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            if 'volume' in df.columns:
                df['volume'] = df['volume'] / 100.0
            return df
        except Exception as e:
            logger.warning(f"baostock 获取 {self.stock_code} 失败: {e}")
            return pd.DataFrame()

    def _fetch_us_stock_yf(self, ticker: str, start_date: str, end_date: str, adjust_str: str) -> pd.DataFrame:
        """通过 yfinance 获取美股个股日线数据（主数据源）。

        返回小写列名 (date/open/high/low/close/volume) 的 DataFrame，
        以便与 akshare 返回格式一致，复用 get_stock_data 的列名重命名逻辑。

        :param ticker: 大写美股代码，如 'AAPL'
        :param start_date: 'YYYYMMDD'
        :param end_date: 'YYYYMMDD'
        :param adjust_str: akshare 风格复权标识 ('' 不复权 / 'qfq' 前复权 / 'hfq' 后复权)
        :return: 小写列名 DataFrame；失败返回空 DataFrame
        """
        try:
            import yfinance as yf
        except ImportError:
            logger.warning("yfinance 未安装，跳过 yfinance 数据源")
            return pd.DataFrame()

        try:
            yf_start = f"{start_date[:4]}-{start_date[4:6]}-{start_date[6:8]}" if start_date else None
            if end_date:
                yf_end_dt = pd.to_datetime(end_date, format='%Y%m%d') + pd.Timedelta(days=1)
                yf_end = yf_end_dt.strftime('%Y-%m-%d')
            else:
                yf_end = None

            auto_adjust = adjust_str in ('qfq', 'hfq')
            logger.info(f"yfinance: 获取 {ticker} 日线 ({yf_start} ~ {yf_end}, auto_adjust={auto_adjust})")
            df = yf.Ticker(ticker).history(
                start=yf_start, end=yf_end,
                interval='1d', auto_adjust=auto_adjust,
                actions=False, raise_errors=True,
            )

            if df is None or df.empty:
                return pd.DataFrame()

            df = df.reset_index()
            date_col = 'Date' if 'Date' in df.columns else df.columns[0]
            df[date_col] = pd.to_datetime(df[date_col]).dt.tz_localize(None)
            df.columns = df.columns.str.lower()

            return df
        except Exception as e:
            logger.warning(f"yfinance 获取 {ticker} 失败: {e}")
            return pd.DataFrame()

    def get_stock_name(self):
        """
        先查找本地股票数据文件， 若不存在则使用akshare获取
        """
        try:
            file_path = os.path.join(self.stock_data_dir, 'stocks.csv')
            if os.path.exists(file_path):
                # 读取本地股票数据文件
                name_list = pd.read_csv(file_path)
            else:
                # 使用akshare获取股票代码和名称的映射
                name_list = ak.stock_info_a_code_name()
                # 保存到本地文件（目录可能尚未创建，先确保存在）
                os.makedirs(self.stock_data_dir, exist_ok=True)
                name_list.to_csv(file_path, index=False)
            # 映射表中 A 股代码为不带前缀的 6 位数字；CSV 回读可能被解析成 int（丢失前导0），统一按字符串比较
            code = str(self.get_code_without_prefix()) if self.market == 'zh_a' else str(self.stock_code)
            codes = name_list['code'].astype(str)
            if self.market == 'zh_a':
                codes = codes.str.zfill(6)
            stock_name = name_list[codes == code]
            if not stock_name.empty:
                return stock_name.iloc[0]['name']
            return None
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
                # 定义复权类型映射（A股与美股通用）
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

                    # ---- DB 缓存层（Redis→PostgreSQL）----
                    # 先查缓存，命中且非空则直接返回，跳过网络。
                    # 失败静默降级（连不上 DB 时回退到下面的网络回退链）。
                    try:
                        from src.data import db as _db
                        _cached = _db.get_cached_range(
                            code_without_prefix, self.market, adjust,
                            start_date, end_date,
                        )
                        if _cached is not None and not _cached.empty:
                            logger.info(f"DB 缓存命中 {self.stock_code} ({self.market}/{adjust}): {len(_cached)} 行")
                            return _cached, file_name
                    except Exception as _e:
                        logger.debug(f"DB 缓存查询失败，回退网络链: {_e}")

                    print(f"正在获取{self.stock_code}的历史数据（日线），日期范围: {start_date}至{end_date}")
                    if self.market == 'us':
                        ticker = self.get_code_without_prefix()
                        # 优先 yfinance（支持 start/end，更可靠），失败回退 akshare 新浪源
                        try:
                            stock_data = self._fetch_us_stock_yf(ticker, start_date, end_date, adjust_map[adjust])
                        except Exception as e:
                            logger.warning(f"yfinance 个股获取异常，准备回退: {e}")
                            stock_data = pd.DataFrame()
                        if stock_data is None or stock_data.empty:
                            logger.warning("yfinance 返回空数据，回退到 akshare stock_us_daily（新浪源）")
                            stock_data = ak.stock_us_daily(symbol=ticker, adjust=adjust_map[adjust])
                            stock_data = self._filter_us_daily_by_date(stock_data, start_date, end_date)
                    else:
                        # A股回退链：Tushare(可选首选) → 新浪源 → 东财源 → baostock
                        if _TUSHARE_TOKEN:
                            stock_data = self._fetch_ashare_tushare(start_date, end_date, adjust_map[adjust])
                        else:
                            stock_data = pd.DataFrame()

                        if stock_data is None or stock_data.empty:
                            try:
                                stock_data = ak.stock_zh_a_daily(
                                    symbol=self.stock_code,
                                    start_date=start_date,
                                    end_date=end_date,
                                    adjust=adjust_map[adjust]
                                )
                            except Exception as e:
                                logger.warning(f"akshare 新浪源获取 {self.stock_code} 失败: {e}，回退到东财源")
                                stock_data = pd.DataFrame()

                        if stock_data is None or stock_data.empty:
                            logger.warning("新浪源返回空数据，回退到 akshare stock_zh_a_hist（东财源）")
                            stock_data = self._fetch_ashare_hist_em(start_date, end_date, adjust_map[adjust])

                        if stock_data is None or stock_data.empty:
                            logger.warning("东财源返回空数据，回退到 baostock")
                            stock_data = self._fetch_ashare_baostock(start_date, end_date, adjust_map[adjust])
                elif type == 'minute':
                    # 获取分钟级数据（仅 A 股支持）
                    if self.market == 'us':
                        print("错误：美股暂不支持分钟级数据")
                        return pd.DataFrame(), ''
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

            # 统一列名重命名（英文→中文），引用唯一来源
            from src.data.columns import EN_TO_ZH
            rename_map = {k: v for k, v in EN_TO_ZH.items() if k in stock_data.columns}

            # 重命名列
            stock_data = stock_data.rename(columns=rename_map)

            # ---- 回填 DB 缓存层（PostgreSQL upsert + Redis）----
            # 仅日线数据写缓存（分钟级数据量大且本模块不持久化）；失败静默。
            if type == 'daily':
                try:
                    from src.data import db as _db
                    _db.save_daily(
                        stock_data, code_without_prefix, self.market, adjust,
                    )
                except Exception as _e:
                    logger.debug(f"DB 缓存回填失败（不影响主流程）: {_e}")

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
        save_path = str(PROJECT_ROOT / "stock_data" / "沪深300")
        
        # 创建保存路径（如果不存在）
        ensure_dir(save_path)
        
        # 获取沪深300成分股列表，先看本地是否有缓存文件
        cache_file = os.path.join(save_path, '沪深300成分股列表.csv')
        if os.path.exists(cache_file):
            logger.info(f"发现本地缓存文件: {cache_file}")
            hs300_df = pd.read_csv(cache_file, encoding='utf-8')
            
            # 处理股票代码格式
            stock_list = hs300_df['股票代码'].tolist()
            
            logger.info(f"从缓存文件加载沪深300成分股，共{len(stock_list)}只股票")
            return stock_list
        else:
            # 如果缓存文件不存在，直接使用akshare获取沪深300成分股列表
            logger.info("本地缓存文件不存在，正在从akshare获取沪深300成分股列表")
            hs300_df = ak.index_stock_info(index_code="000300")
            
            # 处理股票代码格式
            stock_list = hs300_df['成分券代码'].tolist()
            
            # 保存到缓存文件
            hs300_df.to_csv(cache_file, encoding='utf-8', index=False)
            logger.info(f"已获取并保存沪深300成分股列表到{cache_file}，共{len(stock_list)}只股票")
            return stock_list
    except Exception as e:
        logger.error(f"获取沪深300成分股列表时发生错误: {e}")
        raise e


# 常用指数代码（akshare stock_zh_index_daily 的 symbol 形如 sh000300 / sz399001）
INDEX_SYMBOLS = {
    '000300': 'sh000300',   # 沪深300
    '399300': 'sz399300',
    '000001': 'sh000001',   # 上证指数
    '399001': 'sz399001',   # 深证成指
    '399006': 'sz399006',   # 创业板指
}


# 美股指数代码（akshare index_us_stock_sina 的 symbol 为新浪点前缀代码）
US_INDEX_SYMBOLS = {
    'SP500': '.INX',        # 标普500
    'NASDAQ': '.IXIC',      # 纳斯达克综合
    'DOWJONES': '.DJI',     # 道琼斯工业
    'NASDAQ100': '.NDX',    # 纳斯达克100
}

# yfinance 美股指数代码（Yahoo Finance 用 ^ 前缀）
US_INDEX_YF_SYMBOLS = {
    'SP500': '^GSPC',       # 标普500
    'NASDAQ': '^IXIC',      # 纳斯达克综合
    'DOWJONES': '^DJI',     # 道琼斯工业
    'NASDAQ100': '^NDX',    # 纳斯达克100
}


# ---------------------------------------------------------------------------
# baostock 会话管理（A 股回退源2）
# ---------------------------------------------------------------------------
# baostock adjustflag 与 akshare adjust 字符串的映射（含义相反！）
# akshare: '' 不复权 / 'qfq' 前复权 / 'hfq' 后复权
# baostock: '3' 不复权 / '2' 前复权 / '1' 后复权
BAOSTOCK_ADJUST_MAP = {'nfq': '3', '': '3', 'qfq': '2', 'hfq': '1'}


class _BaoStockSession:
    """baostock 单例会话：自动重登 + 查询计数 + 指数退避重试。

    baostock 单次登录约 200 次查询后随机失败，30 分钟无请求自动断开。
    本封装在查询失败或计数超限时自动重登，并对每次查询做指数退避重试。

    线程安全：共享 socket + login 状态非线程安全，用全局锁串行化所有查询。
    baostock 仅是最终回退源，串行化它对并发主链（akshare 系）几乎无影响。
    """

    def __init__(self):
        import threading
        self._logged_in = False
        self._query_count = 0
        self._max_per_session = 200
        self._lock = threading.Lock()

    def _ensure_login(self):
        import baostock as bs
        if self._logged_in and self._query_count < self._max_per_session:
            return
        if self._logged_in:
            try:
                bs.logout()
            except Exception:
                pass
            self._logged_in = False
        import contextlib, io
        with contextlib.redirect_stdout(io.StringIO()):
            lg = bs.login()
        if lg.error_code != '0':
            raise ConnectionError(f"baostock 登录失败: {lg.error_msg}")
        self._logged_in = True
        self._query_count = 0
        logger.info("baostock 登录成功")

    def query(self, bs_code, fields, start_date, end_date, adjustflag="3"):
        """带重试的查询。返回 DataFrame（列名来自 rs.fields），失败抛异常。

        整个查询（含 login 状态变更 + socket 读写）持锁串行化，保证多线程安全。

        :param bs_code: 'sh.600000' / 'sz.000001' / 'sh.000300'（指数）
        :param fields: 逗号分隔字段串，如 "date,open,high,low,close,volume,amount"
        :param start_date: 'YYYY-MM-DD'
        :param end_date: 'YYYY-MM-DD'
        :param adjustflag: '1' 后复权 / '2' 前复权 / '3' 不复权
        """
        with self._lock:
            import time
            import baostock as bs
            last_err = None
            for attempt in range(3):
                try:
                    self._ensure_login()
                    import contextlib, io
                    with contextlib.redirect_stdout(io.StringIO()):
                        rs = bs.query_history_k_data_plus(
                            bs_code, fields,
                            start_date=start_date, end_date=end_date,
                            frequency="d", adjustflag=adjustflag,
                        )
                    if rs.error_code == '0':
                        data = []
                        while rs.next():
                            data.append(rs.get_row_data())
                        self._query_count += 1
                        time.sleep(0.3)
                        return pd.DataFrame(data, columns=rs.fields)
                    last_err = rs.error_msg
                except Exception as e:
                    last_err = str(e)
                time.sleep(2 ** attempt)
                self._logged_in = False  # 失败 → 下次重登
            raise RuntimeError(f"baostock 重试失败: {last_err}")

    def logout(self):
        if not self._logged_in:
            return
        try:
            import baostock as bs
            bs.logout()
        except Exception:
            pass
        self._logged_in = False


_bs_session = _BaoStockSession()


def _to_baostock_code(code_with_prefix: str) -> str:
    """akshare 风格 'sh600000' / 'sz000001' → baostock 风格 'sh.600000' / 'sz.000001'。"""
    s = str(code_with_prefix)
    pfx = s[:2].lower()
    if pfx in ('sh', 'sz', 'bj'):
        return f"{pfx}.{s[2:]}"
    return s


def _baostock_query(code_with_prefix: str, start_date: str, end_date: str,
                    adjust_str: str, fields: str = "date,open,high,low,close,volume,amount") -> pd.DataFrame:
    """baostock 查询封装（个股/指数通用）。

    :param code_with_prefix: 'sh600000' / 'sz000001' / 'sh000300'（指数）
    :param start_date: 'YYYYMMDD'（自动转为 'YYYY-MM-DD'）
    :param end_date: 'YYYYMMDD'
    :param adjust_str: '' / 'qfq' / 'hfq'（akshare 风格，自动映射 baostock adjustflag）
    :param fields: 逗号分隔字段串
    :return: DataFrame；失败抛异常（由调用方 try/except）
    """
    bs_code = _to_baostock_code(code_with_prefix)
    bs_start = f"{start_date[:4]}-{start_date[4:6]}-{start_date[6:8]}" if start_date else None
    bs_end = f"{end_date[:4]}-{end_date[4:6]}-{end_date[6:8]}" if end_date else None
    adjustflag = BAOSTOCK_ADJUST_MAP.get(adjust_str, '3')
    return _bs_session.query(bs_code, fields, bs_start, bs_end, adjustflag=adjustflag)


def get_index_data(index_code: str = '000300', start_date: str = '', end_date: str = '',
                   market: str = 'zh_a') -> pd.DataFrame:
    """
    获取指数日线数据，用于回测基准（Alpha/Beta/信息比率）。

    :param index_code: 指数代码。A股默认 '000300'（沪深300）；
                       美股为 US_INDEX_SYMBOLS 的键（如 'SP500'）。
    :param start_date: 开始日期 'YYYYMMDD'
    :param end_date: 结束日期 'YYYYMMDD'，默认今天
    :param market: 市场，'zh_a'（A股，默认）或 'us'（美股）
    :return: 与 Stock.get_stock_data 列名一致的 DataFrame
             （开盘/最高/最低/收盘/成交量/时间，'时间' 为列而非 index）。
             失败时返回空 DataFrame。
    """
    if market == 'us':
        return get_us_index_data(index_code, start_date, end_date)
    try:
        if not end_date:
            end_date = datetime.now().strftime('%Y%m%d')

        symbol = INDEX_SYMBOLS.get(index_code)
        if symbol is None:
            # 兜底：6 开头归上交所，0/3 开头归深交所
            symbol = ('sh' if str(index_code).startswith('6') else 'sz') + str(index_code)

        # ---- DB 缓存层（指数）----
        # 命中则直接返回，跳过网络回退链；失败静默降级。
        try:
            from src.data import db as _db
            _cached = _db.get_cached_range(
                str(index_code), market, 'nfq', start_date, end_date, is_index=True,
            )
            if _cached is not None and not _cached.empty:
                logger.info(f"DB 缓存命中 指数 {index_code}: {len(_cached)} 行")
                return _cached
        except Exception as _e:
            logger.debug(f"DB 缓存查询失败（指数），回退网络链: {_e}")

        print(f"正在获取指数 {index_code} 的日线数据，日期范围: {start_date} 至 {end_date}")

        # A股指数回退链：Tushare(可选首选) → 新浪源 → 东财源 → baostock
        # 0) Tushare Pro（需 token，支持 start/end）
        df = pd.DataFrame()
        if _TUSHARE_TOKEN:
            try:
                import tushare as ts
                ts.set_token(_TUSHARE_TOKEN)
                pro = ts.pro_api()
                # sh000300 → 000300.SH
                idx_ts_code = f"{symbol[2:]}.{symbol[:2].upper()}"
                raw = pro.index_daily(ts_code=idx_ts_code, start_date=start_date, end_date=end_date)
                if raw is not None and not raw.empty:
                    col_map = {'trade_date': 'date', 'vol': 'volume'}
                    col_map = {k: v for k, v in col_map.items() if k in raw.columns}
                    df = raw.rename(columns=col_map)
                    for col in ('open', 'high', 'low', 'close', 'volume', 'amount'):
                        if col in df.columns:
                            df[col] = pd.to_numeric(df[col], errors='coerce')
                    if 'amount' in df.columns:
                        df['amount'] = df['amount'] * 1000.0  # 千元 → 元
            except Exception as e:
                logger.warning(f"Tushare 指数获取 {index_code} 失败: {e}，回退到免费链")
                df = pd.DataFrame()

        # 1) 新浪源（不支持 start/end，需本地过滤）
        if df is None or df.empty:
            try:
                df = ak.stock_zh_index_daily(symbol=symbol)
            except Exception as e:
                logger.warning(f"akshare 新浪指数源获取 {index_code} 失败: {e}，回退到东财源")
                df = pd.DataFrame()

        # 2) 东财源（支持 start/end，更精确）
        if df is None or df.empty:
            logger.warning("新浪指数源返回空数据，回退到 akshare stock_zh_index_daily_em（东财源）")
            try:
                df = ak.stock_zh_index_daily_em(
                    symbol=symbol,
                    start_date=start_date or '19900101',
                    end_date=end_date or '20500101',
                )
            except Exception as e:
                logger.warning(f"akshare 东财指数源获取 {index_code} 失败: {e}，回退到 baostock")
                df = pd.DataFrame()

        # 3) baostock（独立服务器，指数用不复权）
        if df is None or df.empty:
            logger.warning("东财指数源返回空数据，回退到 baostock")
            try:
                df = _baostock_query(
                    symbol, start_date, end_date, adjust_str='',
                    fields="date,open,high,low,close,volume,amount",
                )
                if df is not None and not df.empty:
                    for col in ('open', 'high', 'low', 'close', 'volume', 'amount'):
                        if col in df.columns:
                            df[col] = pd.to_numeric(df[col], errors='coerce')
                    if 'volume' in df.columns:
                        df['volume'] = df['volume'] / 100.0  # 股 → 手
            except Exception as e:
                logger.warning(f"baostock 指数获取 {index_code} 失败: {e}")
                df = pd.DataFrame()

        if df is None or df.empty:
            print(f"指数 {index_code} 所有数据源均返回空数据")
            return pd.DataFrame()

        # 统一列名重命名（三条路径都返回小写英文列名）
        from src.data.columns import EN_TO_ZH
        rename_map = {k: v for k, v in EN_TO_ZH.items() if k in df.columns}
        df = df.rename(columns=rename_map)

        # 本地日期过滤（新浪源不支持 start/end；东财/baostock 已过滤，但统一过滤确保一致）
        if '时间' in df.columns:
            df['时间'] = pd.to_datetime(df['时间'])
            if start_date:
                df = df[df['时间'] >= pd.to_datetime(start_date)]
            if end_date:
                df = df[df['时间'] <= pd.to_datetime(end_date)]
            df = df.sort_values('时间').reset_index(drop=True)

        # ---- 回填 DB 缓存层（指数）----
        try:
            from src.data import db as _db
            _db.save_daily(df, str(index_code), market, 'nfq', is_index=True)
        except Exception as _e:
            logger.debug(f"DB 缓存回填失败（指数，不影响主流程）: {_e}")

        print(f"成功获取指数数据，数据行数: {len(df)}")
        return df
    except Exception as e:
        print(f"获取指数数据失败: {e}")
        traceback.print_exc()
        return pd.DataFrame()


def _fetch_us_index_yf(index_code: str = 'SP500', start_date: str = '', end_date: str = '') -> pd.DataFrame:
    """通过 yfinance 获取美股指数日线数据（主数据源）。

    返回小写列名 (date/open/high/low/close/volume) 的 DataFrame，
    以便与 akshare 返回格式一致，复用 get_us_index_data 的列名重命名逻辑。

    :param index_code: US_INDEX_YF_SYMBOLS 的键（如 'SP500'），也接受 Yahoo 原始代码（如 '^GSPC'）
    :param start_date: 'YYYYMMDD'
    :param end_date: 'YYYYMMDD'
    :return: 小写列名 DataFrame；失败返回空 DataFrame
    """
    try:
        import yfinance as yf
    except ImportError:
        logger.warning("yfinance 未安装，跳过 yfinance 指数数据源")
        return pd.DataFrame()

    try:
        symbol = US_INDEX_YF_SYMBOLS.get(str(index_code).upper(), index_code)
        yf_start = f"{start_date[:4]}-{start_date[4:6]}-{start_date[6:8]}" if start_date else None
        if end_date:
            yf_end_dt = pd.to_datetime(end_date, format='%Y%m%d') + pd.Timedelta(days=1)
            yf_end = yf_end_dt.strftime('%Y-%m-%d')
        else:
            yf_end = None

        logger.info(f"yfinance: 获取指数 {symbol} 日线 ({yf_start} ~ {yf_end})")
        df = yf.Ticker(symbol).history(
            start=yf_start, end=yf_end,
            interval='1d', auto_adjust=False,
            actions=False, raise_errors=True,
        )

        if df is None or df.empty:
            return pd.DataFrame()

        df = df.reset_index()
        date_col = 'Date' if 'Date' in df.columns else df.columns[0]
        df[date_col] = pd.to_datetime(df[date_col]).dt.tz_localize(None)
        df.columns = df.columns.str.lower()

        return df
    except Exception as e:
        logger.warning(f"yfinance 获取指数 {index_code} 失败: {e}")
        return pd.DataFrame()


def get_us_index_data(index_code: str = 'SP500', start_date: str = '', end_date: str = '') -> pd.DataFrame:
    """
    获取美股指数日线数据，用于美股回测基准。

    优先使用 yfinance（Yahoo Finance，免费免 key、支持 start/end），
    失败回退 akshare 新浪源（index_us_stock_sina，不支持 start/end 需本地过滤）。
    两条路径均返回统一中文列名（时间/开盘/最高/最低/收盘/成交量/成交额）。

    :param index_code: US_INDEX_SYMBOLS / US_INDEX_YF_SYMBOLS 的键，默认 'SP500'（标普500）。
                       也接受新浪代码（'.INX'）或 Yahoo 代码（'^GSPC'）。
    :param start_date: 开始日期 'YYYYMMDD'
    :param end_date: 结束日期 'YYYYMMDD'，默认今天
    :return: 与 get_index_data 列名一致的 DataFrame。失败时返回空 DataFrame。
    """
    try:
        if not end_date:
            end_date = datetime.now().strftime('%Y%m%d')

        # ---- DB 缓存层（美股指数）----
        try:
            from src.data import db as _db
            _cached = _db.get_cached_range(
                str(index_code), 'us', 'nfq', start_date, end_date, is_index=True,
            )
            if _cached is not None and not _cached.empty:
                logger.info(f"DB 缓存命中 美股指数 {index_code}: {len(_cached)} 行")
                return _cached
        except Exception as _e:
            logger.debug(f"DB 缓存查询失败（美股指数），回退网络链: {_e}")

        print(f"正在获取美股指数 {index_code} 的日线数据，日期范围: {start_date} 至 {end_date}")

        # 优先 yfinance（返回小写列名，已按 start/end 过滤）
        try:
            df = _fetch_us_index_yf(index_code, start_date, end_date)
        except Exception as e:
            logger.warning(f"yfinance 指数获取异常，准备回退: {e}")
            df = pd.DataFrame()

        if df is None or df.empty:
            # 回退 akshare 新浪源（不支持 start/end，需本地过滤）
            logger.warning("yfinance 指数数据为空，回退到 akshare index_us_stock_sina（新浪源）")
            symbol = US_INDEX_SYMBOLS.get(str(index_code).upper(), index_code)
            df = ak.index_us_stock_sina(symbol=symbol)
            if df is None or df.empty:
                print(f"美股指数 {index_code} 返回空数据")
                return pd.DataFrame()
            # 本地日期过滤（小写 date 列）
            if 'date' in df.columns:
                df['date'] = pd.to_datetime(df['date'])
                if start_date:
                    df = df[df['date'] >= pd.to_datetime(start_date)]
                if end_date:
                    df = df[df['date'] <= pd.to_datetime(end_date)]
                df = df.sort_values('date').reset_index(drop=True)

        if df is None or df.empty:
            return pd.DataFrame()

        # 统一列名重命名（两条路径都返回小写列名）
        from src.data.columns import EN_TO_ZH
        rename_map = {k: v for k, v in EN_TO_ZH.items() if k in df.columns}
        df = df.rename(columns=rename_map)

        # ---- 回填 DB 缓存层（美股指数）----
        try:
            from src.data import db as _db
            _db.save_daily(df, str(index_code), 'us', 'nfq', is_index=True)
        except Exception as _e:
            logger.debug(f"DB 缓存回填失败（美股指数，不影响主流程）: {_e}")

        print(f"成功获取美股指数数据，数据行数: {len(df)}")
        return df
    except Exception as e:
        print(f"获取美股指数数据失败: {e}")
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