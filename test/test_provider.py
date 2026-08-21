# coding=utf-8
"""KlineProvider 深模块测试：DB命中→网络回退链→列名契约→DB回填 单点收口。

风格参考 test/test_db_cache.py（手动 sys.path 插入项目根）。

覆盖：
- 缓存命中不调 fetcher
- 未命中走 fetcher 并回填
- fetcher 抛异常返回空
- EN_TO_ZH 重命名生效
"""
import os
import sys
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)


def _sample_en_df(n=2):
    """英文小写列名 DataFrame（含 date/open/...），模拟 fetcher 返回。"""
    return pd.DataFrame({
        'date': ['2024-01-02', '2024-01-03'][:n],
        'open': [10.0, 11.0][:n],
        'high': [10.5, 11.5][:n],
        'low': [9.8, 10.8][:n],
        'close': [10.2, 11.2][:n],
        'volume': [100000.0, 110000.0][:n],
        'amount': [1e6, 1.1e6][:n],
    })


def _sample_zh_df(n=2):
    """中文列名 DataFrame，模拟 DB 缓存命中返回。"""
    return pd.DataFrame({
        '时间': ['2024-01-02', '2024-01-03'][:n],
        '开盘': [10.0, 11.0][:n],
        '最高': [10.5, 11.5][:n],
        '最低': [9.8, 10.8][:n],
        '收盘': [10.2, 11.2][:n],
        '成交量': [100000.0, 110000.0][:n],
        '成交额': [1e6, 1.1e6][:n],
    })


class TestProviderCacheHit:
    """缓存命中不调 fetcher。"""

    def test_cache_hit_skips_fetcher(self):
        from src.data.provider import KlineProvider
        cached = _sample_zh_df()
        fetcher = MagicMock(return_value=_sample_en_df())
        with patch('src.data.db.get_cached_range', return_value=cached) as mock_get, \
             patch('src.data.db.save_daily') as mock_save:
            provider = KlineProvider(fetcher=fetcher)
            df, fname = provider.fetch_daily('600938', 'zh_a', 'hfq', '20240101', '20240131')
        assert mock_get.called
        assert not fetcher.called, "缓存命中时不应调 fetcher"
        assert not mock_save.called, "缓存命中时不应回填"
        pd.testing.assert_frame_equal(df.reset_index(drop=True), cached.reset_index(drop=True))
        assert fname == "600938_hfq_daily_20240101_20240131.csv"


class TestProviderMissFetchAndBackfill:
    """未命中走 fetcher 并回填。"""

    def test_miss_calls_fetcher_and_save(self):
        from src.data.provider import KlineProvider
        en_df = _sample_en_df()
        fetcher = MagicMock(return_value=en_df)
        with patch('src.data.db.get_cached_range', return_value=None), \
             patch('src.data.db.save_daily') as mock_save:
            provider = KlineProvider(fetcher=fetcher)
            df, fname = provider.fetch_daily('600938', 'zh_a', 'hfq', '20240101', '20240131')
        assert fetcher.called, "未命中应调 fetcher"
        assert mock_save.called, "成功后应回填 DB"
        # 验证 fetcher 收到映射后的 adjust_str（hfq→hfq）
        args = fetcher.call_args[0]
        assert args[0] == '20240101' and args[1] == '20240131'
        # 第三参为 ''/qfq/hfq 之一
        assert args[2] == 'hfq'
        assert '时间' in df.columns and '开盘' in df.columns
        assert fname == "600938_hfq_daily_20240101_20240131.csv"

    def test_db_params_passed_through(self):
        """get_cached_range / save_daily 应收到正确的 code/market/adjust。"""
        from src.data.provider import KlineProvider
        fetcher = MagicMock(return_value=_sample_en_df())
        with patch('src.data.db.get_cached_range', return_value=None) as mock_get, \
             patch('src.data.db.save_daily') as mock_save:
            provider = KlineProvider(fetcher=fetcher)
            provider.fetch_daily('600938', 'zh_a', 'hfq', '20240101', '20240131')
        get_args = mock_get.call_args[0]
        assert get_args[0] == '600938' and get_args[1] == 'zh_a' and get_args[2] == 'hfq'
        save_args = mock_save.call_args[0]
        assert save_args[1] == '600938' and save_args[2] == 'zh_a' and save_args[3] == 'hfq'

    def test_index_flag_passthrough(self):
        """is_index 透传验证（kwargs 形态断言）。"""
        from src.data.provider import KlineProvider
        en_df = _sample_en_df()
        with patch('src.data.db.get_cached_range', return_value=None) as mock_get, \
             patch('src.data.db.save_daily') as mock_save:
            fetcher2 = MagicMock(return_value=en_df)
            provider2 = KlineProvider(fetcher=fetcher2)
            provider2.fetch_daily('000300', 'zh_a', 'nfq', '20240101', '20240131', is_index=True)
        assert mock_get.call_args.kwargs.get('is_index') is True
        assert mock_save.call_args.kwargs.get('is_index') is True

    def test_db_exception_fallback_to_fetcher(self):
        """DB 查询抛异常应静默降级并走 fetcher。"""
        from src.data.provider import KlineProvider
        fetcher = MagicMock(return_value=_sample_en_df())
        with patch('src.data.db.get_cached_range', side_effect=Exception("db down")), \
             patch('src.data.db.save_daily') as mock_save:
            provider = KlineProvider(fetcher=fetcher)
            df, fname = provider.fetch_daily('600938', 'zh_a', 'hfq', '20240101', '20240131')
        assert fetcher.called
        assert not df.empty
        assert mock_save.called


