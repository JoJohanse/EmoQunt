# coding=utf-8
"""daily_recommend 并发拉取测试。

覆盖：
- generate_daily_recommend 用 ThreadPoolExecutor 并发评分（mock 网络层）
- 结果保序（ex.map 按提交顺序）
- 个别股票评分失败被隔离，不影响其余
- baostock 回退在并发下不崩（_BaoStockSession 锁串行化）
- STOCK_DATA_CACHE 多线程写入安全（加锁）

运行：pytest test/test_daily_recommend_parallel.py -v
"""
import os
import sys
import threading
import time
from unittest.mock import patch, MagicMock

import pandas as pd
import pytest

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)


def _sample_ashare_df(n=5):
    """daily_recommend.get_stock_data 期望的中文列名 + DatetimeIndex 形态。"""
    idx = pd.date_range('2024-01-02', periods=n, freq='B')
    return pd.DataFrame({
        '开盘': [10.0 + i for i in range(n)],
        '最高': [10.5 + i for i in range(n)],
        '最低': [9.8 + i for i in range(n)],
        '收盘': [10.2 + i for i in range(n)],
        '成交量': [100000 + i * 1000 for i in range(n)],
        '成交额': [1e6 + i * 1e4 for i in range(n)],
    }, index=idx)


# ---------------------------------------------------------------------------
# 并发评分：正确性 + 保序
# ---------------------------------------------------------------------------
class TestParallelScoring:
    @patch('src.factor.daily_recommend.get_top_sectors')
    @patch('src.factor.daily_recommend.get_sector_stocks')
    @patch('src.factor.daily_recommend.calculate_stock_score')
    def test_all_candidates_scored(self, mock_score, mock_sector_stocks, mock_top):
        """所有候选都应被评分，结果数 == 候选数。"""
        from src.factor import daily_recommend as dr

        mock_top.return_value = [('石油行业', 70), ('银行', 65), ('白酒', 60)]
        # 每板块 3 只候选（dict schema 同 load_hs300_stocks: code/name/full_code/industry）
        def _stocks(sector):
            return [{'code': f'{i:06d}', 'name': f'{sector}{i}',
                     'full_code': f'{i:06d}.SH', 'industry': sector} for i in range(3)]
        mock_sector_stocks.side_effect = _stocks

        # 评分函数返回带 score 的 dict，按 i 给不同分（验证排序）
        def _score(code, name, sector, sentiment):
            i = int(name[-1])
            return {'code': code, 'name': name, 'sector': sector,
                    'score': float(i), 'price_score': 0, 'volume_score': 0,
                    'sentiment_score': 0, 'technical_score': 0, 'reason': ''}
        mock_score.side_effect = _score

        result = dr.generate_daily_recommend(n=5)
        assert len(result['recommendations']) == 5
        assert mock_score.call_count == 9  # 3 板块 × 3 只

    @patch('src.factor.daily_recommend.get_top_sectors')
    @patch('src.factor.daily_recommend.get_sector_stocks')
    @patch('src.factor.daily_recommend.calculate_stock_score')
    def test_sorted_by_score_desc(self, mock_score, mock_sector_stocks, mock_top):
        """recommendations 应按 score 降序。"""
        from src.factor import daily_recommend as dr
        mock_top.return_value = [('石油行业', 70)]
        mock_sector_stocks.return_value = [
            {'code': '000001', 'name': 'A', 'full_code': '000001.SH', 'industry': '石油行业'},
            {'code': '000002', 'name': 'B', 'full_code': '000002.SH', 'industry': '石油行业'},
            {'code': '000003', 'name': 'C', 'full_code': '000003.SH', 'industry': '石油行业'},
        ]
        scores = {'A': 30.0, 'B': 90.0, 'C': 60.0}
        mock_score.side_effect = lambda code, name, sec, s: {
            'code': code, 'name': name, 'sector': sec, 'score': scores[name],
            'price_score': 0, 'volume_score': 0, 'sentiment_score': 0,
            'technical_score': 0, 'reason': ''}
        result = dr.generate_daily_recommend(n=3)
        names = [r['name'] for r in result['recommendations']]
        assert names == ['B', 'C', 'A'], "应按 score 降序：B(90)>C(60)>A(30)"


