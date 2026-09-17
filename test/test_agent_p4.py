"""P4 agent 增量测试：策略上下文注入（src/agent/context.py）+ 新工具（src/agent/tools.py）。

覆盖：
- coerce_strategy_id 的宽容解析（None/''/0 → None，数字字符串 → int，垃圾 → None）
- build_strategy_context：存在/不存在、源码截断、最近回测/调优行（store 层直接种数据）
- with_strategy_context：SystemMessage 插到最后一条 HumanMessage 之前，缺省原样返回
- 双语上下文（set_request_lang 切换 en-US / zh-CN，测完恢复）
- 新工具：create_tuning_task / get_tuning_status / list_backtest_runs / get_run /
  list_factors / create_factor / analyze_factor（monkeypatch 服务层 + tmp DB 真实落库）
使用独立临时库（与 test_tuning.py 同款隔离模式）。不触网、不 import web_app、不测 SSE。
运行：pytest test/test_agent_p4.py -v
"""
import json
import os
import sys
import tempfile

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_TMPDIR = tempfile.mkdtemp(prefix="emoqunt_agent_p4_test_")

from src.services import factor_library as flib  # noqa: E402
from src.services import strategy_library as lib  # noqa: E402
from src.store import db as store  # noqa: E402
from src.utils.i18n import set_request_lang  # noqa: E402

# 合法代码策略源码（与 test_tuning.py 同款样例）
GOOD = '''STRATEGY_PARAMS = {"window": 10, "threshold": 0.5}


def initialize(context):
    pass


def handle_data(context, data):
    pass
'''

# 合法因子源码（最小形态，与 agent 工具 docstring 示例一致）
FACTOR_SOURCE = '''def compute(df):
    """动量：过去 20 日收益率。"""
    return df["收盘"].pct_change(20)
'''


@pytest.fixture(scope="module", autouse=True)
def _isolated_db():
    """独立临时库：QDT_STORE_DB_PATH 指 tmp 路径 + reset，测完恢复默认语言。"""
    os.environ["QDT_STORE_DB_PATH"] = os.path.join(_TMPDIR, "test_agent_p4.db")
    store.reset_for_tests()
    store.init_db()
    yield
    store.reset_for_tests()
    set_request_lang("zh-CN")


# ---------------------------------------------------------------------------
# 种数据助手（模块内缓存，避免重复创建撞名称唯一约束）
# ---------------------------------------------------------------------------
_CTX_CACHE = {}


def _ctx_strategy() -> int:
    """种一个代码策略（显式参数覆盖源码默认 → 上下文应出现漂移提示），返回 id。"""
    if "sid" not in _CTX_CACHE:
        _CTX_CACHE["sid"] = lib.create_code_strategy(
            "P4-上下文策略", "P4 上下文测试策略", "zh_a", GOOD, {"window": 15})["id"]
    return _CTX_CACHE["sid"]


def _seed_run(sid: int) -> int:
    """种一条成功回测运行（store 层直写），返回 run id。"""
    if "run_id" not in _CTX_CACHE:
        run_id = store.create_run(
            {
                "strategy_name": "P4-上下文策略", "stock_code": "000001", "market": "zh_a",
                "start_date": "2024-01-01", "end_date": "2024-03-31",
                "initial_capital": 100000.0, "commission_rate": 0.0003,
            },
            strategy_kind="code", strategy_id=sid)
        store.finish_run_if_active(
            run_id,
            {"总收益率": 0.12, "夏普比率": 1.5, "最大回撤": -0.08},
            ["2024-01-02", "2024-03-29"], [100000.0, 112000.0], [], [], 1234)
        _CTX_CACHE["run_id"] = run_id
    return _CTX_CACHE["run_id"]


