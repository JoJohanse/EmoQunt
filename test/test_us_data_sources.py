"""美股数据源测试（yfinance 主源 + akshare 回退）。

覆盖：
- _fetch_us_stock_yf：列名小写化、时区去除、end+1day 排他修正、auto_adjust 映射
- _fetch_us_index_yf：指数代码映射、列名处理
- get_us_index_data：yfinance→akshare 回退逻辑
- US_INDEX_YF_SYMBOLS：代码映射完整性
- 真实 yfinance 网络拉取（AAPL / SP500，网络不可用时 skip）

运行：pytest test/test_us_data_sources.py -v
（需在项目 conda 环境 qdt 中，依赖 yfinance/pandas/numpy）
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


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------
def _make_yf_stock_df(n=5, with_tz=True):
    """构造模拟 yfinance Ticker.history() 返回的个股 DataFrame。"""
    dates = pd.date_range('2024-01-02', periods=n, freq='B')
    if with_tz:
        dates = dates.tz_localize('America/New_York')
    df = pd.DataFrame({
        'Open': [180.0 + i for i in range(n)],
        'High': [182.0 + i for i in range(n)],
        'Low': [179.0 + i for i in range(n)],
        'Close': [181.0 + i for i in range(n)],
        'Volume': [1000000 + i * 10000 for i in range(n)],
    }, index=dates)
    df.index.name = 'Date'
    return df


def _make_yf_index_df(n=5):
    """构造模拟 yfinance Ticker.history() 返回的指数 DataFrame。"""
    dates = pd.date_range('2024-01-02', periods=n, freq='B')
    dates = dates.tz_localize('America/New_York')
    df = pd.DataFrame({
        'Open': [4000.0 + i for i in range(n)],
        'High': [4020.0 + i for i in range(n)],
        'Low': [3990.0 + i for i in range(n)],
        'Close': [4010.0 + i for i in range(n)],
        'Volume': [1000000 + i * 10000 for i in range(n)],
    }, index=dates)
    df.index.name = 'Date'
    return df


# ---------------------------------------------------------------------------
# yfinance 个股数据获取
# ---------------------------------------------------------------------------
class TestYFinanceStockData:
    """yfinance 美股个股数据获取测试。"""

    @patch('yfinance.Ticker')
    def test_columns_lowercase(self, mock_ticker_cls):
        """yfinance 大写列名应转为小写，便于复用现有 rename_map。"""
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = _make_yf_stock_df()
        mock_ticker_cls.return_value = mock_ticker

        from src.data.data_manager import Stock
        stock = Stock('AAPL', market='us')
        df = stock._fetch_us_stock_yf('AAPL', '20240101', '20240131', 'qfq')

        assert not df.empty
        for col in ('date', 'open', 'high', 'low', 'close', 'volume'):
            assert col in df.columns, f"缺少小写列: {col}"

    @patch('yfinance.Ticker')
    def test_timezone_stripped(self, mock_ticker_cls):
        """yfinance 返回的 Date 带时区，应去除时区信息。"""
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = _make_yf_stock_df(with_tz=True)
        mock_ticker_cls.return_value = mock_ticker

        from src.data.data_manager import Stock
        stock = Stock('AAPL', market='us')
        df = stock._fetch_us_stock_yf('AAPL', '20240101', '20240131', 'qfq')

        assert 'date' in df.columns
        assert df['date'].dt.tz is None, "date 列仍带时区信息"

    @patch('yfinance.Ticker')
    def test_end_date_exclusive_plus_one_day(self, mock_ticker_cls):
        """yfinance end 参数是排他的，应传 end+1 天以包含当天。"""
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = _make_yf_stock_df()
        mock_ticker_cls.return_value = mock_ticker

        from src.data.data_manager import Stock
        stock = Stock('AAPL', market='us')
        stock._fetch_us_stock_yf('AAPL', '20240101', '20240131', 'qfq')

        _, kwargs = mock_ticker.history.call_args
        assert kwargs['start'] == '2024-01-01'
        assert kwargs['end'] == '2024-02-01', "end 应为 2024-01-31 + 1天"

    @patch('yfinance.Ticker')
    def test_auto_adjust_mapping(self, mock_ticker_cls):
        """adjust_str 到 auto_adjust 映射：qfq/hfq→True，nfq('')→False。"""
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = _make_yf_stock_df()
        mock_ticker_cls.return_value = mock_ticker

        from src.data.data_manager import Stock
        stock = Stock('AAPL', market='us')

        stock._fetch_us_stock_yf('AAPL', '20240101', '20240131', 'qfq')
        assert mock_ticker.history.call_args.kwargs['auto_adjust'] is True

        stock._fetch_us_stock_yf('AAPL', '20240101', '20240131', 'hfq')
        assert mock_ticker.history.call_args.kwargs['auto_adjust'] is True

        stock._fetch_us_stock_yf('AAPL', '20240101', '20240131', '')
        assert mock_ticker.history.call_args.kwargs['auto_adjust'] is False

    @patch('yfinance.Ticker')
    def test_empty_returns_empty(self, mock_ticker_cls):
        """yfinance 返回空 DataFrame 时应返回空。"""
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = pd.DataFrame()
        mock_ticker_cls.return_value = mock_ticker

        from src.data.data_manager import Stock
        stock = Stock('AAPL', market='us')
        df = stock._fetch_us_stock_yf('AAPL', '20240101', '20240131', 'qfq')
        assert df.empty

    @patch('yfinance.Ticker')
    def test_exception_returns_empty(self, mock_ticker_cls):
        """yfinance 抛异常时应返回空 DataFrame（触发回退）。"""
        mock_ticker = MagicMock()
        mock_ticker.history.side_effect = Exception("429 Too Many Requests")
        mock_ticker_cls.return_value = mock_ticker

        from src.data.data_manager import Stock
        stock = Stock('AAPL', market='us')
        df = stock._fetch_us_stock_yf('AAPL', '20240101', '20240131', 'qfq')
        assert df.empty

    @patch('yfinance.Ticker')
    def test_actions_false_passed(self, mock_ticker_cls):
        """应传 actions=False 避免 Dividends/Stock Splits 列。"""
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = _make_yf_stock_df()
        mock_ticker_cls.return_value = mock_ticker

        from src.data.data_manager import Stock
        stock = Stock('AAPL', market='us')
        stock._fetch_us_stock_yf('AAPL', '20240101', '20240131', 'qfq')

        _, kwargs = mock_ticker.history.call_args
        assert kwargs['actions'] is False


# ---------------------------------------------------------------------------
# yfinance 指数数据获取
# ---------------------------------------------------------------------------
class TestYFinanceIndexData:
    """yfinance 美股指数数据获取测试。"""

    @patch('yfinance.Ticker')
    def test_index_symbol_mapping(self, mock_ticker_cls):
        """SP500 应映射到 ^GSPC。"""
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = _make_yf_index_df()
        mock_ticker_cls.return_value = mock_ticker

        from src.data.data_manager import _fetch_us_index_yf
        _fetch_us_index_yf('SP500', '20240101', '20240131')

        mock_ticker_cls.assert_called_with('^GSPC')

    @patch('yfinance.Ticker')
    def test_index_columns_lowercase(self, mock_ticker_cls):
        """指数数据列名应转为小写。"""
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = _make_yf_index_df()
        mock_ticker_cls.return_value = mock_ticker

        from src.data.data_manager import _fetch_us_index_yf
        df = _fetch_us_index_yf('SP500', '20240101', '20240131')

        for col in ('date', 'open', 'high', 'low', 'close', 'volume'):
            assert col in df.columns, f"缺少小写列: {col}"

    @patch('yfinance.Ticker')
    def test_index_timezone_stripped(self, mock_ticker_cls):
        """指数 Date 应去除时区。"""
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = _make_yf_index_df()
        mock_ticker_cls.return_value = mock_ticker

        from src.data.data_manager import _fetch_us_index_yf
        df = _fetch_us_index_yf('SP500', '20240101', '20240131')

        assert df['date'].dt.tz is None

    @patch('yfinance.Ticker')
    def test_index_end_date_plus_one(self, mock_ticker_cls):
        """指数 end 参数也需 +1 天。"""
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = _make_yf_index_df()
        mock_ticker_cls.return_value = mock_ticker

        from src.data.data_manager import _fetch_us_index_yf
        _fetch_us_index_yf('SP500', '20240101', '20240131')

        _, kwargs = mock_ticker.history.call_args
        assert kwargs['end'] == '2024-02-01'


# ---------------------------------------------------------------------------
# 回退逻辑（yfinance → akshare）
# ---------------------------------------------------------------------------
class TestFallbackLogic:
    """yfinance → akshare 回退逻辑测试。"""

    @patch('src.data.data_manager._fetch_us_index_yf')
    @patch('akshare.index_us_stock_sina')
    def test_index_fallback_on_empty(self, mock_ak, mock_yf):
        """yfinance 返回空时应回退到 akshare 新浪源。"""
        mock_yf.return_value = pd.DataFrame()
        mock_ak.return_value = pd.DataFrame({
            'date': ['2024-01-02', '2024-01-03'],
            'open': [4000, 4010], 'high': [4020, 4030],
            'low': [3990, 4000], 'close': [4010, 4020],
            'volume': [1000000, 1100000],
        })

        from src.data.data_manager import get_us_index_data
        df = get_us_index_data('SP500', '20240101', '20240131')

        assert mock_yf.called
        assert mock_ak.called, "yfinance 空时应回退到 akshare"
        assert '时间' in df.columns
        assert '收盘' in df.columns
        assert len(df) == 2

    @patch('src.data.data_manager._fetch_us_index_yf')
    @patch('akshare.index_us_stock_sina')
    def test_index_no_fallback_on_success(self, mock_ak, mock_yf):
        """yfinance 成功时不应调用 akshare。"""
        mock_yf.return_value = pd.DataFrame({
            'date': pd.to_datetime(['2024-01-02', '2024-01-03']),
            'open': [4000, 4010], 'high': [4020, 4030],
            'low': [3990, 4000], 'close': [4010, 4020],
            'volume': [1000000, 1100000],
        })

        from src.data.data_manager import get_us_index_data
        df = get_us_index_data('SP500', '20240101', '20240131')

        assert mock_yf.called
        assert not mock_ak.called, "yfinance 成功时不应回退"
        assert '时间' in df.columns
        assert '收盘' in df.columns

    @patch('src.data.data_manager._fetch_us_index_yf')
    @patch('akshare.index_us_stock_sina')
    def test_index_fallback_on_exception(self, mock_ak, mock_yf):
        """yfinance 异常时应回退到 akshare。"""
        mock_yf.side_effect = Exception("network error")
        mock_ak.return_value = pd.DataFrame({
            'date': ['2024-01-02'],
            'open': [4000], 'high': [4020],
            'low': [3990], 'close': [4010],
            'volume': [1000000],
        })

        from src.data.data_manager import get_us_index_data
        df = get_us_index_data('SP500', '20240101', '20240131')

        assert mock_ak.called, "yfinance 异常时应回退"
        assert len(df) == 1
        assert '时间' in df.columns

    @patch('src.data.data_manager._fetch_us_index_yf')
    @patch('akshare.index_us_stock_sina')
    def test_index_fallback_date_filter(self, mock_ak, mock_yf):
        """回退 akshare 时应做本地日期过滤。"""
        mock_yf.return_value = pd.DataFrame()
        # akshare 返回超范围数据
        mock_ak.return_value = pd.DataFrame({
            'date': ['2023-12-25', '2024-01-02', '2024-01-03', '2024-02-15'],
            'open': [4000, 4010, 4020, 4030],
            'high': [4020, 4030, 4040, 4050],
            'low': [3990, 4000, 4010, 4020],
            'close': [4010, 4020, 4030, 4040],
            'volume': [1000000, 1100000, 1200000, 1300000],
        })

        from src.data.data_manager import get_us_index_data
        df = get_us_index_data('SP500', '20240101', '20240131')

        assert len(df) == 2, "应只保留 2024-01-02 和 2024-01-03"
        dates = pd.to_datetime(df['时间'])
        assert dates.min() >= pd.to_datetime('20240101')
        assert dates.max() <= pd.to_datetime('20240131')


# ---------------------------------------------------------------------------
# US_INDEX_YF_SYMBOLS 映射
# ---------------------------------------------------------------------------
class TestUSIndexYFSymbols:
    """yfinance 美股指数代码映射测试。"""

    def test_all_expected_keys(self):
        from src.data.data_manager import US_INDEX_YF_SYMBOLS
        assert US_INDEX_YF_SYMBOLS['SP500'] == '^GSPC'
        assert US_INDEX_YF_SYMBOLS['NASDAQ'] == '^IXIC'
        assert US_INDEX_YF_SYMBOLS['DOWJONES'] == '^DJI'
        assert US_INDEX_YF_SYMBOLS['NASDAQ100'] == '^NDX'

    def test_keys_match_akshare_symbols(self):
        """yfinance 映射键应与 akshare 映射键一致（回退时键可互换）。"""
        from src.data.data_manager import US_INDEX_SYMBOLS, US_INDEX_YF_SYMBOLS
        assert set(US_INDEX_YF_SYMBOLS.keys()) == set(US_INDEX_SYMBOLS.keys())

    def test_exported_from_data_package(self):
        """US_INDEX_YF_SYMBOLS 应从 src.data 包导出。"""
        from src.data import US_INDEX_YF_SYMBOLS
        assert 'SP500' in US_INDEX_YF_SYMBOLS


# ---------------------------------------------------------------------------
# 真实 yfinance 网络测试（网络不可用时 skip）
# ---------------------------------------------------------------------------
class TestRealYFinance:
    """真实 yfinance 网络拉取测试。网络不可用或被限流时自动 skip。"""

    def test_real_aapl_daily(self):
        """真实拉取 AAPL 日线数据，验证列名和数据量。"""
        from src.data.data_manager import Stock
        stock = Stock('AAPL', market='us')
        df = stock._fetch_us_stock_yf('AAPL', '20240101', '20240131', 'qfq')

        if df.empty:
            pytest.skip("yfinance 网络不可用或被限流")

        assert 'date' in df.columns
        assert 'close' in df.columns
        assert len(df) > 15, "2024年1月应有超过15个交易日"

    def test_real_sp500_index(self):
        """真实拉取标普500指数数据。"""
        from src.data.data_manager import _fetch_us_index_yf
        df = _fetch_us_index_yf('SP500', '20240101', '20240131')

        if df.empty:
            pytest.skip("yfinance 网络不可用或被限流")

        assert 'date' in df.columns
        assert 'close' in df.columns
        assert len(df) > 15

    def test_real_end_to_end_us_index_data(self):
        """端到端测试 get_us_index_data 返回中文列名。"""
        from src.data.data_manager import get_us_index_data
        df = get_us_index_data('SP500', '20240101', '20240131')

        if df.empty:
            pytest.skip("网络不可用")

        assert '时间' in df.columns
        assert '收盘' in df.columns
        assert '开盘' in df.columns
        assert '最高' in df.columns
        assert '最低' in df.columns
        assert '成交量' in df.columns


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
