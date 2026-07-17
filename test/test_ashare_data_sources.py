"""A股数据源多级回退测试（Tushare → 新浪源 → 东财源 → baostock）。

覆盖：
- _fetch_ashare_tushare：Tushare Pro ts_code 转换、trade_date/vol 列名归一化、amount 千元→元、无 token 跳过
- _fetch_ashare_hist_em：东财源 symbol 转换、中文列名→小写英文、异常处理
- _fetch_ashare_baostock：baostock code 转换、volume 单位转换、数值类型转换
- _to_baostock_code：sh600000 → sh.600000
- BAOSTOCK_ADJUST_MAP：复权标识映射（与 akshare 相反）
- get_stock_data A股分支：四级回退逻辑（Tushare→新浪→东财→baostock）
- get_index_data A股分支：四级回退逻辑

运行：pytest test/test_ashare_data_sources.py -v
（需在项目 conda 环境 qdt 中，依赖 akshare/baostock/pandas）
"""
import os
import sys

import pandas as pd
import pytest
from unittest.mock import patch, MagicMock

# 确保项目根在 sys.path（从 test/ 目录直接 pytest 时也生效）
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)


@pytest.fixture(autouse=True)
def _disable_db_cache(monkeypatch):
    """禁用 DB/Redis 缓存层（本文件专门测网络回退链，不应被缓存命中短路）。

    若不禁用，Docker 起着时 get_stock_data 会命中 PG 缓存提前返回，
    网络源 mock 不会被调用，破坏回退链断言。
    """
    import src.data.db as _db
    monkeypatch.setattr(_db, 'DB_CACHE_ENABLED', False)
    monkeypatch.setattr(_db, 'REDIS_CACHE_ENABLED', False)


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------
def _make_sina_daily_df(n=5):
    """模拟 ak.stock_zh_a_daily（新浪源）返回：小写英文列名。"""
    return pd.DataFrame({
        'date': pd.date_range('2024-01-02', periods=n, freq='B'),
        'open': [10.0 + i for i in range(n)],
        'high': [10.5 + i for i in range(n)],
        'low': [9.8 + i for i in range(n)],
        'close': [10.2 + i for i in range(n)],
        'volume': [100000 + i * 1000 for i in range(n)],
        'amount': [1000000 + i * 10000 for i in range(n)],
    })


def _make_em_hist_df(n=5):
    """模拟 ak.stock_zh_a_hist（东财源）返回：中文列名。"""
    return pd.DataFrame({
        '日期': pd.date_range('2024-01-02', periods=n, freq='B'),
        '股票代码': ['000001'] * n,
        '开盘': [10.0 + i for i in range(n)],
        '收盘': [10.2 + i for i in range(n)],
        '最高': [10.5 + i for i in range(n)],
        '最低': [9.8 + i for i in range(n)],
        '成交量': [100000 + i * 1000 for i in range(n)],
        '成交额': [1000000 + i * 10000 for i in range(n)],
        '振幅': [1.5] * n,
        '涨跌幅': [0.2] * n,
        '涨跌额': [0.02] * n,
        '换手率': [0.5] * n,
    })


def _make_baostock_df(n=5):
    """模拟 baostock query_history_k_data_plus 返回：字符串数值、volume 单位为股。"""
    return pd.DataFrame({
        'date': ['2024-01-02', '2024-01-03', '2024-01-04', '2024-01-05', '2024-01-08'][:n],
        'open': ['10.00', '11.00', '12.00', '13.00', '14.00'][:n],
        'high': ['10.50', '11.50', '12.50', '13.50', '14.50'][:n],
        'low': ['9.80', '10.80', '11.80', '12.80', '13.80'][:n],
        'close': ['10.20', '11.20', '12.20', '13.20', '14.20'][:n],
        'volume': ['10000000', '11000000', '12000000', '13000000', '14000000'][:n],
        'amount': ['1000000', '1100000', '1200000', '1300000', '1400000'][:n],
    })