def _seed_tuning(sid: int) -> int:
    """种一个调优任务（store 层直写，保持 queued 态），返回 task id。"""
    if "task_id" not in _CTX_CACHE:
        _CTX_CACHE["task_id"] = store.create_tuning_task(
            {
                "strategy_kind": "code", "strategy_id": sid, "strategy_name": "P4-上下文策略",
                "market": "zh_a", "stock_code": "000001",
                "start_date": "2024-01-01", "end_date": "2024-03-31",
                "initial_capital": 100000.0, "commission_rate": 0.0003,
                "param_grid_json": '{"window": [5, 15, 30]}', "grid_keys_json": '["window"]',
                "target_metric": "总收益率", "target_metric_desc": 1,
            },
            [{"combo_index": 0, "is_baseline": 1, "params": {"window": 15}}])
    return _CTX_CACHE["task_id"]


# ---------------------------------------------------------------------------
# coerce_strategy_id：请求体 id 的宽容解析
# ---------------------------------------------------------------------------
class TestCoerceStrategyId:
    def test_falsy_values_return_none(self):
        """None / 空串 / 0 都视为「未绑定策略」。"""
        from src.agent.context import coerce_strategy_id
        assert coerce_strategy_id(None) is None
        assert coerce_strategy_id("") is None
        assert coerce_strategy_id(0) is None

    def test_numeric_string_and_int(self):
        from src.agent.context import coerce_strategy_id
        assert coerce_strategy_id("12") == 12
        assert coerce_strategy_id(12) == 12

    def test_garbage_returns_none(self):
        from src.agent.context import coerce_strategy_id
        assert coerce_strategy_id("abc") is None


# ---------------------------------------------------------------------------
# build_strategy_context：策略 → 双语上下文文本
# ---------------------------------------------------------------------------
class TestBuildContext:
    def test_existing_strategy_contains_id_name_params_source(self):
        """策略存在 → 文本含 id/名称/生效参数（DB 为真相）/漂移提示/完整源码。"""
        from src.agent.context import build_strategy_context
        sid = _ctx_strategy()
        text = build_strategy_context(sid)
        assert text is not None
        assert f"- id: {sid}" in text
        assert "P4-上下文策略" in text
        assert "策略上下文" in text
        assert "window=15" in text  # 生效参数（DB 为真相）
        assert "源码默认值已被参数覆盖" in text  # 源码默认 window=10 ≠ 生效 15
        assert "def handle_data" in text  # 源码完整嵌入（未截断）

    def test_missing_strategy_returns_none(self):
        from src.agent.context import build_strategy_context
        assert build_strategy_context(999999) is None

    def test_source_truncated_when_clip_small(self, monkeypatch):
        """源码超长 → 按模块常量 _SOURCE_CLIP 截断并带截断标记（monkeypatch 成小值验证）。"""
        import src.agent.context as ctx_mod
        from src.agent.context import build_strategy_context
        sid = _ctx_strategy()
        assert len(GOOD) > 50
        monkeypatch.setattr(ctx_mod, "_SOURCE_CLIP", 50)
        text = build_strategy_context(sid)
        assert "已截断" in text
        assert GOOD.strip() not in text  # 完整源码不再整体出现
        monkeypatch.undo()
        assert GOOD.strip() in build_strategy_context(sid)  # 恢复后完整嵌入

    def test_recent_runs_line(self):
        """store 层种一条成功运行 → 上下文出现「最近回测」行（含指标中文键）。"""
        from src.agent.context import build_strategy_context
        sid = _ctx_strategy()
        run_id = _seed_run(sid)
        text = build_strategy_context(sid)
        assert "最近回测" in text
        assert f"run #{run_id}" in text
        assert "总收益率 0.12" in text

    def test_recent_tuning_line(self):
        """store 层种一个调优任务 → 上下文出现「最近调优任务」行（含状态）。"""
        from src.agent.context import build_strategy_context
        sid = _ctx_strategy()
        task_id = _seed_tuning(sid)
        text = build_strategy_context(sid)
        assert "最近调优任务" in text
        assert f"tuning task #{task_id}" in text
        assert "queued" in text


