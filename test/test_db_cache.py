# coding=utf-8
"""本地数据缓存层测试（PostgreSQL + Redis）。

不依赖真实 Docker 服务：通过 patch src.data.db._get_pg / _get_redis 注入 mock 连接，
验证：
- get_cached_range 的 Redis→PG 优先级
- save_daily 的 upsert + Redis 回填
- parquet 序列化 round-trip 与中文列名契约
- 降级短路（QDT_DB_CACHE_ENABLED / QDT_REDIS_CACHE_ENABLED=false 时所有函数 no-op）
- Stock.get_stock_data 命中 DB 时不触网络层

运行：pytest test/test_db_cache.py -v
（需在项目 conda 环境 qdt 中，依赖 pandas/pyarrow；psycopg/redis 可不装 —— 用 mock）
"""
import os
import sys
from io import BytesIO
from unittest.mock import patch, MagicMock

import pandas as pd
import pytest

# 确保项目根在 sys.path（从 test/ 目录直接 pytest 时也生效）
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)


def _sample_zh_df(n=3):
    """中文列名契约的样例 DataFrame（与 data_manager 输出一致）。"""
    return pd.DataFrame({
        '时间': ['2024-01-02', '2024-01-03', '2024-01-04'][:n],
        '开盘': [10.0, 11.0, 12.0][:n],
        '最高': [10.5, 11.5, 12.5][:n],
        '最低': [9.8, 10.8, 11.8][:n],
        '收盘': [10.2, 11.2, 12.2][:n],
        '成交量': [100000.0, 110000.0, 120000.0][:n],
        '成交额': [1e6, 1.1e6, 1.2e6][:n],
    })


# ---------------------------------------------------------------------------
# 降级短路：开关关闭时 no-op
# ---------------------------------------------------------------------------
class TestDisabledShortCircuit:
    """QDT_DB_CACHE_ENABLED / QDT_REDIS_CACHE_ENABLED=false 时应静默 no-op。"""

    def test_get_returns_none_when_db_disabled(self):
        with patch('src.data.db.DB_CACHE_ENABLED', False), \
             patch('src.data.db.REDIS_CACHE_ENABLED', False):
            from src.data.db import get_cached_range
            assert get_cached_range('600938', 'zh_a', 'hfq', '20240101', '20240131') is None

    def test_save_noop_when_all_disabled(self):
        with patch('src.data.db.DB_CACHE_ENABLED', False), \
             patch('src.data.db.REDIS_CACHE_ENABLED', False):
            from src.data.db import save_daily
            # 不应抛异常
            save_daily(_sample_zh_df(), '600938', 'zh_a', 'hfq')

    def test_healthcheck_all_disabled(self):
        with patch('src.data.db.DB_CACHE_ENABLED', False), \
             patch('src.data.db.REDIS_CACHE_ENABLED', False):
            from src.data.db import healthcheck
            assert healthcheck() == {'postgres': False, 'redis': False}


