# coding=utf-8
"""SnapshotStore (src/data/sentiment_snapshots.py) 单元测试。

用 tmp_path 合成快照 fixture 覆盖情绪快照解析契约（不依赖真实快照）：
- 日期回退三种情况：无 date 字段走文件名 / date 字段存在 / 仅 timestamp
- 日期回退统一语义：文件名优先于 date 字段（B5 归一决策的固化测试）
- 0-100 → -1..1 归一化（含越界裁剪、不可解析记中性）
- 快照间缺失行业 fillna(0.0)
- 个股情绪序列构建（成分股扫描路径）
- 情绪日历按日聚合 build_daily_summaries

运行：pytest test/test_sentiment_snapshot_store.py -v
"""
import json
import os
import sys

import pandas as pd
import pytest

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from src.data.sentiment_snapshots import (
    build_daily_summaries,
    build_stock_sentiment_series,
    load_sentiment_snapshots,
    normalize_sentiment,
    resolve_snapshot_date,
)


def _write_snapshot(directory, filename, payload):
    """在指定目录写入一个快照 JSON fixture。"""
    (directory / filename).write_text(json.dumps(payload, ensure_ascii=False),
                                      encoding="utf-8")


class TestDateFallback:
    """快照日期回退：文件名 YYYYMMDD → date 字段 → timestamp 字段。"""

    def test_filename_used_when_no_date_field(self, tmp_path):
        # 无 date/timestamp 字段 → 回退文件名 YYYYMMDD
        _write_snapshot(tmp_path, "20240105.json", {
            "all_sectors": [{"name": "石油行业", "sentiment": 60, "stocks": []}],
        })
        panel = load_sentiment_snapshots(str(tmp_path))
        assert list(panel.index) == [pd.Timestamp("2024-01-05")]

    def test_date_field_used_when_filename_not_a_date(self, tmp_path):
        # 文件名不是 8 位日期 → 回退文件内 date 字段
        _write_snapshot(tmp_path, "snapshot_alpha.json", {
            "date": "2024-01-06",
            "all_sectors": [{"name": "石油行业", "sentiment": 60, "stocks": []}],
        })
        panel = load_sentiment_snapshots(str(tmp_path))
        assert list(panel.index) == [pd.Timestamp("2024-01-06")]

    def test_timestamp_used_when_no_date_field(self, tmp_path):
        # 文件名不是日期且无 date 字段 → 回退 timestamp（与原面板行为一致，保留时刻）
        _write_snapshot(tmp_path, "snapshot_beta.json", {
            "timestamp": "2024-01-07 15:30:00",
            "all_sectors": [{"name": "石油行业", "sentiment": 60, "stocks": []}],
        })
        panel = load_sentiment_snapshots(str(tmp_path))
        assert list(panel.index) == [pd.Timestamp("2024-01-07 15:30:00")]

    def test_filename_wins_over_date_field(self, tmp_path):
        # 统一语义（B5 归一）：文件名与 date 字段不一致时，文件名优先。
        # （原日历侧顺序为 date → 文件名，此处固化归一后的行为）
        _write_snapshot(tmp_path, "20240201.json", {
            "date": "2024-12-31",
            "all_sectors": [{"name": "石油行业", "sentiment": 60, "stocks": []}],
        })
        panel = load_sentiment_snapshots(str(tmp_path))
        assert list(panel.index) == [pd.Timestamp("2024-02-01")]

    def test_unresolvable_date_skips_file(self, tmp_path):
        # 三种日期来源均不可解析 → 跳过该文件（不抛异常）
        _write_snapshot(tmp_path, "not-a-date.json", {
            "all_sectors": [{"name": "石油行业", "sentiment": 60, "stocks": []}],
        })
        assert load_sentiment_snapshots(str(tmp_path)).empty
        assert resolve_snapshot_date(str(tmp_path / "not-a-date.json"), {}) is None