def _make_tushare_df(n=5):
    """模拟 Tushare pro.daily 返回：trade_date(YYYYMMDD)、vol(手)、amount(千元)。"""
    return pd.DataFrame({
        'ts_code': ['000001.SZ'] * n,
        'trade_date': ['20240102', '20240103', '20240104', '20240105', '20240108'][:n],
        'open': [10.0 + i for i in range(n)],
        'high': [10.5 + i for i in range(n)],
        'low': [9.8 + i for i in range(n)],
        'close': [10.2 + i for i in range(n)],
        'vol': [100000 + i * 1000 for i in range(n)],          # 手
        'amount': [100000.0 + i * 10000.0 for i in range(n)],  # 千元
    })


# ---------------------------------------------------------------------------
# _to_baostock_code
# ---------------------------------------------------------------------------
class TestToBaostockCode:
    """baostock 代码格式转换测试。"""

    def test_sh_prefix(self):
        from src.data.data_manager import _to_baostock_code
        assert _to_baostock_code('sh600000') == 'sh.600000'

    def test_sz_prefix(self):
        from src.data.data_manager import _to_baostock_code
        assert _to_baostock_code('sz000001') == 'sz.000001'

    def test_index_sh(self):
        from src.data.data_manager import _to_baostock_code
        assert _to_baostock_code('sh000300') == 'sh.000300'

    def test_no_prefix_passthrough(self):
        from src.data.data_manager import _to_baostock_code
        assert _to_baostock_code('600000') == '600000'


# ---------------------------------------------------------------------------
# BAOSTOCK_ADJUST_MAP
# ---------------------------------------------------------------------------
class TestBaostockAdjustMap:
    """baostock 复权标识映射测试（与 akshare 含义相反）。"""

    def test_nfq_maps_to_3(self):
        from src.data.data_manager import BAOSTOCK_ADJUST_MAP
        assert BAOSTOCK_ADJUST_MAP['nfq'] == '3'
        assert BAOSTOCK_ADJUST_MAP[''] == '3'

    def test_qfq_maps_to_2(self):
        from src.data.data_manager import BAOSTOCK_ADJUST_MAP
        assert BAOSTOCK_ADJUST_MAP['qfq'] == '2'

    def test_hfq_maps_to_1(self):
        from src.data.data_manager import BAOSTOCK_ADJUST_MAP
        assert BAOSTOCK_ADJUST_MAP['hfq'] == '1'


# ---------------------------------------------------------------------------
# _fetch_ashare_hist_em（东财源）
# ---------------------------------------------------------------------------
class TestFetchAshareHistEM:
    """akshare 东财源 (stock_zh_a_hist) 数据获取测试。"""

    @patch('akshare.stock_zh_a_hist')
    def test_symbol_without_prefix(self, mock_hist):
        """东财源 symbol 应为纯6位代码（不带 sh/sz 前缀）。"""
        mock_hist.return_value = _make_em_hist_df()
        from src.data.data_manager import Stock
        stock = Stock('000001', market='zh_a')
        stock._fetch_ashare_hist_em('20240101', '20240131', 'hfq')

        _, kwargs = mock_hist.call_args
        assert kwargs['symbol'] == '000001', "东财源 symbol 不应带 sh/sz 前缀"
        assert kwargs['period'] == 'daily'

    @patch('akshare.stock_zh_a_hist')
    def test_chinese_to_lowercase_columns(self, mock_hist):
        """东财源中文列名应转为小写英文，以便复用 rename_map。"""
        mock_hist.return_value = _make_em_hist_df()
        from src.data.data_manager import Stock
        stock = Stock('000001', market='zh_a')
        df = stock._fetch_ashare_hist_em('20240101', '20240131', 'hfq')

        for col in ('date', 'open', 'high', 'low', 'close', 'volume', 'amount'):
            assert col in df.columns, f"缺少小写列: {col}"

    @patch('akshare.stock_zh_a_hist')
    def test_empty_returns_empty(self, mock_hist):
        """东财源返回空时应返回空 DataFrame。"""
        mock_hist.return_value = pd.DataFrame()
        from src.data.data_manager import Stock
        stock = Stock('000001', market='zh_a')
        df = stock._fetch_ashare_hist_em('20240101', '20240131', 'hfq')
        assert df.empty

    @patch('akshare.stock_zh_a_hist')
    def test_exception_returns_empty(self, mock_hist):
        """东财源异常时应返回空 DataFrame（触发回退）。"""
        mock_hist.side_effect = Exception("ConnectionError")
        from src.data.data_manager import Stock
        stock = Stock('000001', market='zh_a')
        df = stock._fetch_ashare_hist_em('20240101', '20240131', 'hfq')
        assert df.empty

    @patch('akshare.stock_zh_a_hist')
    def test_adjust_passed_through(self, mock_hist):
        """adjust 参数应透传给东财源。"""
        mock_hist.return_value = _make_em_hist_df()
        from src.data.data_manager import Stock
        stock = Stock('000001', market='zh_a')
        stock._fetch_ashare_hist_em('20240101', '20240131', 'qfq')

        _, kwargs = mock_hist.call_args
        assert kwargs['adjust'] == 'qfq'