# ---------------------------------------------------------------------------
# 双语上下文（en-US / zh-CN）
# ---------------------------------------------------------------------------
class TestBilingualContext:
    def test_en_context_markers(self):
        """en-US 下标题与回测摘要行用英文措辞。"""
        from src.agent.context import build_strategy_context
        sid = _ctx_strategy()
        _seed_run(sid)
        _seed_tuning(sid)
        set_request_lang("en-US")
        try:
            text = build_strategy_context(sid)
            assert "[Strategy Context]" in text
            assert "Name" in text
            assert "Recent backtest runs" in text
            assert "Recent tuning tasks" in text
            assert "策略上下文" not in text
        finally:
            set_request_lang("zh-CN")  # 测完恢复，避免影响后续用例

    def test_zh_context_markers(self):
        from src.agent.context import build_strategy_context
        sid = _ctx_strategy()
        _seed_run(sid)  # 模块内缓存幂等，确保本会话内数据存在
        _seed_tuning(sid)
        text = build_strategy_context(sid)
        assert "策略上下文" in text
        assert "- 名称:" in text
        assert "最近回测" in text
        assert "最近调优任务" in text


# ---------------------------------------------------------------------------
# with_strategy_context：消息注入位置
# ---------------------------------------------------------------------------
class TestWithStrategyContext:
    def _messages(self):
        return [SystemMessage(content="sys"),
                HumanMessage(content="第一问"),
                AIMessage(content="第一答"),
                HumanMessage(content="第二问")]

    def test_inserts_system_before_last_human(self):
        """上下文 SystemMessage 紧贴最后一条用户消息之前，原有消息对象原样保留。"""
        from src.agent.context import build_strategy_context, with_strategy_context
        sid = _ctx_strategy()
        msgs = self._messages()
        out = with_strategy_context(msgs, sid)
        assert len(out) == len(msgs) + 1
        assert isinstance(out[3], SystemMessage)  # 插在最后一条 HumanMessage（index 3）之前
        assert out[3].content == build_strategy_context(sid)
        assert out[4] is msgs[3]  # 最后一条用户消息仍紧随其后
        assert out[0] is msgs[0] and out[1] is msgs[1] and out[2] is msgs[2]

    def test_none_id_returns_original_list(self):
        from src.agent.context import with_strategy_context
        msgs = self._messages()
        assert with_strategy_context(msgs, None) is msgs

    def test_missing_strategy_returns_original_list(self):
        """策略不存在 → 静默跳过，返回原列表（同一对象）。"""
        from src.agent.context import with_strategy_context
        msgs = self._messages()
        assert with_strategy_context(msgs, 999999) is msgs


# ---------------------------------------------------------------------------
# 工具：update_strategy（回归：函数内 import json as _json 曾遮蔽模块级 _json 助手，
# 导致工具在最终 return _json(result) 处必然 TypeError——修复后此处真实落库验证）
# ---------------------------------------------------------------------------
class TestUpdateStrategyTool:
    def test_update_description_and_params_real_db(self):
        from src.agent import tools
        sid = _ctx_strategy()
        raw = tools.update_strategy.invoke({
            "strategy_id": sid, "description": "P4 更新后的描述",
            "params": '{"window": 25}',
        })
        data = json.loads(raw)
        assert data.get("updated") is True and data["id"] == sid
        detail = lib.get_strategy_detail(sid)
        assert detail["description"] == "P4 更新后的描述"
        assert detail["params"]["window"] == 25  # 生效参数以 DB 列为真相
        assert len(lib.list_versions(sid)) == 1  # 更新前自动快照版本


