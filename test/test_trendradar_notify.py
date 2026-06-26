# coding=utf-8
"""Characterization (golden-master) tests for trendradar notification/rendering functions.

These tests capture CURRENT behavior BEFORE refactoring. Do NOT modify the
production code (nes_data/trendradar/main.py). If a test fails, the expected
value must be updated to match the actual current output.
"""

import importlib.util
import os
import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Import the module under test (main.py is not a proper package, so we use
# importlib to load it with a non-conflicting module name)
# ---------------------------------------------------------------------------
_TRENDRADAR_DIR = str(
    Path(__file__).resolve().parents[1] / "nes_data" / "trendradar"
)
if _TRENDRADAR_DIR not in sys.path:
    sys.path.insert(0, _TRENDRADAR_DIR)

_SPEC = importlib.util.spec_from_file_location(
    "tr_main", os.path.join(_TRENDRADAR_DIR, "main.py")
)
assert _SPEC is not None, "Could not load spec for main.py"
assert _SPEC.loader is not None, "No loader for main.py spec"
tr = importlib.util.module_from_spec(_SPEC)
# Ensure CONFIG_PATH points to the trendradar config before load
os.environ.setdefault(
    "CONFIG_PATH", os.path.join(_TRENDRADAR_DIR, "config", "config.yaml")
)
_SPEC.loader.exec_module(tr)

# ---------------------------------------------------------------------------
# Fixed datetime for deterministic output
# ---------------------------------------------------------------------------
_FIXED_TIME = datetime(2025, 1, 15, 10, 30, 0)

# ---------------------------------------------------------------------------
# Helper fixtures / factories
# ---------------------------------------------------------------------------


def make_title(**overrides):
    """Return a valid title_data dict with sensible defaults."""
    d = {
        "ranks": [],
        "rank_threshold": 0,
        "mobile_url": "",
        "url": "http://x.com",
        "title": "测试标题",
        "source_name": "测试来源",
        "time_display": "10:30",
        "count": 1,
    }
    d.update(overrides)
    return d


def make_report(stats=None, new_titles=None, failed_ids=None, total_new_count=0):
    """Return a valid report_data dict."""
    return {
        "stats": stats or [],
        "new_titles": new_titles or [],
        "failed_ids": failed_ids or [],
        "total_new_count": total_new_count,
    }


# ---------------------------------------------------------------------------
# Shared report fixtures
# ---------------------------------------------------------------------------

# Titles used in simple_report
_T1 = make_title(title="AI突破", source_name="科技源", count=12)
_T2 = make_title(
    title="大模型应用", source_name="科技源", count=8, ranks=[1], rank_threshold=5
)
_T3 = make_title(
    title="芯片进展", source_name="芯片源", count=3, url="http://y.com"
)

simple_report = make_report(
    stats=[
        {"word": "人工智能", "count": 12, "titles": [_T1, _T2]},
        {"word": "芯片", "count": 3, "titles": [_T3]},
    ]
)

report_with_new = make_report(
    stats=[
        {"word": "人工智能", "count": 12, "titles": [_T1, _T2]},
        {"word": "芯片", "count": 3, "titles": [_T3]},
    ],
    new_titles=[
        {
            "source_name": "快讯",
            "titles": [
                make_title(title="突发新闻"),
                make_title(title="最新消息"),
            ],
        }
    ],
    total_new_count=2,
)

report_with_failed = make_report(
    stats=[
        {"word": "人工智能", "count": 12, "titles": [_T1]},
        {"word": "芯片", "count": 3, "titles": [_T3]},
    ],
    failed_ids=["weibo", "xueqiu"],
)

empty_report = make_report()

# Large report to force multi-batch splitting
_many_titles = [
    make_title(
        title=f"新闻标题第{k+1}号",
        source_name="大源",
        count=2,
        ranks=[k + 1],
        rank_threshold=5,
    )
    for k in range(30)
]
large_report = make_report(
    stats=[
        {"word": "热点词A", "count": 50, "titles": _many_titles},
        {"word": "热点词B", "count": 25, "titles": _many_titles[:15]},
    ]
)

# ====== Default max-bytes per platform ======
_DEFAULT_MAX_BYTES = {
    "feishu": tr.CONFIG.get("FEISHU_BATCH_SIZE", 29000),
    "dingtalk": tr.CONFIG.get("DINGTALK_BATCH_SIZE", 20000),
    "wework": tr.CONFIG.get("MESSAGE_BATCH_SIZE", 4000),
    "telegram": tr.CONFIG.get("MESSAGE_BATCH_SIZE", 4000),
    "ntfy": 3800,
}

# ====== Golden-master expected outputs for split_content_into_batches ======
# All captured with _FIXED_TIME = datetime(2025, 1, 15, 10, 30, 0)

_SPLIT_DEFAULT_MASTER_FEISHU = (
    "📊 **热点词汇统计**\n\n"
    "🔥 <font color='grey'>[1/2]</font> **人工智能** : <font color='red'>12</font> 条\n\n"
    "  1. <font color='grey'>[科技源]</font> [AI突破](http://x.com) <font color='grey'>- 10:30</font> <font color='green'>(12次)</font>\n\n"
    "  2. <font color='grey'>[科技源]</font> [大模型应用](http://x.com) <font color='red'>**[1]**</font> <font color='grey'>- 10:30</font> <font color='green'>(8次)</font>\n\n"
    "━━━━━━━━━━━━━━━━━━━\n\n"
    "📌 <font color='grey'>[2/2]</font> **芯片** : 3 条\n\n"
    "  1. <font color='grey'>[芯片源]</font> [芯片进展](http://y.com) <font color='grey'>- 10:30</font> <font color='green'>(3次)</font>\n\n\n"
    "<font color='grey'>更新时间：2025-01-15 10:30:00</font>"
)

_SPLIT_DEFAULT_MASTER_DINGTALK = (
    "**总新闻数：** 3\n\n"
    "**时间：** 2025-01-15 10:30:00\n\n"
    "**类型：** 热点分析报告\n\n"
    "---\n\n"
    "📊 **热点词汇统计**\n\n"
    "🔥 [1/2] **人工智能** : **12** 条\n\n"
    "  1. [科技源] [AI突破](http://x.com) - 10:30 (12次)\n\n"
    "  2. [科技源] [大模型应用](http://x.com) **[1]** - 10:30 (8次)\n\n"
    "---\n\n"
    "📌 [2/2] **芯片** : 3 条\n\n"
    "  1. [芯片源] [芯片进展](http://y.com) - 10:30 (3次)\n\n\n"
    "> 更新时间：2025-01-15 10:30:00"
)

_SPLIT_DEFAULT_MASTER_WEWORK = (
    "**总新闻数：** 3\n\n\n\n"
    "📊 **热点词汇统计**\n\n"
    "🔥 [1/2] **人工智能** : **12** 条\n\n"
    "  1. [科技源] [AI突破](http://x.com) - 10:30 (12次)\n\n"
    "  2. [科技源] [大模型应用](http://x.com) **[1]** - 10:30 (8次)\n\n\n\n\n"
    "📌 [2/2] **芯片** : 3 条\n\n"
    "  1. [芯片源] [芯片进展](http://y.com) - 10:30 (3次)\n\n\n\n"
    "> 更新时间：2025-01-15 10:30:00"
)

_SPLIT_DEFAULT_MASTER_TELEGRAM = (
    "总新闻数： 3\n\n"
    "📊 热点词汇统计\n\n"
    "🔥 [1/2] 人工智能 : 12 条\n\n"
    "  1. [科技源] <a href=\"http://x.com\">AI突破</a> <code>- 10:30</code> <code>(12次)</code>\n\n"
    "  2. [科技源] <a href=\"http://x.com\">大模型应用</a> <b>[1]</b> <code>- 10:30</code> <code>(8次)</code>\n\n\n"
    "📌 [2/2] 芯片 : 3 条\n\n"
    "  1. [芯片源] <a href=\"http://y.com\">芯片进展</a> <code>- 10:30</code> <code>(3次)</code>\n\n\n"
    "更新时间：2025-01-15 10:30:00"
)

_SPLIT_DEFAULT_MASTER_NTFY = (
    "**总新闻数：** 3\n\n"
    "📊 **热点词汇统计**\n\n"
    "🔥 [1/2] **人工智能** : **12** 条\n\n"
    "  1. [科技源] [AI突破](http://x.com) `- 10:30` `(12次)`\n\n"
    "  2. [科技源] [大模型应用](http://x.com) **[1]** `- 10:30` `(8次)`\n\n\n"
    "📌 [2/2] **芯片** : 3 条\n\n"
    "  1. [芯片源] [芯片进展](http://y.com) `- 10:30` `(3次)`\n\n\n"
    "> 更新时间：2025-01-15 10:30:00"
)

# An even larger report that exceeds ntfy default max_bytes (3800)
_even_more_titles_A = [
    make_title(
        title=f"新闻标题第{k+1}号",
        source_name="大源",
        count=2,
        ranks=[k + 1],
        rank_threshold=5,
    )
    for k in range(50)
]
_even_more_titles_B = [
    make_title(
        title=f"额外新闻第{k+1}号",
        source_name="大源",
        count=3,
        ranks=[k + 1],
        rank_threshold=5,
    )
    for k in range(25)
]
even_larger_report = make_report(
    stats=[
        {"word": "热点词A", "count": 50, "titles": _even_more_titles_A},
        {"word": "热点词B", "count": 25, "titles": _even_more_titles_B},
    ]
)

_SPLIT_NTFY_MULTIBATCH_MASTER = [
    "**总新闻数：** 75\n\n"
    "📊 **热点词汇统计**\n\n"
    "🔥 [1/2] **热点词A** : **50** 条\n\n"
    "  1. [大源] [新闻标题第1号](http://x.com) **[1]** `- 10:30` `(2次)`\n\n"
    "  2. [大源] [新闻标题第2号](http://x.com) **[2]** `- 10:30` `(2次)`\n\n"
    "  3. [大源] [新闻标题第3号](http://x.com) **[3]** `- 10:30` `(2次)`\n\n"
    "  4. [大源] [新闻标题第4号](http://x.com) **[4]** `- 10:30` `(2次)`\n\n"
    "  5. [大源] [新闻标题第5号](http://x.com) **[5]** `- 10:30` `(2次)`\n\n"
    "  6. [大源] [新闻标题第6号](http://x.com) [6] `- 10:30` `(2次)`\n\n"
    "  7. [大源] [新闻标题第7号](http://x.com) [7] `- 10:30` `(2次)`\n\n"
    "  8. [大源] [新闻标题第8号](http://x.com) [8] `- 10:30` `(2次)`\n\n"
    "  9. [大源] [新闻标题第9号](http://x.com) [9] `- 10:30` `(2次)`\n\n"
    "  10. [大源] [新闻标题第10号](http://x.com) [10] `- 10:30` `(2次)`\n\n"
    "  11. [大源] [新闻标题第11号](http://x.com) [11] `- 10:30` `(2次)`\n\n"
    "  12. [大源] [新闻标题第12号](http://x.com) [12] `- 10:30` `(2次)`\n\n"
    "  13. [大源] [新闻标题第13号](http://x.com) [13] `- 10:30` `(2次)`\n\n"
    "  14. [大源] [新闻标题第14号](http://x.com) [14] `- 10:30` `(2次)`\n\n"
    "  15. [大源] [新闻标题第15号](http://x.com) [15] `- 10:30` `(2次)`\n\n"
    "  16. [大源] [新闻标题第16号](http://x.com) [16] `- 10:30` `(2次)`\n\n"
    "  17. [大源] [新闻标题第17号](http://x.com) [17] `- 10:30` `(2次)`\n\n"
    "  18. [大源] [新闻标题第18号](http://x.com) [18] `- 10:30` `(2次)`\n\n"
    "  19. [大源] [新闻标题第19号](http://x.com) [19] `- 10:30` `(2次)`\n\n"
    "  20. [大源] [新闻标题第20号](http://x.com) [20] `- 10:30` `(2次)`\n\n"
    "  21. [大源] [新闻标题第21号](http://x.com) [21] `- 10:30` `(2次)`\n\n"
    "  22. [大源] [新闻标题第22号](http://x.com) [22] `- 10:30` `(2次)`\n\n"
    "  23. [大源] [新闻标题第23号](http://x.com) [23] `- 10:30` `(2次)`\n\n"
    "  24. [大源] [新闻标题第24号](http://x.com) [24] `- 10:30` `(2次)`\n\n"
    "  25. [大源] [新闻标题第25号](http://x.com) [25] `- 10:30` `(2次)`\n\n"
    "  26. [大源] [新闻标题第26号](http://x.com) [26] `- 10:30` `(2次)`\n\n"
    "  27. [大源] [新闻标题第27号](http://x.com) [27] `- 10:30` `(2次)`\n\n"
    "  28. [大源] [新闻标题第28号](http://x.com) [28] `- 10:30` `(2次)`\n\n"
    "  29. [大源] [新闻标题第29号](http://x.com) [29] `- 10:30` `(2次)`\n\n"
    "  30. [大源] [新闻标题第30号](http://x.com) [30] `- 10:30` `(2次)`\n\n"
    "  31. [大源] [新闻标题第31号](http://x.com) [31] `- 10:30` `(2次)`\n\n"
    "  32. [大源] [新闻标题第32号](http://x.com) [32] `- 10:30` `(2次)`\n\n"
    "  33. [大源] [新闻标题第33号](http://x.com) [33] `- 10:30` `(2次)`\n\n"
    "  34. [大源] [新闻标题第34号](http://x.com) [34] `- 10:30` `(2次)`\n\n"
    "  35. [大源] [新闻标题第35号](http://x.com) [35] `- 10:30` `(2次)`\n\n"
    "  36. [大源] [新闻标题第36号](http://x.com) [36] `- 10:30` `(2次)`\n\n"
    "  37. [大源] [新闻标题第37号](http://x.com) [37] `- 10:30` `(2次)`\n\n"
    "  38. [大源] [新闻标题第38号](http://x.com) [38] `- 10:30` `(2次)`\n\n"
    "  39. [大源] [新闻标题第39号](http://x.com) [39] `- 10:30` `(2次)`\n\n"
    "  40. [大源] [新闻标题第40号](http://x.com) [40] `- 10:30` `(2次)`\n\n"
    "  41. [大源] [新闻标题第41号](http://x.com) [41] `- 10:30` `(2次)`\n\n"
    "  42. [大源] [新闻标题第42号](http://x.com) [42] `- 10:30` `(2次)`\n\n"
    "  43. [大源] [新闻标题第43号](http://x.com) [43] `- 10:30` `(2次)`\n\n"
    "  44. [大源] [新闻标题第44号](http://x.com) [44] `- 10:30` `(2次)`\n\n"
    "  45. [大源] [新闻标题第45号](http://x.com) [45] `- 10:30` `(2次)`\n\n"
    "  46. [大源] [新闻标题第46号](http://x.com) [46] `- 10:30` `(2次)`\n\n"
    "  47. [大源] [新闻标题第47号](http://x.com) [47] `- 10:30` `(2次)`\n\n\n\n"
    "> 更新时间：2025-01-15 10:30:00",
    "**总新闻数：** 75\n\n"
    "📊 **热点词汇统计**\n\n"
    "🔥 [1/2] **热点词A** : **50** 条\n\n"
    "  48. [大源] [新闻标题第48号](http://x.com) [48] `- 10:30` `(2次)`\n\n"
    "  49. [大源] [新闻标题第49号](http://x.com) [49] `- 10:30` `(2次)`\n\n"
    "  50. [大源] [新闻标题第50号](http://x.com) [50] `- 10:30` `(2次)`\n\n\n"
    "🔥 [2/2] **热点词B** : **25** 条\n\n"
    "  1. [大源] [额外新闻第1号](http://x.com) **[1]** `- 10:30` `(3次)`\n\n"
    "  2. [大源] [额外新闻第2号](http://x.com) **[2]** `- 10:30` `(3次)`\n\n"
    "  3. [大源] [额外新闻第3号](http://x.com) **[3]** `- 10:30` `(3次)`\n\n"
    "  4. [大源] [额外新闻第4号](http://x.com) **[4]** `- 10:30` `(3次)`\n\n"
    "  5. [大源] [额外新闻第5号](http://x.com) **[5]** `- 10:30` `(3次)`\n\n"
    "  6. [大源] [额外新闻第6号](http://x.com) [6] `- 10:30` `(3次)`\n\n"
    "  7. [大源] [额外新闻第7号](http://x.com) [7] `- 10:30` `(3次)`\n\n"
    "  8. [大源] [额外新闻第8号](http://x.com) [8] `- 10:30` `(3次)`\n\n"
    "  9. [大源] [额外新闻第9号](http://x.com) [9] `- 10:30` `(3次)`\n\n"
    "  10. [大源] [额外新闻第10号](http://x.com) [10] `- 10:30` `(3次)`\n\n"
    "  11. [大源] [额外新闻第11号](http://x.com) [11] `- 10:30` `(3次)`\n\n"
    "  12. [大源] [额外新闻第12号](http://x.com) [12] `- 10:30` `(3次)`\n\n"
    "  13. [大源] [额外新闻第13号](http://x.com) [13] `- 10:30` `(3次)`\n\n"
    "  14. [大源] [额外新闻第14号](http://x.com) [14] `- 10:30` `(3次)`\n\n"
    "  15. [大源] [额外新闻第15号](http://x.com) [15] `- 10:30` `(3次)`\n\n"
    "  16. [大源] [额外新闻第16号](http://x.com) [16] `- 10:30` `(3次)`\n\n"
    "  17. [大源] [额外新闻第17号](http://x.com) [17] `- 10:30` `(3次)`\n\n"
    "  18. [大源] [额外新闻第18号](http://x.com) [18] `- 10:30` `(3次)`\n\n"
    "  19. [大源] [额外新闻第19号](http://x.com) [19] `- 10:30` `(3次)`\n\n"
    "  20. [大源] [额外新闻第20号](http://x.com) [20] `- 10:30` `(3次)`\n\n"
    "  21. [大源] [额外新闻第21号](http://x.com) [21] `- 10:30` `(3次)`\n\n"
    "  22. [大源] [额外新闻第22号](http://x.com) [22] `- 10:30` `(3次)`\n\n"
    "  23. [大源] [额外新闻第23号](http://x.com) [23] `- 10:30` `(3次)`\n\n"
    "  24. [大源] [额外新闻第24号](http://x.com) [24] `- 10:30` `(3次)`\n\n"
    "  25. [大源] [额外新闻第25号](http://x.com) [25] `- 10:30` `(3次)`\n\n\n"
    "> 更新时间：2025-01-15 10:30:00",
]


# ======================================================================
# format_title_for_platform
# ======================================================================


class TestFormatTitleForPlatform:
    """Golden-master tests for format_title_for_platform."""

    def test_feishu_default(self):
        r = tr.format_title_for_platform("feishu", make_title())
        expected = "<font color='grey'>[测试来源]</font> [测试标题](http://x.com) <font color='grey'>- 10:30</font>"
        assert r == expected

    def test_dingtalk_default(self):
        r = tr.format_title_for_platform("dingtalk", make_title())
        expected = "[测试来源] [测试标题](http://x.com) - 10:30"
        assert r == expected

    def test_wework_default(self):
        r = tr.format_title_for_platform("wework", make_title())
        expected = "[测试来源] [测试标题](http://x.com) - 10:30"
        assert r == expected

    def test_telegram_default(self):
        r = tr.format_title_for_platform("telegram", make_title())
        expected = '[测试来源] <a href="http://x.com">测试标题</a> <code>- 10:30</code>'
        assert r == expected

    def test_ntfy_default(self):
        r = tr.format_title_for_platform("ntfy", make_title())
        expected = "[测试来源] [测试标题](http://x.com) `- 10:30`"
        assert r == expected

    def test_html_default(self):
        r = tr.format_title_for_platform("html", make_title())
        expected = '[测试来源] <a href="http://x.com" target="_blank" class="news-link">测试标题</a> <font color=\'grey\'>- 10:30</font>'
        assert r == expected

    # --- show_source=False ---
    def test_feishu_no_source(self):
        r = tr.format_title_for_platform("feishu", make_title(), show_source=False)
        expected = "[测试标题](http://x.com) <font color='grey'>- 10:30</font>"
        assert r == expected

    def test_dingtalk_no_source(self):
        r = tr.format_title_for_platform("dingtalk", make_title(), show_source=False)
        expected = "[测试标题](http://x.com) - 10:30"
        assert r == expected

    def test_wework_no_source(self):
        r = tr.format_title_for_platform("wework", make_title(), show_source=False)
        expected = "[测试标题](http://x.com) - 10:30"
        assert r == expected

    def test_telegram_no_source(self):
        r = tr.format_title_for_platform("telegram", make_title(), show_source=False)
        expected = '<a href="http://x.com">测试标题</a> <code>- 10:30</code>'
        assert r == expected

    def test_ntfy_no_source(self):
        r = tr.format_title_for_platform("ntfy", make_title(), show_source=False)
        expected = "[测试标题](http://x.com) `- 10:30`"
        assert r == expected

    # --- count > 1 ---
    def test_feishu_count5(self):
        r = tr.format_title_for_platform("feishu", make_title(count=5))
        expected = "<font color='grey'>[测试来源]</font> [测试标题](http://x.com) <font color='grey'>- 10:30</font> <font color='green'>(5次)</font>"
        assert r == expected

    def test_dingtalk_count5(self):
        r = tr.format_title_for_platform("dingtalk", make_title(count=5))
        expected = "[测试来源] [测试标题](http://x.com) - 10:30 (5次)"
        assert r == expected

    def test_wework_count5(self):
        r = tr.format_title_for_platform("wework", make_title(count=5))
        expected = "[测试来源] [测试标题](http://x.com) - 10:30 (5次)"
        assert r == expected

    def test_telegram_count5(self):
        r = tr.format_title_for_platform("telegram", make_title(count=5))
        expected = '[测试来源] <a href="http://x.com">测试标题</a> <code>- 10:30</code> <code>(5次)</code>'
        assert r == expected

    def test_ntfy_count5(self):
        r = tr.format_title_for_platform("ntfy", make_title(count=5))
        expected = "[测试来源] [测试标题](http://x.com) `- 10:30` `(5次)`"
        assert r == expected

    # --- is_new=True ---
    def test_feishu_is_new(self):
        r = tr.format_title_for_platform("feishu", make_title(is_new=True))
        expected = "<font color='grey'>[测试来源]</font> 🆕 [测试标题](http://x.com) <font color='grey'>- 10:30</font>"
        assert r == expected

    def test_dingtalk_is_new(self):
        r = tr.format_title_for_platform("dingtalk", make_title(is_new=True))
        expected = "[测试来源] 🆕 [测试标题](http://x.com) - 10:30"
        assert r == expected

    def test_wework_is_new(self):
        r = tr.format_title_for_platform("wework", make_title(is_new=True))
        expected = "[测试来源] 🆕 [测试标题](http://x.com) - 10:30"
        assert r == expected

    def test_telegram_is_new(self):
        r = tr.format_title_for_platform("telegram", make_title(is_new=True))
        expected = '[测试来源] 🆕 <a href="http://x.com">测试标题</a> <code>- 10:30</code>'
        assert r == expected

    def test_ntfy_is_new(self):
        r = tr.format_title_for_platform("ntfy", make_title(is_new=True))
        expected = "[测试来源] 🆕 [测试标题](http://x.com) `- 10:30`"
        assert r == expected

    def test_html_is_new(self):
        r = tr.format_title_for_platform("html", make_title(is_new=True))
        expected = "<div class='new-title'>🆕 [测试来源] <a href=\"http://x.com\" target=\"_blank\" class=\"news-link\">测试标题</a> <font color='grey'>- 10:30</font></div>"
        assert r == expected

    # --- url="" (no link) ---
    def test_feishu_no_url(self):
        r = tr.format_title_for_platform("feishu", make_title(url=""))
        expected = "<font color='grey'>[测试来源]</font> 测试标题 <font color='grey'>- 10:30</font>"
        assert r == expected

    def test_dingtalk_no_url(self):
        r = tr.format_title_for_platform("dingtalk", make_title(url=""))
        expected = "[测试来源] 测试标题 - 10:30"
        assert r == expected

    def test_wework_no_url(self):
        r = tr.format_title_for_platform("wework", make_title(url=""))
        expected = "[测试来源] 测试标题 - 10:30"
        assert r == expected

    def test_telegram_no_url(self):
        r = tr.format_title_for_platform("telegram", make_title(url=""))
        expected = "[测试来源] 测试标题 <code>- 10:30</code>"
        assert r == expected

    def test_ntfy_no_url(self):
        r = tr.format_title_for_platform("ntfy", make_title(url=""))
        expected = "[测试来源] 测试标题 `- 10:30`"
        assert r == expected

    def test_html_no_url(self):
        r = tr.format_title_for_platform("html", make_title(url=""))
        expected = "[测试来源] <span class=\"no-link\">测试标题</span> <font color='grey'>- 10:30</font>"
        assert r == expected

    # --- ranks with threshold ---
    def test_feishu_ranks(self):
        r = tr.format_title_for_platform(
            "feishu", make_title(ranks=[1, 3], rank_threshold=5)
        )
        expected = "<font color='grey'>[测试来源]</font> [测试标题](http://x.com) <font color='red'>**[1 - 3]**</font> <font color='grey'>- 10:30</font>"
        assert r == expected

    def test_dingtalk_ranks(self):
        r = tr.format_title_for_platform(
            "dingtalk", make_title(ranks=[1, 3], rank_threshold=5)
        )
        expected = "[测试来源] [测试标题](http://x.com) **[1 - 3]** - 10:30"
        assert r == expected

    def test_wework_ranks(self):
        r = tr.format_title_for_platform(
            "wework", make_title(ranks=[1, 3], rank_threshold=5)
        )
        expected = "[测试来源] [测试标题](http://x.com) **[1 - 3]** - 10:30"
        assert r == expected

    def test_telegram_ranks(self):
        r = tr.format_title_for_platform(
            "telegram", make_title(ranks=[1, 3], rank_threshold=5)
        )
        expected = '[测试来源] <a href="http://x.com">测试标题</a> <b>[1 - 3]</b> <code>- 10:30</code>'
        assert r == expected

    def test_ntfy_ranks(self):
        r = tr.format_title_for_platform(
            "ntfy", make_title(ranks=[1, 3], rank_threshold=5)
        )
        expected = "[测试来源] [测试标题](http://x.com) **[1 - 3]** `- 10:30`"
        assert r == expected

    def test_html_ranks(self):
        r = tr.format_title_for_platform(
            "html", make_title(ranks=[1], rank_threshold=5)
        )
        expected = "[测试来源] <a href=\"http://x.com\" target=\"_blank\" class=\"news-link\">测试标题</a> <font color='red'><strong>[1]</strong></font> <font color='grey'>- 10:30</font>"
        assert r == expected

    # --- unknown platform returns cleaned title ---
    def test_unknown_platform(self):
        r = tr.format_title_for_platform("unknown", make_title())
        assert r == "测试标题"


# ======================================================================
# split_content_into_batches  (requires patched get_beijing_time)
# ======================================================================


class TestSplitContentIntoBatches:
    """Tests for split_content_into_batches."""

    # ---- byte-size invariant ----

    @pytest.mark.parametrize("platform", ["feishu", "dingtalk", "wework", "telegram", "ntfy"])
    def test_default_max_bytes_invariant(self, platform):
        """Every batch must be under the default byte limit."""
        with patch.object(tr, "get_beijing_time", return_value=_FIXED_TIME):
            batches = tr.split_content_into_batches(simple_report, platform)
        mb = _DEFAULT_MAX_BYTES[platform]
        assert isinstance(batches, list)
        assert len(batches) >= 1
        for b in batches:
            assert len(b.encode("utf-8")) < mb, (
                f"Batch size {len(b.encode('utf-8'))} >= {mb} for {platform}"
            )

    @pytest.mark.parametrize("platform", ["feishu", "dingtalk", "wework", "telegram", "ntfy"])
    def test_small_max_bytes_forces_multibatch(self, platform):
        """With a small max_bytes, the large report is split into many batches."""
        with patch.object(tr, "get_beijing_time", return_value=_FIXED_TIME):
            batches = tr.split_content_into_batches(large_report, platform, max_bytes=500)
        mb = 500
        assert isinstance(batches, list)
        assert len(batches) > 1, f"{platform} should produce multiple batches"
        for b in batches:
            assert len(b.encode("utf-8")) < mb, (
                f"Batch size {len(b.encode('utf-8'))} >= {mb} for {platform}"
            )

    # ---- empty report ----

    @pytest.mark.parametrize("platform", ["feishu", "dingtalk", "wework", "telegram", "ntfy"])
    def test_empty_report(self, platform):
        """Empty report returns one batch with '暂无匹配' text."""
        with patch.object(tr, "get_beijing_time", return_value=_FIXED_TIME):
            batches = tr.split_content_into_batches(empty_report, platform)
        assert isinstance(batches, list)
        assert len(batches) == 1
        assert "暂无匹配" in batches[0]

    # ---- update_info ----

    @pytest.mark.parametrize("platform", ["feishu", "dingtalk", "wework", "telegram", "ntfy"])
    def test_with_update_info(self, platform):
        """With update_info, the batch content contains version text."""
        with patch.object(tr, "get_beijing_time", return_value=_FIXED_TIME):
            batches = tr.split_content_into_batches(
                simple_report,
                platform,
                update_info={"remote_version": "9.9.9", "current_version": "1.0.0"},
            )
        assert isinstance(batches, list)
        assert len(batches) >= 1
        combined = "".join(batches)
        assert "9.9.9" in combined, f"{platform}: version text not found"

    # ---- golden-master exact output ----

    def test_golden_master_feishu_simple_max500(self):
        """Exact golden-master output for known inputs (most critical regression test)."""
        with patch.object(tr, "get_beijing_time", return_value=_FIXED_TIME):
            batches = tr.split_content_into_batches(
                simple_report, "feishu", max_bytes=500
            )
        assert len(batches) == 2
        assert batches[0] == (
            "📊 **热点词汇统计**\n\n"
            "🔥 <font color='grey'>[1/2]</font> **人工智能** : <font color='red'>12</font> 条\n\n"
            "  1. <font color='grey'>[科技源]</font> [AI突破](http://x.com) <font color='grey'>- 10:30</font> <font color='green'>(12次)</font>\n\n"
            "  2. <font color='grey'>[科技源]</font> [大模型应用](http://x.com) <font color='red'>**[1]**</font> <font color='grey'>- 10:30</font> <font color='green'>(8次)</font>\n\n\n"
            "<font color='grey'>更新时间：2025-01-15 10:30:00</font>"
        )
        assert batches[1] == (
            "📊 **热点词汇统计**\n\n"
            "📌 <font color='grey'>[2/2]</font> **芯片** : 3 条\n\n"
            "  1. <font color='grey'>[芯片源]</font> [芯片进展](http://y.com) <font color='grey'>- 10:30</font> <font color='green'>(3次)</font>\n\n\n"
            "<font color='grey'>更新时间：2025-01-15 10:30:00</font>"
        )

    # ---- golden-master: default max_bytes (production path) ----

    def test_split_default_master_feishu(self):
        with patch.object(tr, "get_beijing_time", return_value=_FIXED_TIME):
            batches = tr.split_content_into_batches(simple_report, "feishu")
        assert len(batches) == 1
        assert batches[0] == _SPLIT_DEFAULT_MASTER_FEISHU

    def test_split_default_master_dingtalk(self):
        with patch.object(tr, "get_beijing_time", return_value=_FIXED_TIME):
            batches = tr.split_content_into_batches(simple_report, "dingtalk")
        assert len(batches) == 1
        assert batches[0] == _SPLIT_DEFAULT_MASTER_DINGTALK

    def test_split_default_master_wework(self):
        with patch.object(tr, "get_beijing_time", return_value=_FIXED_TIME):
            batches = tr.split_content_into_batches(simple_report, "wework")
        assert len(batches) == 1
        assert batches[0] == _SPLIT_DEFAULT_MASTER_WEWORK

    def test_split_default_master_telegram(self):
        with patch.object(tr, "get_beijing_time", return_value=_FIXED_TIME):
            batches = tr.split_content_into_batches(simple_report, "telegram")
        assert len(batches) == 1
        assert batches[0] == _SPLIT_DEFAULT_MASTER_TELEGRAM

    def test_split_default_master_ntfy(self):
        with patch.object(tr, "get_beijing_time", return_value=_FIXED_TIME):
            batches = tr.split_content_into_batches(simple_report, "ntfy")
        assert len(batches) == 1
        assert batches[0] == _SPLIT_DEFAULT_MASTER_NTFY

    # ---- golden-master: ntfy default multibatch ----

    def test_split_ntfy_default_multibatch_master(self):
        """ntfy's default max_bytes (3800) triggers multi-batch for a large report."""
        with patch.object(tr, "get_beijing_time", return_value=_FIXED_TIME):
            batches = tr.split_content_into_batches(even_larger_report, "ntfy")
        assert batches == _SPLIT_NTFY_MULTIBATCH_MASTER


# ======================================================================
# Send functions  (mock requests.post)
# ======================================================================


class _MockResponse:
    """Helper to create a fake requests.Response-like object."""

    def __init__(self, status_code, json_data):
        self.status_code = status_code
        self._json_data = json_data

    def json(self):
        return self._json_data


class TestSendToFeishu:
    """Mock-based tests for send_to_feishu."""

    def test_success(self):
        mock_resp = _MockResponse(200, {"StatusCode": 0})
        with patch.object(tr, "requests", autospec=True) as mock_requests:
            with patch.object(tr, "time", autospec=True):
                mock_requests.post.return_value = mock_resp
                result = tr.send_to_feishu(
                    "http://hook.feishu",
                    simple_report,
                    "test",
                )
        assert result is True

    def test_success_code_key(self):
        """Some feishu responses use 'code' key instead of 'StatusCode'."""
        mock_resp = _MockResponse(200, {"code": 0})
        with patch.object(tr, "requests", autospec=True) as mock_requests:
            with patch.object(tr, "time", autospec=True):
                mock_requests.post.return_value = mock_resp
                result = tr.send_to_feishu(
                    "http://hook.feishu",
                    simple_report,
                    "test",
                )
        assert result is True

    def test_failure_response(self):
        """Non-zero StatusCode returns False."""
        mock_resp = _MockResponse(200, {"StatusCode": 1, "msg": "error"})
        with patch.object(tr, "requests", autospec=True) as mock_requests:
            with patch.object(tr, "time", autospec=True):
                mock_requests.post.return_value = mock_resp
                result = tr.send_to_feishu(
                    "http://hook.feishu",
                    simple_report,
                    "test",
                )
        assert result is False

    def test_http_error(self):
        """Non-200 status code returns False."""
        mock_resp = _MockResponse(400, {})
        with patch.object(tr, "requests", autospec=True) as mock_requests:
            with patch.object(tr, "time", autospec=True):
                mock_requests.post.return_value = mock_resp
                result = tr.send_to_feishu(
                    "http://hook.feishu",
                    simple_report,
                    "test",
                )
        assert result is False

    def test_exception(self):
        """Exception during request returns False."""
        with patch.object(tr, "requests", autospec=True) as mock_requests:
            with patch.object(tr, "time", autospec=True):
                mock_requests.post.side_effect = Exception("connection error")
                result = tr.send_to_feishu(
                    "http://hook.feishu",
                    simple_report,
                    "test",
                )
        assert result is False


class TestSendToDingtalk:
    """Mock-based tests for send_to_dingtalk."""

    def test_success(self):
        mock_resp = _MockResponse(200, {"errcode": 0})
        with patch.object(tr, "requests", autospec=True) as mock_requests:
            with patch.object(tr, "time", autospec=True):
                mock_requests.post.return_value = mock_resp
                result = tr.send_to_dingtalk(
                    "http://hook.dingtalk",
                    simple_report,
                    "test",
                )
        assert result is True

    def test_failure_response(self):
        mock_resp = _MockResponse(200, {"errcode": 1, "errmsg": "error"})
        with patch.object(tr, "requests", autospec=True) as mock_requests:
            with patch.object(tr, "time", autospec=True):
                mock_requests.post.return_value = mock_resp
                result = tr.send_to_dingtalk(
                    "http://hook.dingtalk",
                    simple_report,
                    "test",
                )
        assert result is False

    def test_exception(self):
        with patch.object(tr, "requests", autospec=True) as mock_requests:
            with patch.object(tr, "time", autospec=True):
                mock_requests.post.side_effect = Exception("connection error")
                result = tr.send_to_dingtalk(
                    "http://hook.dingtalk",
                    simple_report,
                    "test",
                )
        assert result is False


class TestSendToWework:
    """Mock-based tests for send_to_wework."""

    def test_success(self):
        mock_resp = _MockResponse(200, {"errcode": 0})
        with patch.object(tr, "requests", autospec=True) as mock_requests:
            with patch.object(tr, "time", autospec=True):
                mock_requests.post.return_value = mock_resp
                result = tr.send_to_wework(
                    "http://hook.wework",
                    simple_report,
                    "test",
                )
        assert result is True

    def test_failure_response(self):
        mock_resp = _MockResponse(200, {"errcode": 1, "errmsg": "error"})
        with patch.object(tr, "requests", autospec=True) as mock_requests:
            with patch.object(tr, "time", autospec=True):
                mock_requests.post.return_value = mock_resp
                result = tr.send_to_wework(
                    "http://hook.wework",
                    simple_report,
                    "test",
                )
        assert result is False

    def test_exception(self):
        with patch.object(tr, "requests", autospec=True) as mock_requests:
            with patch.object(tr, "time", autospec=True):
                mock_requests.post.side_effect = Exception("connection error")
                result = tr.send_to_wework(
                    "http://hook.wework",
                    simple_report,
                    "test",
                )
        assert result is False


class TestSendToTelegram:
    """Mock-based tests for send_to_telegram."""

    def test_success(self):
        mock_resp = _MockResponse(200, {"ok": True})
        with patch.object(tr, "requests", autospec=True) as mock_requests:
            with patch.object(tr, "time", autospec=True):
                mock_requests.post.return_value = mock_resp
                result = tr.send_to_telegram(
                    "bot123:abc",
                    "12345",
                    simple_report,
                    "test",
                )
        assert result is True

    def test_failure_response(self):
        mock_resp = _MockResponse(200, {"ok": False, "description": "error"})
        with patch.object(tr, "requests", autospec=True) as mock_requests:
            with patch.object(tr, "time", autospec=True):
                mock_requests.post.return_value = mock_resp
                result = tr.send_to_telegram(
                    "bot123:abc",
                    "12345",
                    simple_report,
                    "test",
                )
        assert result is False

    def test_exception(self):
        with patch.object(tr, "requests", autospec=True) as mock_requests:
            with patch.object(tr, "time", autospec=True):
                mock_requests.post.side_effect = Exception("connection error")
                result = tr.send_to_telegram(
                    "bot123:abc",
                    "12345",
                    simple_report,
                    "test",
                )
        assert result is False