# ---------------------------------------------------------------------------
# _fetch_ashare_tushare（Tushare Pro，可选首选源）
# ---------------------------------------------------------------------------
class TestFetchAshareTushare:
    """Tushare Pro A股个股数据获取测试。"""

    @patch('src.data.data_manager._TUSHARE_TOKEN', 'fake-token')
    @patch('tushare.pro_api')
    @patch('tushare.set_token')
    def test_column_normalization(self, _set_tok, mock_pro_api):
        """Tushare trade_date/vol 列应归一化为 date/volume（小写英文）。"""
        mock_pro = MagicMock()
        mock_pro.daily.return_value = _make_tushare_df()
        mock_pro_api.return_value = mock_pro
        from src.data.data_manager import Stock
        stock = Stock('000001', market='zh_a')
        df = stock._fetch_ashare_tushare('20240101', '20240131', '')

        assert not df.empty
        for col in ('date', 'open', 'high', 'low', 'close', 'volume', 'amount'):
            assert col in df.columns, f"缺少归一化列: {col}"
        # trade_date 不应残留
        assert 'trade_date' not in df.columns

    @patch('src.data.data_manager._TUSHARE_TOKEN', 'fake-token')
    @patch('tushare.pro_api')
    @patch('tushare.set_token')
    def test_ts_code_conversion(self, _set_tok, mock_pro_api):
        """sh 前缀股票应转为 600938.SH 格式调用 Tushare。"""
        mock_pro = MagicMock()
        mock_pro.daily.return_value = _make_tushare_df()
        mock_pro_api.return_value = mock_pro
        from src.data.data_manager import Stock
        stock = Stock('600938', market='zh_a')
        stock._fetch_ashare_tushare('20240101', '20240131', '')

        _, kwargs = mock_pro.daily.call_args
        assert kwargs['ts_code'] == '600938.SH', "Tushare ts_code 应为 600938.SH 格式"

    @patch('src.data.data_manager._TUSHARE_TOKEN', 'fake-token')
    @patch('tushare.pro_api')
    @patch('tushare.set_token')
    def test_amount_thousand_to_yuan(self, _set_tok, mock_pro_api):
        """Tushare amount 单位千元应 ×1000 转为元（与 akshare 对齐）。"""
        mock_pro = MagicMock()
        mock_pro.daily.return_value = _make_tushare_df()
        mock_pro_api.return_value = mock_pro
        from src.data.data_manager import Stock
        stock = Stock('000001', market='zh_a')
        df = stock._fetch_ashare_tushare('20240101', '20240131', '')

        # 原始 amount[0] = 100000 千元 → 100000000 元
        assert df['amount'].iloc[0] == pytest.approx(100000000.0, rel=1e-6)

    @patch('src.data.data_manager._TUSHARE_TOKEN', 'fake-token')
    @patch('tushare.pro_api')
    @patch('tushare.set_token')
    def test_adjust_qfq_uses_pro_bar(self, _set_tok, mock_pro_api):
        """adjust='qfq' 时应改用 ts.pro_bar（pro.daily 仅返回不复权）。"""
        mock_pro = MagicMock()
        mock_pro_api.return_value = mock_pro
        from src.data.data_manager import Stock
        with patch('tushare.pro_bar', return_value=_make_tushare_df()) as mock_bar:
            stock = Stock('000001', market='zh_a')
            stock._fetch_ashare_tushare('20240101', '20240131', 'qfq')
            assert mock_bar.called, "qfq 应调用 pro_bar"
            assert not mock_pro.daily.called, "qfq 不应调用 pro.daily"

    @patch('src.data.data_manager._TUSHARE_TOKEN', '')
    def test_no_token_returns_empty(self):
        """无 TUSHARE_TOKEN 时应静默返回空（跳过该层）。"""
        from src.data.data_manager import Stock
        stock = Stock('000001', market='zh_a')
        df = stock._fetch_ashare_tushare('20240101', '20240131', '')
        assert df.empty, "无 token 应返回空 DataFrame 以触发回退"

    @patch('src.data.data_manager._TUSHARE_TOKEN', 'fake-token')
    @patch('tushare.pro_api')
    @patch('tushare.set_token')
    def test_empty_returns_empty(self, _set_tok, mock_pro_api):
        """Tushare 返回空时应返回空 DataFrame（触发回退）。"""
        mock_pro = MagicMock()
        mock_pro.daily.return_value = pd.DataFrame()
        mock_pro_api.return_value = mock_pro
        from src.data.data_manager import Stock
        stock = Stock('000001', market='zh_a')
        df = stock._fetch_ashare_tushare('20240101', '20240131', '')
        assert df.empty

    @patch('src.data.data_manager._TUSHARE_TOKEN', 'fake-token')
    @patch('tushare.pro_api')
    @patch('tushare.set_token')
    def test_exception_returns_empty(self, _set_tok, mock_pro_api):
        """Tushare 异常时应返回空 DataFrame（触发回退）。"""
        mock_pro = MagicMock()
        mock_pro.daily.side_effect = Exception("token invalid")
        mock_pro_api.return_value = mock_pro
        from src.data.data_manager import Stock
        stock = Stock('000001', market='zh_a')
        df = stock._fetch_ashare_tushare('20240101', '20240131', '')
        assert df.empty