# ---------------------------------------------------------------------------
# get_cached_range：Redis 优先于 PG
# ---------------------------------------------------------------------------
class TestGetCachedRangePriority:
    """Redis 命中时不查 PG；Redis 空/异常时回退 PG。"""

    def test_redis_hit_skips_pg(self):
        """Redis 有数据时应直接返回，不调 PG。"""
        from src.data import db
        cached = _sample_zh_df()
        mock_r = MagicMock()
        mock_r.get.return_value = db._df_to_bytes(cached)
        mock_pg = MagicMock()
        with patch.object(db, '_get_redis', return_value=mock_r), \
             patch.object(db, '_get_pg', return_value=mock_pg):
            df = db.get_cached_range('600938', 'zh_a', 'hfq', '20240101', '20240131')
        assert df is not None and not df.empty
        # Redis 命中，PG 不应被查询
        assert not mock_pg.cursor.called, "Redis 命中时不应查 PG"

    def test_redis_miss_falls_to_pg(self):
        """Redis miss 时回退到 PG，PG 有数据则返回。"""
        from src.data import db
        mock_r = MagicMock()
        mock_r.get.return_value = None
        # mock PG：cursor() 返回上下文，fetchall 返回 PG 行（元组，列顺序同 _PG_COLUMNS）
        mock_cur = MagicMock()
        mock_cur.fetchall.return_value = [
            ('2024-01-02', 10.0, 10.5, 9.8, 10.2, 100000.0, 1e6, None, None),
            ('2024-01-03', 11.0, 11.5, 10.8, 11.2, 110000.0, 1.1e6, None, None),
        ]
        mock_pg = MagicMock()
        mock_pg.cursor.return_value.__enter__.return_value = mock_pg.cursor.return_value
        mock_pg.cursor.return_value.fetchall.return_value = mock_cur.fetchall.return_value
        with patch.object(db, '_get_redis', return_value=mock_r), \
             patch.object(db, '_get_pg', return_value=mock_pg):
            df = db.get_cached_range('600938', 'zh_a', 'hfq', '20240101', '20240131')
        assert df is not None and not df.empty
        assert '时间' in df.columns, "PG 数据应转为中文列名"
        assert len(df) == 2

    def test_all_empty_returns_none(self):
        """Redis + PG 都空时返回 None。"""
        from src.data import db
        mock_r = MagicMock()
        mock_r.get.return_value = None
        mock_cur = MagicMock()
        mock_cur.fetchall.return_value = []
        mock_pg = MagicMock()
        mock_pg.cursor.return_value.__enter__.return_value = mock_pg.cursor.return_value
        mock_pg.cursor.return_value.fetchall.return_value = []
        with patch.object(db, '_get_redis', return_value=mock_r), \
             patch.object(db, '_get_pg', return_value=mock_pg):
            assert db.get_cached_range('600938', 'zh_a', 'hfq', '20240101', '20240131') is None

    def test_pg_exception_returns_none(self):
        """PG 异常时静默返回 None（不抛到调用方）。"""
        from src.data import db
        mock_r = MagicMock()
        mock_r.get.return_value = None
        mock_pg = MagicMock()
        mock_pg.cursor.side_effect = Exception("connection lost")
        with patch.object(db, '_get_redis', return_value=mock_r), \
             patch.object(db, '_get_pg', return_value=mock_pg):
            assert db.get_cached_range('600938', 'zh_a', 'hfq', '20240101', '20240131') is None


# ---------------------------------------------------------------------------
# save_daily：upsert + Redis 回填
# ---------------------------------------------------------------------------
class TestSaveDaily:
    def test_writes_pg_and_redis(self):
        """save_daily 应同时 upsert PG 和回填 Redis。"""
        from src.data import db
        mock_cur = MagicMock()
        mock_pg = MagicMock()
        mock_pg.cursor.return_value.__enter__.return_value = mock_pg.cursor.return_value
        mock_pg.cursor.return_value.executemany = mock_cur.executemany
        mock_r = MagicMock()
        with patch.object(db, '_get_pg', return_value=mock_pg), \
             patch.object(db, '_get_redis', return_value=mock_r):
            db.save_daily(_sample_zh_df(), '600938', 'zh_a', 'hfq')
        # PG upsert 被调用
        assert mock_pg.cursor.return_value.executemany.called, "应 upsert 到 PG"
        # Redis 被回填（setex）
        assert mock_r.setex.called, "应回填 Redis"

    def test_empty_df_noop(self):
        """空 DataFrame 不应触发任何写。"""
        from src.data import db
        mock_pg, mock_r = MagicMock(), MagicMock()
        with patch.object(db, '_get_pg', return_value=mock_pg), \
             patch.object(db, '_get_redis', return_value=mock_r):
            db.save_daily(pd.DataFrame(), '600938', 'zh_a', 'hfq')
        assert not mock_pg.cursor.called
        assert not mock_r.setex.called

    def test_pg_write_failure_silent(self):
        """PG 写失败不应抛异常（应继续写 Redis，最终静默）。"""
        from src.data import db
        mock_pg = MagicMock()
        mock_pg.cursor.return_value.__enter__.return_value = mock_pg.cursor.return_value
        mock_pg.cursor.return_value.executemany.side_effect = Exception("disk full")
        mock_r = MagicMock()
        with patch.object(db, '_get_pg', return_value=mock_pg), \
             patch.object(db, '_get_redis', return_value=mock_r):
            db.save_daily(_sample_zh_df(), '600938', 'zh_a', 'hfq')  # 不抛

    def test_english_columns_normalized(self):
        """英文小写列名也应被接受并转中文写入。"""
        from src.data import db
        eng_df = pd.DataFrame({
            'date': ['2024-01-02'],
            'open': [10.0], 'high': [10.5], 'low': [9.8], 'close': [10.2],
            'volume': [100000.0], 'amount': [1e6],
        })
        mock_pg = MagicMock()
        mock_pg.cursor.return_value.__enter__.return_value = mock_pg.cursor.return_value
        mock_r = MagicMock()
        with patch.object(db, '_get_pg', return_value=mock_pg), \
             patch.object(db, '_get_redis', return_value=mock_r):
            db.save_daily(eng_df, 'AAPL', 'us', 'qfq')
        args, _ = mock_pg.cursor.return_value.executemany.call_args
        sql, rows = args
        assert len(rows) == 1
        assert rows[0][0] == 'AAPL'  # code