# ---------------------------------------------------------------------------
# 工具：create_tuning_task / get_tuning_status（monkeypatch 服务层）
# ---------------------------------------------------------------------------
class TestTuningTools:
    def test_create_task_passthrough_and_note(self, monkeypatch):
        """服务层返回值原样透出并补 note；payload 传参（含 param_grid 反序列化）正确。"""
        from src.agent import tools
        captured = {}

        def fake_create(payload):
            captured.update(payload)
            return {"id": 7, "status": "queued", "total_combos": 5}

        monkeypatch.setattr("src.services.tuning.create_tuning_task", fake_create)
        raw = tools.create_tuning_task.invoke({
            "strategy_kind": "code", "strategy_id": 3,
            "stock_code": "000001", "start_date": "2024-01-01", "end_date": "2024-03-31",
            "param_grid": '{"window": [5, 10]}',
        })
        data = json.loads(raw)
        assert data["id"] == 7
        assert data["total_combos"] == 5
        assert "note" in data and "7" in data["note"]  # note 提示用 task_id=7 轮询
        assert captured["strategy_id"] == 3
        assert captured["param_grid"] == {"window": [5, 10]}  # JSON 串已反序列化为网格对象
        assert captured["target_metric"] == "总收益率"  # 缺省目标指标

    def test_create_task_bad_grid_json(self, monkeypatch):
        """param_grid 非法 JSON → {"error": ...}，不抛异常给 agent。"""
        from src.agent import tools
        monkeypatch.setattr(
            "src.services.tuning.create_tuning_task",
            lambda payload: pytest.fail("grid 解析失败时不应触达服务层"))
        raw = tools.create_tuning_task.invoke({
            "strategy_kind": "code", "strategy_id": 3,
            "stock_code": "000001", "start_date": "2024-01-01", "end_date": "2024-03-31",
            "param_grid": "{not json",
        })
        data = json.loads(raw)
        assert "error" in data
        assert "参数网格" in data["error"]

    def test_status_mapping_strips_series(self, monkeypatch):
        """任务 dict → 组合行只含摘要指标；净值/日期序列被剥除；best_combo 映射正确。"""
        from src.agent import tools
        detail = {
            "id": 42, "status": "succeeded",
            "strategy_kind": "code", "strategy_name": "P4-上下文策略",
            "stock_code": "000001", "market": "zh_a",
            "start_date": "2024-01-01", "end_date": "2024-03-31",
            "target_metric": "夏普比率", "total_combos": 3,
            "done_combos": 3, "succeeded_combos": 2, "best_combo_index": 2,
            "error": None,
            "combos": [
                {"combo_index": 0, "is_baseline": True, "status": "succeeded",
                 "params": {"window": 15},
                 "metrics": {"总收益率": 0.1, "夏普比率": 1.1, "最大回撤": -0.2},
                 "equity_curve": [1.0, 2.0], "dates": ["2024-01-02"]},  # 服务层含序列，应被剥除
                {"combo_index": 1, "is_baseline": False, "status": "failed",
                 "params": {"window": 5}, "metrics": {}, "error": "组合失败(window=5)"},
                {"combo_index": 2, "is_baseline": False, "status": "succeeded",
                 "params": {"window": 30},
                 "metrics": {"总收益率": 0.3, "夏普比率": 2.5, "最大回撤": -0.1}},
            ],
        }
        monkeypatch.setattr("src.services.tuning.get_tuning_detail",
                            lambda task_id, include_series=True: detail)
        raw = tools.get_tuning_status.invoke({"task_id": 42})
        data = json.loads(raw)
        assert data.get("error") is None  # 成功任务的 error 字段为 null
        assert data["target_metric"] == "夏普比率"
        # 组合行：目标指标键在行内，序列类字段不出现
        row0 = data["combos"][0]
        assert row0["夏普比率"] == 1.1
        assert row0["is_baseline"] is True
        assert "equity_curve" not in row0 and "dates" not in row0
        assert all("equity" not in k for k in data)
        # 失败组合透出 error
        assert "error" in data["combos"][1] and "组合失败" in data["combos"][1]["error"]
        # best_combo 映射（combo_index=2 → window=30 / 夏普 2.5）
        assert data["best_combo"]["combo_index"] == 2
        assert data["best_combo"]["params"] == {"window": 30}
        assert data["best_combo"]["夏普比率"] == 2.5

    def test_status_missing_task_error(self, monkeypatch):
        """detail 为 None → error 含「调优任务不存在」。"""
        from src.agent import tools
        monkeypatch.setattr("src.services.tuning.get_tuning_detail",
                            lambda task_id, include_series=True: None)
        data = json.loads(tools.get_tuning_status.invoke({"task_id": 999999}))
        assert "调优任务不存在" in data["error"]