# ---------------------------------------------------------------------------
# _fetch_ashare_baostock
# ---------------------------------------------------------------------------
class TestFetchAshareBaostock:
    """baostock A股个股数据获取测试。"""

    @patch('src.data.data_manager._baostock_query')
    def test_volume_divided_by_100(self, mock_bs):
        """baostock volume 单位是股，应 /100 转为手。"""
        mock_bs.return_value = _make_baostock_df()
        from src.data.data_manager import Stock
        stock = Stock('000001', market='zh_a')
        df = stock._fetch_ashare_baostock('20240101', '20240131', 'hfq')

        assert not df.empty
        # 原始 volume 10000000 股 → 100000 手
        assert df['volume'].iloc[0] == pytest.approx(100000.0, rel=1e-6)

    @patch('src.data.data_manager._baostock_query')
    def test_numeric_conversion(self, mock_bs):
        """baostock 返回字符串，应转为 float。"""
        mock_bs.return_value = _make_baostock_df()
        from src.data.data_manager import Stock
        stock = Stock('000001', market='zh_a')
        df = stock._fetch_ashare_baostock('20240101', '20240131', 'hfq')

        for col in ('open', 'high', 'low', 'close', 'volume', 'amount'):
            assert pd.api.types.is_numeric_dtype(df[col]), f"{col} 应为数值类型"

    @patch('src.data.data_manager._baostock_query')
    def test_code_conversion(self, mock_bs):
        """应将 sh600000 转为 baostock 格式调用。"""
        mock_bs.return_value = _make_baostock_df()
        from src.data.data_manager import Stock
        stock = Stock('600000', market='zh_a')
        stock._fetch_ashare_baostock('20240101', '20240131', 'hfq')

        args, _ = mock_bs.call_args
        # _baostock_query(code_with_prefix, ...) 第一个参数是 sh600000 格式
        assert args[0] == 'sh600000'

    @patch('src.data.data_manager._baostock_query')
    def test_empty_returns_empty(self, mock_bs):
        """baostock 返回空时应返回空 DataFrame。"""
        mock_bs.return_value = pd.DataFrame()
        from src.data.data_manager import Stock
        stock = Stock('000001', market='zh_a')
        df = stock._fetch_ashare_baostock('20240101', '20240131', 'hfq')
        assert df.empty

    @patch('src.data.data_manager._baostock_query')
    def test_exception_returns_empty(self, mock_bs):
        """baostock 异常时应返回空 DataFrame。"""
        mock_bs.side_effect = Exception("login failed")
        from src.data.data_manager import Stock
        stock = Stock('000001', market='zh_a')
        df = stock._fetch_ashare_baostock('20240101', '20240131', 'hfq')
        assert df.empty