# ---------------------------------------------------------------------------
# 异常隔离：个别股票失败不影响其余
# ---------------------------------------------------------------------------
class TestExceptionIsolation:
    @patch('src.factor.daily_recommend.get_top_sectors')
    @patch('src.factor.daily_recommend.get_sector_stocks')
    @patch('src.factor.daily_recommend.calculate_stock_score')
    def test_one_failure_does_not_crash_others(self, mock_score, mock_sector_stocks, mock_top):
        """一只股票评分抛异常应被捕获（返回 None 并过滤），其余正常返回。"""
        from src.factor import daily_recommend as dr
        mock_top.return_value = [('石油行业', 70)]
        mock_sector_stocks.return_value = [
            {'code': '000001', 'name': 'A', 'full_code': '000001.SH', 'industry': '石油行业'},
            {'code': '000002', 'name': 'B', 'full_code': '000002.SH', 'industry': '石油行业'},
            {'code': '000003', 'name': 'C', 'full_code': '000003.SH', 'industry': '石油行业'},
        ]

        def _score(code, name, sec, s):
            if name == 'B':
                raise RuntimeError("网络超时")
            return {'code': code, 'name': name, 'sector': sec, 'score': 50.0,
                    'price_score': 0, 'volume_score': 0, 'sentiment_score': 0,
                    'technical_score': 0, 'reason': ''}
        mock_score.side_effect = _score

        # 不应抛异常
        result = dr.generate_daily_recommend(n=5)
        # A、C 正常返回，B 被隔离
        names = {r['name'] for r in result['recommendations']}
        assert 'B' not in names
        assert 'A' in names and 'C' in names


# ---------------------------------------------------------------------------
# baostock 并发不崩（_BaoStockSession 锁串行化）
# ---------------------------------------------------------------------------
class TestBaostockThreadSafety:
    def test_concurrent_query_no_crash(self):
        """多线程并发调用 _bs_session.query（持锁），应无异常且各自返回独立结果。

        直接单元测试 query 方法的并发安全，不经 get_stock_data（避免引入 DB 缓存层）。
        mock baostock 底层 login + query_history_k_data_plus，让 _ensure_login 不触真实网络。
        """
        from src.data.data_manager import _bs_session
        import baostock as bs

        # 注意：unittest.mock.patch 修改的是共享模块属性，多线程各自进入/退出
        # 补丁会互相覆盖 → 必须在起线程池前一次性 patch 整个并发区段。
        bs_login_result = MagicMock()
        bs_login_result.error_code = '0'

        def _make_rs(*args, **kwargs):
            """构造一个 baostock ResultSet mock。所有线程共享同一个返回工厂。"""
            rs = MagicMock()
            rs.error_code = '0'
            rs.fields = ['date', 'open', 'high', 'low', 'close', 'volume', 'amount']
            row = ['2024-01-02', '10.0', '10.5', '9.8', '10.2', '10000000', '1000000']
            rs.next = MagicMock(side_effect=[True, False])
            rs.get_row_data = MagicMock(return_value=row)
            return rs

        errors = []
        def _query_one(tag):
            try:
                df = _bs_session.query(
                    f'sh.60000{tag}', 'date,close',
                    '2024-01-01', '2024-01-31', adjustflag='2',
                )
                return df
            except Exception as e:
                errors.append((tag, e))
                return None

        # 补丁一次性包裹整个线程池（线程内不再各自 patch）
        with patch.object(bs, 'login', return_value=bs_login_result), \
             patch.object(bs, 'logout'), \
             patch('baostock.query_history_k_data_plus', side_effect=_make_rs), \
             patch('contextlib.redirect_stdout'):
            from concurrent.futures import ThreadPoolExecutor
            tags = list(range(8))
            with ThreadPoolExecutor(max_workers=8) as ex:
                results = list(ex.map(_query_one, tags))

        assert not errors, f"并发 baostock query 出现异常: {errors}"
        # 每个线程都应拿到非空结果
        for r in results:
            assert r is not None and not r.empty


# ---------------------------------------------------------------------------
# STOCK_DATA_CACHE 多线程写入安全
# ---------------------------------------------------------------------------
class TestCacheLockThreadSafety:
    def test_concurrent_writes_no_error(self):
        """多线程并发写 STOCK_DATA_CACHE 不应抛异常（锁保护）。"""
        from src.factor import daily_recommend as dr
        # 清空缓存确保测试干净
        dr.STOCK_DATA_CACHE.clear()

        errors = []
        def _write(i):
            try:
                with dr._STOCK_DATA_CACHE_LOCK:
                    dr.STOCK_DATA_CACHE[f'00000{i}'] = _sample_ashare_df()
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=_write, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert not errors
        assert len(dr.STOCK_DATA_CACHE) == 10


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