class TestNormalizationAndFillna:
    """0-100 → -1..1 归一化与跨快照缺失行业填充。"""

    def test_normalize_sentiment_unit(self):
        assert normalize_sentiment(50) == 0.0      # 中性
        assert normalize_sentiment(60) == pytest.approx(0.2)
        assert normalize_sentiment(40) == pytest.approx(-0.2)
        assert normalize_sentiment(200) == 1.0     # 越界裁剪到上界
        assert normalize_sentiment(-50) == -1.0    # 越界裁剪到下界
        assert normalize_sentiment(None) == 0.0    # 缺失 → 中性
        assert normalize_sentiment("不可解析") == 0.0

    def test_panel_normalization_and_fillna(self, tmp_path):
        _write_snapshot(tmp_path, "20240101.json", {
            "date": "2024-01-01",
            "all_sectors": [
                {"name": "石油行业", "sentiment": 60, "stocks": []},
                {"name": "科技行业", "sentiment": 40, "stocks": []},
            ],
        })
        # 第二个快照缺少"科技行业"，应填中性 0
        _write_snapshot(tmp_path, "20240102.json", {
            "all_sectors": [
                {"name": "石油行业", "sentiment": 100, "stocks": []},
            ],
        })

        panel = load_sentiment_snapshots(str(tmp_path))

        assert panel.index.name == "日期"
        assert panel.shape == (2, 2)
        assert panel.loc[pd.Timestamp("2024-01-01"), "石油行业"] == pytest.approx(0.2)
        assert panel.loc[pd.Timestamp("2024-01-01"), "科技行业"] == pytest.approx(-0.2)
        assert panel.loc[pd.Timestamp("2024-01-02"), "石油行业"] == pytest.approx(1.0)
        assert panel.loc[pd.Timestamp("2024-01-02"), "科技行业"] == 0.0  # fillna
        assert panel.values.min() >= -1.0 and panel.values.max() <= 1.0

    def test_corrupt_json_skipped(self, tmp_path):
        (tmp_path / "20240103.json").write_text("{not json", encoding="utf-8")
        _write_snapshot(tmp_path, "20240104.json", {
            "all_sectors": [{"name": "石油行业", "sentiment": 60, "stocks": []}],
        })
        panel = load_sentiment_snapshots(str(tmp_path))
        assert list(panel.index) == [pd.Timestamp("2024-01-04")]

    def test_empty_dir_returns_empty(self, tmp_path):
        assert load_sentiment_snapshots(str(tmp_path)).empty


class TestBuildStockSentimentSeries:
    """个股情绪序列构建（成分股扫描路径，不依赖行业映射器）。"""

    def test_series_via_sector_membership_scan(self, tmp_path):
        # 980001 不在沪深300成分股列表中 → 映射器无结果 → 回退快照成分股扫描
        _write_snapshot(tmp_path, "20240101.json", {
            "all_sectors": [{
                "name": "测试行业", "sentiment": 70,
                "stocks": [{"code": "980001", "name": "合成股"}],
            }],
        })
        _write_snapshot(tmp_path, "20240102.json", {
            "all_sectors": [{
                "name": "测试行业", "sentiment": 30,
                "stocks": [{"code": "980001", "name": "合成股"}],
            }],
        })
        panel = load_sentiment_snapshots(str(tmp_path))

        series, sector = build_stock_sentiment_series(
            panel, "980001", snapshots_dir=str(tmp_path))

        assert sector == "测试行业"
        assert list(series.index) == list(panel.index)
        assert series.iloc[0] == pytest.approx(0.4)   # (70-50)/50
        assert series.iloc[1] == pytest.approx(-0.4)  # (30-50)/50

    def test_series_tolerates_sh_sz_prefix(self, tmp_path):
        _write_snapshot(tmp_path, "20240101.json", {
            "all_sectors": [{
                "name": "测试行业", "sentiment": 60,
                "stocks": [{"code": "980002", "name": "合成股"}],
            }],
        })
        panel = load_sentiment_snapshots(str(tmp_path))
        series, sector = build_stock_sentiment_series(
            panel, "sz980002", snapshots_dir=str(tmp_path))
        assert sector == "测试行业"
        assert series.iloc[0] == pytest.approx(0.2)

    def test_unknown_code_returns_empty(self, tmp_path):
        _write_snapshot(tmp_path, "20240101.json", {
            "all_sectors": [{"name": "测试行业", "sentiment": 60, "stocks": []}],
        })
        panel = load_sentiment_snapshots(str(tmp_path))
        series, sector = build_stock_sentiment_series(
            panel, "999999", snapshots_dir=str(tmp_path))
        assert series.empty
        assert sector is None

    def test_empty_panel_returns_empty(self):
        series, sector = build_stock_sentiment_series(pd.DataFrame(), "000001")
        assert series.empty
        assert sector is None


class TestBuildDailySummaries:
    """情绪日历按日聚合（top_sentiment 保留 0-100 原始量表）。"""

    def test_summaries_ascending_with_raw_scale(self, tmp_path):
        _write_snapshot(tmp_path, "20240101.json", {
            "date": "2024-01-01",
            "news_count": 12,
            "all_sectors": [
                {"name": "石油行业", "sentiment": 60, "stocks": []},
                {"name": "科技行业", "sentiment": 40, "stocks": []},
            ],
            # 无 top_sectors → 回退 all_sectors 中原始分最高者
        })
        _write_snapshot(tmp_path, "20240102.json", {
            "news_count": 3,
            "all_sectors": [{"name": "石油行业", "sentiment": 10, "stocks": []}],
            "top_sectors": [{"name": "银行行业", "sentiment": 88}],
        })

        summaries = build_daily_summaries(str(tmp_path))

        assert [s["date"] for s in summaries] == ["2024-01-01", "2024-01-02"]
        first, second = summaries
        assert first == {
            "date": "2024-01-01", "sectors_count": 2,
            "top_sentiment": 60, "top_sector_name": "石油行业", "news_count": 12,
        }
        # top_sectors 榜单优先于 all_sectors 回退
        assert second["top_sentiment"] == 88
        assert second["top_sector_name"] == "银行行业"
        assert second["sectors_count"] == 1
        assert second["news_count"] == 3

    def test_summaries_empty_dir(self, tmp_path):
        assert build_daily_summaries(str(tmp_path)) == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