# ---------------------------------------------------------------------------
# 工具：list_backtest_runs / get_run（monkeypatch 服务层）
# ---------------------------------------------------------------------------
class TestRunHistoryTools:
    def test_list_runs_summary(self, monkeypatch):
        """列表返回摘要指标；筛选参数透传且 limit 收敛到 50；不含净值序列。"""
        from src.agent import tools
        rows = [{
            "id": 11, "status": "succeeded", "strategy_kind": "code",
            "strategy_name": "P4-上下文策略", "stock_code": "000001", "market": "zh_a",
            "start_date": "2024-01-01", "end_date": "2024-03-31",
            "metrics": {"总收益率": 0.12, "夏普比率": 1.5, "最大回撤": -0.08},
        }]
        captured = {}

        def fake_list_runs(**kw):
            captured.update(kw)
            return rows

        monkeypatch.setattr("src.services.backtest_runs.list_runs", fake_list_runs)
        raw = tools.list_backtest_runs.invoke(
            {"strategy_kind": "code", "strategy_id": 3, "status": "succeeded", "limit": 999})
        data = json.loads(raw)
        assert data["count"] == 1
        run = data["runs"][0]
        assert run["总收益率"] == 0.12 and run["夏普比率"] == 1.5
        assert captured == {"strategy_kind": "code", "strategy_id": 3,
                            "status": "succeeded", "limit": 50}  # 上限收敛
        assert "equity" not in raw  # 摘要不含净值序列

    def test_get_run_detail_no_series(self, monkeypatch):
        """详情返回指标/阶段/成交笔数，但不含净值与成交明细序列本身。"""
        from src.agent import tools
        detail = {
            "id": 9, "status": "succeeded", "strategy_kind": "code",
            "strategy_name": "P4-上下文策略", "stock_code": "000001", "market": "zh_a",
            "start_date": "2024-01-01", "end_date": "2024-03-31",
            "metrics": {"总收益率": 0.12, "夏普比率": 1.5},
            "stages": [{"stage": "fetch", "ms": 10}],
            "trades": [{"date": "2024-01-02", "side": "buy"},
                       {"date": "2024-01-05", "side": "sell"}],
            "error": None,
            "equity_curve": [100000.0, 112000.0],  # 服务层含序列，应被剥除
        }
        monkeypatch.setattr("src.services.backtest_runs.get_run_detail", lambda run_id: detail)
        raw = tools.get_run.invoke({"run_id": 9})
        data = json.loads(raw)
        assert data.get("error") is None  # 成功运行的 error 字段为 null
        assert data["trade_count"] == 2  # 只给笔数
        assert data["metrics"]["总收益率"] == 0.12
        assert "params" not in data  # runs 表无参数列，工具不输出该死键
        assert "equity_curve" not in data  # 净值序列不出现

    def test_get_run_missing_error(self, monkeypatch):
        """运行记录不存在 → error 含「运行记录不存在」。"""
        from src.agent import tools
        monkeypatch.setattr("src.services.backtest_runs.get_run_detail", lambda run_id: None)
        data = json.loads(tools.get_run.invoke({"run_id": 999999}))
        assert "运行记录不存在" in data["error"]