# ---------------------------------------------------------------------------
# get_stock_data A股回退链
# ---------------------------------------------------------------------------
class TestAshareStockFallback:
    """get_stock_data A股分支回退链逻辑测试。

    回退顺序：Tushare(可选) → 新浪 → 东财 → baostock。
    既有用例 patch _fetch_ashare_tushare 返回空，以隔离测「新浪→东财→baostock」段。
    """

    @patch('src.data.data_manager.Stock._fetch_ashare_tushare')
    @patch('src.data.data_manager.Stock._fetch_ashare_baostock')
    @patch('src.data.data_manager.Stock._fetch_ashare_hist_em')
    @patch('akshare.stock_zh_a_daily')
    def test_sina_success_no_fallback(self, mock_sina, mock_em, mock_bs, mock_ts):
        """Tushare 空 + 新浪源成功时不继续回退。"""
        mock_ts.return_value = pd.DataFrame()
        mock_sina.return_value = _make_sina_daily_df()
        from src.data.data_manager import Stock
        stock = Stock('000001', market='zh_a')
        df, _ = stock.get_stock_data('20240101', '20240131', adjust='hfq', type='daily')

        assert mock_sina.called
        assert not mock_em.called, "新浪源成功时不应回退到东财"
        assert not mock_bs.called, "新浪源成功时不应回退到 baostock"
        assert not df.empty
        assert '时间' in df.columns
        assert '收盘' in df.columns

    @patch('src.data.data_manager.Stock._fetch_ashare_tushare')
    @patch('src.data.data_manager.Stock._fetch_ashare_baostock')
    @patch('src.data.data_manager.Stock._fetch_ashare_hist_em')
    @patch('akshare.stock_zh_a_daily')
    def test_sina_empty_fallback_to_em(self, mock_sina, mock_em, mock_bs, mock_ts):
        """Tushare 空 + 新浪源返回空时回退到东财源。"""
        mock_ts.return_value = pd.DataFrame()
        mock_sina.return_value = pd.DataFrame()
        mock_em.return_value = _make_em_hist_df().rename(columns={
            '日期': 'date', '开盘': 'open', '最高': 'high', '最低': 'low',
            '收盘': 'close', '成交量': 'volume', '成交额': 'amount',
        })
        from src.data.data_manager import Stock
        stock = Stock('000001', market='zh_a')
        df, _ = stock.get_stock_data('20240101', '20240131', adjust='hfq', type='daily')

        assert mock_sina.called
        assert mock_em.called, "新浪源空时应回退到东财"
        assert not mock_bs.called, "东财源成功时不应回退到 baostock"
        assert not df.empty

    @patch('src.data.data_manager.Stock._fetch_ashare_tushare')
    @patch('src.data.data_manager.Stock._fetch_ashare_baostock')
    @patch('src.data.data_manager.Stock._fetch_ashare_hist_em')
    @patch('akshare.stock_zh_a_daily')
    def test_sina_em_empty_fallback_to_baostock(self, mock_sina, mock_em, mock_bs, mock_ts):
        """Tushare 空 + 新浪和东财都空时回退到 baostock。"""
        mock_ts.return_value = pd.DataFrame()
        mock_sina.return_value = pd.DataFrame()
        mock_em.return_value = pd.DataFrame()
        mock_bs.return_value = _make_baostock_df()
        from src.data.data_manager import Stock
        stock = Stock('000001', market='zh_a')
        df, _ = stock.get_stock_data('20240101', '20240131', adjust='hfq', type='daily')

        assert mock_em.called, "应尝试东财源"
        assert mock_bs.called, "新浪和东财都空时应回退到 baostock"
        assert not df.empty
        assert '时间' in df.columns

    @patch('src.data.data_manager.Stock._fetch_ashare_tushare')
    @patch('src.data.data_manager.Stock._fetch_ashare_baostock')
    @patch('src.data.data_manager.Stock._fetch_ashare_hist_em')
    @patch('akshare.stock_zh_a_daily')
    def test_sina_exception_fallback_to_em(self, mock_sina, mock_em, mock_bs, mock_ts):
        """Tushare 空 + 新浪源异常时回退到东财源。"""
        mock_ts.return_value = pd.DataFrame()
        mock_sina.side_effect = Exception("sina blocked")
        mock_em.return_value = _make_em_hist_df().rename(columns={
            '日期': 'date', '开盘': 'open', '最高': 'high', '最低': 'low',
            '收盘': 'close', '成交量': 'volume', '成交额': 'amount',
        })
        from src.data.data_manager import Stock
        stock = Stock('000001', market='zh_a')
        df, _ = stock.get_stock_data('20240101', '20240131', adjust='hfq', type='daily')

        assert mock_em.called, "新浪源异常时应回退到东财"
        assert not mock_bs.called
        assert not df.empty

    @patch('src.data.data_manager.Stock._fetch_ashare_tushare')
    @patch('src.data.data_manager.Stock._fetch_ashare_baostock')
    @patch('src.data.data_manager.Stock._fetch_ashare_hist_em')
    @patch('akshare.stock_zh_a_daily')
    def test_all_sources_empty_returns_empty(self, mock_sina, mock_em, mock_bs, mock_ts):
        """所有数据源都空时返回空 DataFrame。"""
        mock_ts.return_value = pd.DataFrame()
        mock_sina.return_value = pd.DataFrame()
        mock_em.return_value = pd.DataFrame()
        mock_bs.return_value = pd.DataFrame()
        from src.data.data_manager import Stock
        stock = Stock('000001', market='zh_a')
        df, _ = stock.get_stock_data('20240101', '20240131', adjust='hfq', type='daily')

        assert df.empty

    @patch('src.data.data_manager.Stock._fetch_ashare_tushare')
    @patch('src.data.data_manager.Stock._fetch_ashare_baostock')
    @patch('src.data.data_manager.Stock._fetch_ashare_hist_em')
    @patch('akshare.stock_zh_a_daily')
    def test_column_contract_preserved(self, mock_sina, mock_em, mock_bs, mock_ts):
        """无论哪个源成功，最终列名都应是中文契约（时间/开盘/最高/最低/收盘/成交量）。"""
        mock_ts.return_value = pd.DataFrame()
        mock_sina.return_value = _make_sina_daily_df()
        from src.data.data_manager import Stock
        stock = Stock('000001', market='zh_a')
        df, _ = stock.get_stock_data('20240101', '20240131', adjust='hfq', type='daily')

        for col in ('时间', '开盘', '最高', '最低', '收盘', '成交量'):
            assert col in df.columns, f"缺少中文列: {col}"

    # --- Tushare 作为首选层的新用例 ---
    @patch('src.data.data_manager._TUSHARE_TOKEN', 'fake-token')
    @patch('src.data.data_manager.Stock._fetch_ashare_tushare')
    @patch('src.data.data_manager.Stock._fetch_ashare_baostock')
    @patch('src.data.data_manager.Stock._fetch_ashare_hist_em')
    @patch('akshare.stock_zh_a_daily')
    def test_tushare_success_no_further_fallback(self, mock_sina, mock_em, mock_bs, mock_ts):
        """Tushare 命中时不应调用新浪/东财/baostock。"""
        # _fetch_ashare_tushare 内部已归一化为小写英文列，这里返回归一化后的形状
        mock_ts.return_value = _make_sina_daily_df()
        from src.data.data_manager import Stock
        stock = Stock('000001', market='zh_a')
        df, _ = stock.get_stock_data('20240101', '20240131', adjust='hfq', type='daily')

        assert mock_ts.called, "应首选 Tushare"
        assert not mock_sina.called, "Tushare 成功时不应回退到新浪"
        assert not mock_em.called
        assert not mock_bs.called
        assert not df.empty
        # Tushare 路径同样满足中文列契约
        assert '时间' in df.columns
        assert '收盘' in df.columns

    @patch('src.data.data_manager._TUSHARE_TOKEN', 'fake-token')
    @patch('src.data.data_manager.Stock._fetch_ashare_tushare')
    @patch('src.data.data_manager.Stock._fetch_ashare_baostock')
    @patch('src.data.data_manager.Stock._fetch_ashare_hist_em')
    @patch('akshare.stock_zh_a_daily')
    def test_tushare_empty_falls_to_sina(self, mock_sina, mock_em, mock_bs, mock_ts):
        """Tushare 返回空时应回退到新浪源。"""
        mock_ts.return_value = pd.DataFrame()
        mock_sina.return_value = _make_sina_daily_df()
        from src.data.data_manager import Stock
        stock = Stock('000001', market='zh_a')
        df, _ = stock.get_stock_data('20240101', '20240131', adjust='hfq', type='daily')

        assert mock_ts.called, "应先试 Tushare"
        assert mock_sina.called, "Tushare 空时应回退到新浪"
        assert not mock_em.called, "新浪成功不应继续回退"
        assert not df.empty