class TestProviderFetcherException:
    """fetcher 抛异常返回空。"""

    def test_fetcher_raises_returns_empty(self):
        from src.data.provider import KlineProvider

        def bad_fetcher(s, e, a):
            raise RuntimeError("network down")

        with patch('src.data.db.get_cached_range', return_value=None), \
             patch('src.data.db.save_daily') as mock_save:
            provider = KlineProvider(fetcher=bad_fetcher)
            df, fname = provider.fetch_daily('600938', 'zh_a', 'hfq', '20240101', '20240131')
        assert df.empty
        assert fname == ''
        assert not mock_save.called

    def test_fetcher_returns_empty_no_backfill(self):
        from src.data.provider import KlineProvider
        fetcher = MagicMock(return_value=pd.DataFrame())
        with patch('src.data.db.get_cached_range', return_value=None), \
             patch('src.data.db.save_daily') as mock_save:
            provider = KlineProvider(fetcher=fetcher)
            df, fname = provider.fetch_daily('600938', 'zh_a', 'hfq', '20240101', '20240131')
        assert df.empty and fname == ''
        assert not mock_save.called

    def test_fetcher_returns_none_no_backfill(self):
        from src.data.provider import KlineProvider
        fetcher = MagicMock(return_value=None)
        with patch('src.data.db.get_cached_range', return_value=None), \
             patch('src.data.db.save_daily') as mock_save:
            provider = KlineProvider(fetcher=fetcher)
            df, fname = provider.fetch_daily('600938', 'zh_a', 'hfq', '20240101', '20240131')
        assert df.empty and fname == ''
        assert not mock_save.called


class TestProviderRename:
    """EN_TO_ZH 重命名生效。"""

    def test_en_to_zh_rename(self):
        from src.data.provider import KlineProvider
        en_df = _sample_en_df()
        fetcher = MagicMock(return_value=en_df)
        with patch('src.data.db.get_cached_range', return_value=None), \
             patch('src.data.db.save_daily'):
            provider = KlineProvider(fetcher=fetcher)
            df, _ = provider.fetch_daily('600938', 'zh_a', 'hfq', '20240101', '20240131')
        assert '时间' in df.columns
        assert '开盘' in df.columns
        assert 'date' not in df.columns
        assert 'open' not in df.columns

    def test_index_column_cleaned(self):
        from src.data.provider import KlineProvider
        en_df = _sample_en_df()
        en_df['index'] = [0, 1]
        fetcher = MagicMock(return_value=en_df)
        with patch('src.data.db.get_cached_range', return_value=None), \
             patch('src.data.db.save_daily'):
            provider = KlineProvider(fetcher=fetcher)
            df, _ = provider.fetch_daily('600938', 'zh_a', 'hfq', '20240101', '20240131')
        assert 'index' not in df.columns

    def test_nfq_adjust_mapped_to_empty(self):
        from src.data.provider import KlineProvider
        fetcher = MagicMock(return_value=_sample_en_df())
        with patch('src.data.db.get_cached_range', return_value=None), \
             patch('src.data.db.save_daily'):
            provider = KlineProvider(fetcher=fetcher)
            provider.fetch_daily('600938', 'zh_a', 'nfq', '20240101', '20240131')
        # nfq → '' 映射
        assert fetcher.call_args[0][2] == ''

    def test_save_daily_exception_silent(self):
        """save_daily 抛异常应静默，不影响返回。"""
        from src.data.provider import KlineProvider
        fetcher = MagicMock(return_value=_sample_en_df())
        with patch('src.data.db.get_cached_range', return_value=None), \
             patch('src.data.db.save_daily', side_effect=Exception("pg down")):
            provider = KlineProvider(fetcher=fetcher)
            df, fname = provider.fetch_daily('600938', 'zh_a', 'hfq', '20240101', '20240131')
        assert not df.empty and fname != ''

    def test_per_call_fetcher_overrides_constructor(self):
        from src.data.provider import KlineProvider
        ctor_fetcher = MagicMock(return_value=_sample_en_df())
        call_fetcher = MagicMock(return_value=_sample_en_df())
        with patch('src.data.db.get_cached_range', return_value=None), \
             patch('src.data.db.save_daily'):
            provider = KlineProvider(fetcher=ctor_fetcher)
            provider.fetch_daily('600938', 'zh_a', 'hfq', '20240101', '20240131', fetcher=call_fetcher)
        assert not ctor_fetcher.called
        assert call_fetcher.called


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