# ---------------------------------------------------------------------------
# 工具：list_factors / create_factor / analyze_factor
# ---------------------------------------------------------------------------
class TestFactorTools:
    def test_list_factors_passthrough(self, monkeypatch):
        from src.agent import tools
        rows = [{"id": 1, "name": "动量20", "market": "zh_a", "description": "20 日动量"}]
        captured = {}

        def fake_list(**kw):
            captured.update(kw)
            return rows

        monkeypatch.setattr("src.services.factor_library.list_factors", fake_list)
        raw = tools.list_factors.invoke({"q": "动量"})
        data = json.loads(raw)
        assert data["count"] == 1
        assert data["factors"][0]["name"] == "动量20"
        assert captured["q"] == "动量"

    def test_create_factor_real_db(self):
        """tmp DB 下真实创建合法 compute 源码 → 返回 id 且详情可查（名称避开会被过滤的连字符）。"""
        from src.agent import tools
        raw = tools.create_factor.invoke({
            "name": "P4工具动量因子", "description": "agent 工具创建的动量因子",
            "source": FACTOR_SOURCE,
        })
        data = json.loads(raw)
        assert "error" not in data
        assert isinstance(data["id"], int) and data["id"] > 0
        detail = flib.get_factor_detail(data["id"])
        assert detail["name"] == "P4工具动量因子"
        assert "compute" in detail["source"]

    def test_create_factor_malicious_source_rejected(self):
        """恶意源码（import os）→ {"error": ...}，不落库。"""
        from src.agent import tools
        raw = tools.create_factor.invoke({
            "name": "P4恶意因子", "description": "", "source": "import os\n" + FACTOR_SOURCE,
        })
        data = json.loads(raw)
        assert "error" in data
        assert store.get_factor_row_by_name("P4恶意因子") is None

    def test_analyze_factor_error_passthrough(self, monkeypatch):
        """分析服务返回 error 键 → 工具输出 error，不吞掉。"""
        from src.agent import tools
        monkeypatch.setattr(
            "src.services.factor_library.analyze_user_factor",
            lambda *a, **k: {"error": "因子分析失败: 数据不可用"})
        data = json.loads(tools.analyze_factor.invoke(
            {"factor_id": 1, "start_date": "2024-01-01", "end_date": "2024-12-31"}))
        assert "因子分析失败" in data["error"]

    def test_analyze_factor_summary_strips_series(self, monkeypatch):
        """正常分析 → 输出 ic_stats 与 note，但 ic_series / 分层净值等序列被剥除。"""
        from src.agent import tools
        result = {
            "factor_type": "动量20", "universe_size": 6,
            "ic_stats": {"ic_mean": 0.42, "ic_ir": 1.1, "ic_win_rate": 0.6},
            "monotonicity": "monotonic",
            "quantile_stats": [{"quantile": 1, "mean_return": 0.01}],
            "ic_series": [0.1, 0.2, 0.3],           # 服务层含序列，应被剥除
            "quantile_cumreturns": [[1.0, 1.1]],
            "quantile_labels": ["Q1", "Q2"],
        }
        captured = {}

        def fake_analyze(factor_id, start_date, end_date, **kw):
            captured.update({"factor_id": factor_id, "start_date": start_date,
                             "end_date": end_date, **kw})
            return result

        monkeypatch.setattr("src.services.factor_library.analyze_user_factor", fake_analyze)
        raw = tools.analyze_factor.invoke(
            {"factor_id": 5, "start_date": "2024-01-01", "end_date": "2024-06-30",
             "n_quantiles": 3})
        data = json.loads(raw)
        assert "error" not in data
        assert data["ic_stats"]["ic_mean"] == 0.42
        assert data["monotonicity"] == "monotonic"
        assert "note" in data
        assert "ic_series" not in data and "ic_series" not in raw
        assert "quantile_cum" not in raw
        assert captured["factor_id"] == 5 and captured["n_quantiles"] == 3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