# ---------------------------------------------------------------------------
# get_index_data A股回退链
# ---------------------------------------------------------------------------
class TestAshareIndexFallback:
    """get_index_data A股分支回退链逻辑测试。

    回退顺序：Tushare(可选) → 新浪 → 东财 → baostock。
    既有用例 patch tushare.pro_api 返回空，以隔离测「新浪→东财→baostock」段。
    """

    @patch('tushare.pro_api')
    @patch('src.data.data_manager._baostock_query')
    @patch('akshare.stock_zh_index_daily_em')
    @patch('akshare.stock_zh_index_daily')
    def test_sina_index_success_no_fallback(self, mock_sina, mock_em, mock_bs, mock_ts):
        """Tushare 空 + 新浪指数源成功时不回退。"""
        mock_ts.return_value = MagicMock()
        mock_ts.return_value.index_daily.return_value = pd.DataFrame()
        mock_sina.return_value = _make_sina_daily_df()
        from src.data.data_manager import get_index_data
        df = get_index_data('000300', '20240101', '20240131', market='zh_a')

        assert mock_sina.called
        assert not mock_em.called
        assert not mock_bs.called
        assert not df.empty
        assert '时间' in df.columns
        assert '收盘' in df.columns

    @patch('tushare.pro_api')
    @patch('src.data.data_manager._baostock_query')
    @patch('akshare.stock_zh_index_daily_em')
    @patch('akshare.stock_zh_index_daily')
    def test_sina_index_empty_fallback_to_em(self, mock_sina, mock_em, mock_bs, mock_ts):
        """Tushare 空 + 新浪指数源空时回退到东财指数源。"""
        mock_ts.return_value = MagicMock()
        mock_ts.return_value.index_daily.return_value = pd.DataFrame()
        mock_sina.return_value = pd.DataFrame()
        mock_em.return_value = _make_sina_daily_df()
        from src.data.data_manager import get_index_data
        df = get_index_data('000300', '20240101', '20240131', market='zh_a')

        assert mock_sina.called
        assert mock_em.called, "新浪指数源空时应回退到东财"
        assert not mock_bs.called
        assert not df.empty

    @patch('tushare.pro_api')
    @patch('src.data.data_manager._baostock_query')
    @patch('akshare.stock_zh_index_daily_em')
    @patch('akshare.stock_zh_index_daily')
    def test_sina_em_index_empty_fallback_to_baostock(self, mock_sina, mock_em, mock_bs, mock_ts):
        """Tushare 空 + 新浪和东财指数源都空时回退到 baostock。"""
        mock_ts.return_value = MagicMock()
        mock_ts.return_value.index_daily.return_value = pd.DataFrame()
        mock_sina.return_value = pd.DataFrame()
        mock_em.return_value = pd.DataFrame()
        mock_bs.return_value = _make_baostock_df()
        from src.data.data_manager import get_index_data
        df = get_index_data('000300', '20240101', '20240131', market='zh_a')

        assert mock_em.called
        assert mock_bs.called, "新浪和东财都空时应回退到 baostock"
        assert not df.empty
        assert '时间' in df.columns

    @patch('tushare.pro_api')
    @patch('src.data.data_manager._baostock_query')
    @patch('akshare.stock_zh_index_daily_em')
    @patch('akshare.stock_zh_index_daily')
    def test_sina_index_exception_fallback(self, mock_sina, mock_em, mock_bs, mock_ts):
        """Tushare 空 + 新浪指数源异常时回退到东财。"""
        mock_ts.return_value = MagicMock()
        mock_ts.return_value.index_daily.return_value = pd.DataFrame()
        mock_sina.side_effect = Exception("sina blocked")
        mock_em.return_value = _make_sina_daily_df()
        from src.data.data_manager import get_index_data
        df = get_index_data('000300', '20240101', '20240131', market='zh_a')

        assert mock_em.called, "新浪指数源异常时应回退"
        assert not df.empty

    @patch('tushare.pro_api')
    @patch('src.data.data_manager._baostock_query')
    @patch('akshare.stock_zh_index_daily_em')
    @patch('akshare.stock_zh_index_daily')
    def test_index_date_filter_applied(self, mock_sina, mock_em, mock_bs, mock_ts):
        """指数数据应做本地日期过滤。"""
        mock_ts.return_value = MagicMock()
        mock_ts.return_value.index_daily.return_value = pd.DataFrame()
        # 新浪源返回超范围数据
        df_full = pd.DataFrame({
            'date': pd.to_datetime(['2023-12-25', '2024-01-02', '2024-01-03', '2024-02-15']),
            'open': [4000, 4010, 4020, 4030],
            'high': [4020, 4030, 4040, 4050],
            'low': [3990, 4000, 4010, 4020],
            'close': [4010, 4020, 4030, 4040],
            'volume': [1000000, 1100000, 1200000, 1300000],
            'amount': [1e8, 1.1e8, 1.2e8, 1.3e8],
        })
        mock_sina.return_value = df_full
        from src.data.data_manager import get_index_data
        df = get_index_data('000300', '20240101', '20240131', market='zh_a')

        assert len(df) == 2, "应只保留 2024-01-02 和 2024-01-03"
        dates = pd.to_datetime(df['时间'])
        assert dates.min() >= pd.to_datetime('20240101')
        assert dates.max() <= pd.to_datetime('20240131')

    @patch('tushare.pro_api')
    @patch('src.data.data_manager._baostock_query')
    @patch('akshare.stock_zh_index_daily_em')
    @patch('akshare.stock_zh_index_daily')
    def test_index_all_empty_returns_empty(self, mock_sina, mock_em, mock_bs, mock_ts):
        """所有指数源都空时返回空。"""
        mock_ts.return_value = MagicMock()
        mock_ts.return_value.index_daily.return_value = pd.DataFrame()
        mock_sina.return_value = pd.DataFrame()
        mock_em.return_value = pd.DataFrame()
        mock_bs.return_value = pd.DataFrame()
        from src.data.data_manager import get_index_data
        df = get_index_data('000300', '20240101', '20240131', market='zh_a')

        assert df.empty


# ---------------------------------------------------------------------------
# 真实网络测试（网络不可用时 skip）
# ---------------------------------------------------------------------------
class TestRealAshareData:
    """真实 A 股数据拉取测试。网络不可用时自动 skip。"""

    def test_real_index_data(self):
        """端到端测试 get_index_data 返回中文列名。"""
        from src.data.data_manager import get_index_data
        df = get_index_data('000300', '20240101', '20240131', market='zh_a')

        if df.empty:
            pytest.skip("网络不可用")

        assert '时间' in df.columns
        assert '收盘' in df.columns
        assert '开盘' in df.columns
        assert '最高' in df.columns
        assert '最低' in df.columns
        assert '成交量' in df.columns
        assert len(df) > 15, "2024年1月应有超过15个交易日"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