# ---------------------------------------------------------------------------
# parquet 序列化 round-trip
# ---------------------------------------------------------------------------
class TestSerialization:
    def test_roundtrip_preserves_data(self):
        from src.data.db import _df_to_bytes, _df_from_bytes
        df = _sample_zh_df()
        out = _df_from_bytes(_df_to_bytes(df))
        pd.testing.assert_frame_equal(
            out.reset_index(drop=True), df.reset_index(drop=True),
            check_dtype=False,
        )


# ---------------------------------------------------------------------------
# get_latest_date
# ---------------------------------------------------------------------------
class TestGetLatestDate:
    def test_returns_max_date(self):
        from src.data import db
        mock_cur = MagicMock()
        mock_cur.fetchone.return_value = ('2024-01-04',)
        mock_pg = MagicMock()
        mock_pg.cursor.return_value.__enter__.return_value = mock_pg.cursor.return_value
        mock_pg.cursor.return_value.fetchone.return_value = ('2024-01-04',)
        with patch.object(db, '_get_pg', return_value=mock_pg):
            assert db.get_latest_date('600938', 'zh_a', 'hfq') == '2024-01-04'

    def test_returns_none_when_no_data(self):
        from src.data import db
        mock_pg = MagicMock()
        mock_pg.cursor.return_value.__enter__.return_value = mock_pg.cursor.return_value
        mock_pg.cursor.return_value.fetchone.return_value = (None,)
        with patch.object(db, '_get_pg', return_value=mock_pg):
            assert db.get_latest_date('600938', 'zh_a', 'hfq') is None


# ---------------------------------------------------------------------------
# 集成层：Stock.get_stock_data 命中 DB 时不触网络
# ---------------------------------------------------------------------------
class TestStockIntegrationDBHit:
    """get_stock_data 命中 DB 缓存时应跳过网络回退链。"""

    def test_db_hit_skips_network(self, tmp_path):
        """DB 命中时不应调用任何网络数据源。"""
        # 用一个不存在的本地 CSV 路径，强制走到 DB 检查分支
        cached = _sample_zh_df()
        from src.data import db as _db
        from src.data.data_manager import Stock

        stock = Stock('600938', market='zh_a')
        # 确保 stock_data_dir 指向空目录（无 CSV 命中）
        stock.stock_data_dir = str(tmp_path)

        # data_manager 内部 `from src.data import db as _db` → patch db 模块的函数
        with patch.object(_db, 'get_cached_range', return_value=cached) as mock_get, \
             patch('akshare.stock_zh_a_daily') as mock_sina, \
             patch.object(Stock, '_fetch_ashare_tushare') as mock_ts, \
             patch.object(Stock, '_fetch_ashare_hist_em') as mock_em, \
             patch.object(Stock, '_fetch_ashare_baostock') as mock_bs:
            df, _ = stock.get_stock_data('20240101', '20240131', adjust='hfq', type='daily')

        assert mock_get.called, "应查询 DB 缓存"
        assert not mock_sina.called, "DB 命中时不应触网络"
        assert not mock_ts.called
        assert not mock_em.called
        assert not mock_bs.called
        assert not df.empty
        assert '时间' in df.columns


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
