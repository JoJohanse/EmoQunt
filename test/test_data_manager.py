# coding=utf-8
"""数据层模块 (src/data/data_manager.py) 单元测试。

注意：Stock 美股初始化、US_INDEX_SYMBOLS 映射、以及真实情绪快照的集成测试
已在 test/test_backtest.py 覆盖。本文件覆盖：
- Stock._filter_us_daily_by_date 本地日期过滤
- Stock 的 A 股整型/前缀处理细节
- load_sentiment_snapshots 用合成快照验证归一化逻辑（不依赖真实数据）
- build_stock_sentiment_series 空面板回退

运行：pytest test/test_data_manager.py -v
"""
import json
import os
import sys

import pandas as pd
import pytest

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)


@pytest.fixture(autouse=True)
def _disable_db_cache(monkeypatch):
    """禁用 DB/Redis 缓存层（与缓存状态解耦，避免 Docker 起着时影响断言）。"""
    import src.data.db as _db
    monkeypatch.setattr(_db, 'DB_CACHE_ENABLED', False)
    monkeypatch.setattr(_db, 'REDIS_CACHE_ENABLED', False)

from src.data.data_manager import (
    Stock,
    load_sentiment_snapshots,
    build_stock_sentiment_series,
    US_INDEX_SYMBOLS,
)


class TestFilterUSDailyByDate:
    """美股日线本地日期过滤测试。"""

    @pytest.fixture
    def df(self):
        return pd.DataFrame({
            "date": ["2024-01-01", "2024-02-01", "2024-03-01"],
            "close": [1, 2, 3],
        })

    def test_inclusive_range(self, df):
        out = Stock._filter_us_daily_by_date(df, "20240101", "20240201")
        assert len(out) == 2

    def test_partial_range(self, df):
        # 仅 2024-02-01 落在 [2024-01-15, 2024-02-28] 内
        out = Stock._filter_us_daily_by_date(df, "20240115", "20240228")
        assert len(out) == 1
        assert out.iloc[0]["close"] == 2

    def test_full_range(self, df):
        out = Stock._filter_us_daily_by_date(df, "20240101", "20240301")
        assert len(out) == 3

    def test_none_returns_none(self):
        assert Stock._filter_us_daily_by_date(None, "20240101", "20240201") is None

    def test_empty_df(self):
        out = Stock._filter_us_daily_by_date(pd.DataFrame(), "20240101", "20240201")
        assert out.empty

    def test_missing_date_column_returns_original(self):
        df = pd.DataFrame({"close": [1, 2]})
        out = Stock._filter_us_daily_by_date(df, "20240101", "20240201")
        # 无 date 列时原样返回
        assert out is df or out.equals(df)


class TestStockAShareInit:
    """A 股 Stock 初始化细节测试（补充 test_backtest.py）。"""

    def test_int_code_with_prefix(self):
        # 整型 600000 → "sh600000"
        s = Stock(600000)
        assert s.stock_code == "sh600000"
        assert s.market == "zh_a"

    def test_int_code_zfill(self):
        # 整型 1 → zfill 为 "000001" → "sz000001"
        s = Stock(1)
        assert s.stock_code == "sz000001"

    def test_existing_prefix_preserved(self):
        s = Stock("sh600000")
        assert s.stock_code == "sh600000"
        assert s.get_code_without_prefix() == "600000"

    def test_get_code_without_prefix_sz(self):
        s = Stock("000001")
        assert s.get_code_without_prefix() == "000001"


class TestUSIndexSymbols:
    """美股指数符号映射完整性测试。"""

    def test_all_expected_keys(self):
        for key in ["SP500", "NASDAQ", "DOWJONES", "NASDAQ100"]:
            assert key in US_INDEX_SYMBOLS


class TestLoadSentimentSnapshots:
    """情绪快照面板构建测试（使用合成快照）。"""

    def test_empty_dir_returns_empty(self, tmp_path):
        panel = load_sentiment_snapshots(str(tmp_path))
        assert panel.empty

    def test_panel_normalization_and_fill(self, tmp_path):
        (tmp_path / "20240101.json").write_text(json.dumps({
            "date": "2024-01-01",
            "all_sectors": [
                {"name": "石油行业", "sentiment": 60, "stocks": []},
                {"name": "科技行业", "sentiment": 40, "stocks": []},
            ],
        }), encoding="utf-8")
        # 第二个快照缺少"科技行业"，应填中性 0
        (tmp_path / "20240102.json").write_text(json.dumps({
            "all_sectors": [
                {"name": "石油行业", "sentiment": 100, "stocks": []},
            ],
        }), encoding="utf-8")

        panel = load_sentiment_snapshots(str(tmp_path))

        assert panel.index.name == "日期"
        assert panel.shape[0] == 2
        # 0-100 → (s-50)/50：60→0.2, 40→-0.2, 100→1.0
        assert panel.loc[pd.Timestamp("2024-01-01"), "石油行业"] == pytest.approx(0.2)
        assert panel.loc[pd.Timestamp("2024-01-01"), "科技行业"] == pytest.approx(-0.2)
        assert panel.loc[pd.Timestamp("2024-01-02"), "石油行业"] == pytest.approx(1.0)
        # 缺失行业填中性 0
        assert panel.loc[pd.Timestamp("2024-01-02"), "科技行业"] == 0.0
        # 范围 [-1, 1]
        assert panel.values.min() >= -1.0
        assert panel.values.max() <= 1.0

    def test_invalid_sentiment_treated_as_neutral(self, tmp_path):
        (tmp_path / "20240101.json").write_text(json.dumps({
            "all_sectors": [
                {"name": "测试行业", "sentiment": "不可解析", "stocks": []},
            ],
        }), encoding="utf-8")
        panel = load_sentiment_snapshots(str(tmp_path))
        assert panel.loc[pd.Timestamp("2024-01-01"), "测试行业"] == 0.0

    def test_out_of_range_clipped(self, tmp_path):
        (tmp_path / "20240101.json").write_text(json.dumps({
            "all_sectors": [
                {"name": "高情绪", "sentiment": 200, "stocks": []},  # 越界
                {"name": "低情绪", "sentiment": -50, "stocks": []},
            ],
        }), encoding="utf-8")
        panel = load_sentiment_snapshots(str(tmp_path))
        assert panel.iloc[0]["高情绪"] == 1.0   # 裁剪到上界
        assert panel.iloc[0]["低情绪"] == -1.0  # 裁剪到下界


class TestBuildStockSentimentSeries:
    """个股情绪序列构建测试。"""

    def test_empty_panel_returns_empty(self):
        s, sector = build_stock_sentiment_series(pd.DataFrame(), "000001")
        assert s.empty
        assert sector is None

    def test_none_panel_returns_empty(self):
        s, sector = build_stock_sentiment_series(None, "000001")
        assert s.empty
        assert sector is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
