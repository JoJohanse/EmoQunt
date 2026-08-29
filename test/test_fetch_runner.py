# coding=utf-8
"""fetch_runner.run_source_chain 纯逻辑单测。

用假 source callable 验证统一回退链 runner 的契约：
- 逐源尝试：成功即返回、异常/空 DataFrame/None 视为失败并回退下一源
- 源顺序：严格按 chain 顺序尝试，成功后不再触碰后续源
- health 打点：每源恰好一次 record_source_health(name, ok)，顺序与尝试顺序一致
- 全失败 / 空 chain：返回空 DataFrame

不依赖网络。运行：pytest test/test_fetch_runner.py -v
"""
import logging
import os
import sys

import pandas as pd
import pytest

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from src.data import fetch_runner
from src.data.fetch_runner import run_source_chain


def _df(tag="ok"):
    """非空 DataFrame（内容不参与逻辑，仅用于身份断言）。"""
    return pd.DataFrame({"date": ["2024-01-02"], "close": [1.0], "src": [tag]})


@pytest.fixture(autouse=True)
def _health_recorder(monkeypatch):
    """将 fetch_runner 内的 record_source_health 替换为记录器，供打点断言。"""
    calls = []

    def _record(source, ok):
        calls.append((source, ok))

    monkeypatch.setattr(fetch_runner, "record_source_health", _record)
    return calls


def _run(chain):
    return run_source_chain(chain, logger=logging.getLogger("test.fetch_runner"),
                            context="测试上下文")


class TestSuccessAndOrder:
    """成功路径与源顺序。"""

    def test_first_source_success_returns_its_df(self, _health_recorder):
        second = _df("second")
        out = _run([
            ("a", lambda: _df("first")),
            ("b", lambda: second),
        ])
        # 返回首个成功源的数据本身（同一对象）
        assert out is not None and not out.empty
        assert out["src"].iloc[0] == "first"

    def test_sources_tried_in_chain_order(self, _health_recorder):
        order = []

        def _src(name, df):
            def _fetch():
                order.append(name)
                return df
            return _fetch

        out = _run([
            ("a", _src("a", pd.DataFrame())),
            ("b", _src("b", pd.DataFrame())),
            ("c", _src("c", _df("c"))),
            ("d", _src("d", _df("d"))),
        ])
        assert order == ["a", "b", "c"], "应严格按 chain 顺序尝试，成功后停止"
        assert out["src"].iloc[0] == "c"

    def test_success_skips_later_sources(self, _health_recorder):
        called = []
        _run([
            ("a", lambda: _df()),
            ("b", lambda: called.append("b") or _df()),
        ])
        assert called == [], "首源成功后不应调用后续源"


class TestFailureFallback:
    """异常 / 空数据视为失败并回退。"""

    def test_exception_falls_back(self, _health_recorder):
        out = _run([
            ("bad", lambda: (_ for _ in ()).throw(RuntimeError("网络超时"))),
            ("good", lambda: _df()),
        ])
        assert not out.empty
        assert _health_recorder == [("bad", False), ("good", True)]

    def test_empty_df_falls_back(self, _health_recorder):
        out = _run([
            ("empty", lambda: pd.DataFrame()),
            ("good", lambda: _df()),
        ])
        assert not out.empty
        assert _health_recorder == [("empty", False), ("good", True)]

    def test_none_falls_back(self, _health_recorder):
        out = _run([
            ("none", lambda: None),
            ("good", lambda: _df()),
        ])
        assert not out.empty
        assert _health_recorder == [("none", False), ("good", True)]

    def test_every_failure_mode_triggers_fallback(self, _health_recorder):
        """异常 / None / 空 DataFrame 三种失败形态都推进到下一源。"""
        order = []
        out = _run([
            ("exc", lambda: order.append("exc") or (_ for _ in ()).throw(ValueError("x"))),
            ("none", lambda: order.append("none") or None),
            ("empty", lambda: order.append("empty") or pd.DataFrame()),
            ("good", lambda: order.append("good") or _df()),
        ])
        assert order == ["exc", "none", "empty", "good"]
        assert not out.empty


class TestHealthRecording:
    """record_source_health 打点契约。"""

    def test_recorded_once_per_attempted_source(self, _health_recorder):
        _run([
            ("a", lambda: pd.DataFrame()),
            ("b", lambda: (_ for _ in ()).throw(RuntimeError("boom"))),
            ("c", lambda: _df()),
        ])
        # 每个被尝试的源恰好打点一次；未尝试的源不打点
        assert _health_recorder == [("a", False), ("b", False), ("c", True)]

    def test_disabled_source_not_recorded(self, _health_recorder):
        """调用方未把某源放进 chain（未启用）时，该源不应有打点记录。"""
        _run([("sina", lambda: _df())])
        assert _health_recorder == [("sina", True)]

    def test_all_fail_health_all_false(self, _health_recorder):
        _run([
            ("a", lambda: pd.DataFrame()),
            ("b", lambda: None),
            ("c", lambda: (_ for _ in ()).throw(RuntimeError("x"))),
        ])
        assert _health_recorder == [("a", False), ("b", False), ("c", False)]


class TestAllFailAndEmptyChain:
    """全失败与空链的兜底返回。"""

    def test_all_fail_returns_empty_df(self, _health_recorder):
        out = _run([
            ("a", lambda: pd.DataFrame()),
            ("b", lambda: (_ for _ in ()).throw(RuntimeError("x"))),
        ])
        assert isinstance(out, pd.DataFrame)
        assert out.empty

    def test_empty_chain_returns_empty_df(self, _health_recorder):
        out = _run([])
        assert isinstance(out, pd.DataFrame)
        assert out.empty
        assert _health_recorder == [], "空链不应产生任何打点"


class TestLogging:
    """warning 日志。"""

    def test_failure_and_success_logged(self, _health_recorder, caplog):
        with caplog.at_level(logging.WARNING, logger="test.fetch_runner"):
            _run([
                ("bad", lambda: (_ for _ in ()).throw(RuntimeError("网络超时"))),
                ("good", lambda: _df()),
            ])
        messages = [r.getMessage() for r in caplog.records]
        assert any("bad" in m and "失败" in m for m in messages), "单源异常应有 warning"
        assert any("测试上下文" in m for m in messages), "日志应携带 context"

    def test_all_fail_warning_logged(self, _health_recorder, caplog):
        with caplog.at_level(logging.WARNING, logger="test.fetch_runner"):
            _run([("a", lambda: pd.DataFrame())])
        messages = [r.getMessage() for r in caplog.records]
        assert any("所有数据源均失败" in m for m in messages)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
