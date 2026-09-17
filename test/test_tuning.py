"""src/services/tuning.py 参数调优服务测试。

网格校验、任务创建（基准 + 笛卡尔积）、并发执行（fake 回测核心）、
最优组合汇总、apply 只写参数、重启清扫、看门狗回调泛化。
使用独立临时库（与 test_store_db 同款隔离模式）。
"""
import os
import sys
import tempfile
import time
from threading import Event

import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_TMPDIR = tempfile.mkdtemp(prefix="emoqunt_tuning_test_")

from src.store import db as store  # noqa: E402
from src.services import strategy_library as lib  # noqa: E402
from src.services import tuning  # noqa: E402
from src.services import task_runner  # noqa: E402

GOOD = '''STRATEGY_PARAMS = {"window": 10, "threshold": 0.5}


def initialize(context):
    pass


def handle_data(context, data):
    pass
'''


@pytest.fixture(scope="module", autouse=True)
def _isolated_db():
    os.environ["QDT_STORE_DB_PATH"] = os.path.join(_TMPDIR, "test_tuning.db")
    store.reset_for_tests()
    store.init_db()
    yield
    store.reset_for_tests()


def _make_strategy(name: str) -> int:
    return lib.create_code_strategy(name, "调优测试", "zh_a", GOOD, {"window": 10, "threshold": 0.5})["id"]


def _payload(strategy_id: int, grid: dict, **kw) -> dict:
    return {
        "strategy_kind": "code",
        "strategy_id": strategy_id,
        "stock_code": "000001",
        "market": "zh_a",
        "start_date": "2024-01-01",
        "end_date": "2024-03-31",
        "param_grid": grid,
        **kw,
    }


def _fake_core_factory(fail_on=None):
    """伪造回测核心：总收益率随 window 线性变化；fail_on 参数值时抛错。"""
    def _fake_core(**kwargs):
        params = kwargs.get("strategy_params") or {}
        if fail_on is not None and params.get("window") in fail_on:
            raise RuntimeError(f"组合失败(.window={params.get('window')})")
        mult = float(params.get("window", 1))
        n = 30
        return {
            "metrics_raw": {"总收益率": 0.01 * mult, "夏普比率": mult, "最大回撤": -0.2},
            "performance_report": None, "risk_report": None,
            "alpha": None, "beta": None, "info_ratio": None,
            "daily_returns": pd.Series([0.001] * n, index=pd.date_range("2024-01-01", periods=n)),
            "equity": pd.Series([100000.0 * (1 + 0.001 * mult * i) for i in range(n)]),
            "stages": [],
        }
    return _fake_core


@pytest.fixture()
def fake_core(monkeypatch):
    """把回测核心替换为 fake（worker 线程共享 module 属性）。"""
    import src.backtest.backtest_manager as bm

    fake = _fake_core_factory()
    monkeypatch.setattr(bm, "_run_backtest_core", fake)
    return fake


def _wait_terminal(task_id: int, timeout: float = 10.0) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        detail = tuning.get_tuning_detail(task_id)
        if detail["status"] in ("succeeded", "failed"):
            return detail
        time.sleep(0.05)
    raise AssertionError(f"任务 {task_id} 未在 {timeout}s 内到达终态")


# ---------------------------------------------------------------------------
# 网格校验
# ---------------------------------------------------------------------------
class TestGridValidation:
    def test_empty_grid_rejected(self):
        with pytest.raises(ValueError):
            tuning._validate_grid({}, {"a": 1})
        with pytest.raises(ValueError):
            tuning._validate_grid(None, {"a": 1})

    def test_unknown_param_rejected(self):
        with pytest.raises(ValueError, match="不在该策略"):
            tuning._validate_grid({"nope": [1]}, {"a": 1})

    def test_empty_values_rejected(self):
        with pytest.raises(ValueError, match="取值列表为空"):
            tuning._validate_grid({"a": []}, {"a": 1})

    def test_too_many_values_rejected(self):
        with pytest.raises(ValueError, match="最多"):
            tuning._validate_grid({"a": list(range(11))}, {"a": 1})

    def test_non_scalar_rejected(self):
        with pytest.raises(ValueError, match="数字或布尔"):
            tuning._validate_grid({"a": ["x"]}, {"a": 1})

    def test_product_over_cap_rejected(self):
        grid = {"a": [1, 2, 3, 4], "b": [1, 2, 3, 4], "c": [1, 2, 3, 4]}  # 64 > 63
        with pytest.raises(ValueError, match="上限"):
            tuning._validate_grid(grid, {"a": 1, "b": 2, "c": 3})

    def test_bool_and_number_ok(self):
        cleaned = tuning._validate_grid({"a": [True, False], "b": [0.1, 0.2]}, {"a": True, "b": 0.1})
        assert cleaned == {"a": [True, False], "b": [0.1, 0.2]}


class TestTargetMetric:
    def test_unknown_metric_rejected(self):
        sid = _make_strategy("调优-指标校验")
        with pytest.raises(ValueError, match="目标指标"):
            tuning.create_tuning_task(_payload(sid, {"window": [5, 10]}, target_metric="不存在的指标"))


# ---------------------------------------------------------------------------
# 创建与执行（fake 核心）
# ---------------------------------------------------------------------------
class TestCreateAndExecute:
    def test_create_builds_baseline_plus_grid(self, fake_core):
        sid = _make_strategy("调优-执行A")
        result = tuning.create_tuning_task(_payload(sid, {"window": [5, 10, 20], "threshold": [0.3, 0.6]}))
        assert result["total_combos"] == 7  # 6 组合 + 1 基准
        detail = _wait_terminal(result["id"])
        assert detail["status"] == "succeeded"
        assert detail["total_combos"] == 7
        assert detail["done_combos"] == 7
        assert detail["succeeded_combos"] == 7
        combos = detail["combos"]
        assert combos[0]["is_baseline"] is True
        assert combos[0]["params"] == {"window": 10, "threshold": 0.5}  # 基准 = 当前生效参数
        assert [c["combo_index"] for c in combos] == list(range(7))
        # 覆盖组合 = 基底 + 网格覆盖
        combo1 = combos[1]
        assert combo1["params"]["threshold"] in (0.3, 0.6)
        assert combo1["params"]["window"] in (5, 10, 20)
        assert combo1["is_baseline"] is False
        # 指标与降采样净值已落库
        assert "总收益率" in combo1["metrics"]
        assert 0 < len(combo1["equity_curve"]) <= tuning.EQUITY_POINTS
        assert len(combo1["dates"]) == len(combo1["equity_curve"])
        # 最优 = window 最大的组合（fake 收益随 window 线性增）
        best = next(c for c in combos if c["combo_index"] == detail["best_combo_index"])
        assert best["params"]["window"] == 20

    def test_partial_failure_still_succeeds_with_best(self, monkeypatch):
        import src.backtest.backtest_manager as bm

        monkeypatch.setattr(bm, "_run_backtest_core", _fake_core_factory(fail_on={5}))
        sid = _make_strategy("调优-部分失败")
        result = tuning.create_tuning_task(_payload(sid, {"window": [5, 10]}))
        detail = _wait_terminal(result["id"])
        assert detail["status"] == "succeeded"
        assert detail["succeeded_combos"] == 2  # window=10 候选 + 基准
        failed = [c for c in detail["combos"] if c["status"] == "failed"]
        assert len(failed) == 1 and "组合失败" in failed[0]["error"]

    def test_all_failed_marks_task_failed(self, monkeypatch):
        import src.backtest.backtest_manager as bm

        def _always_fail(**kwargs):
            raise RuntimeError("全部失败")
        monkeypatch.setattr(bm, "_run_backtest_core", _always_fail)
        sid = _make_strategy("调优-全失败")
        result = tuning.create_tuning_task(_payload(sid, {"window": [7]}))
        detail = _wait_terminal(result["id"])
        assert detail["status"] == "failed"
        assert "均失败" in (detail["error"] or "")

    def test_template_strategy_tuning(self, fake_core):
        """模板策略同样可调优：基准参数来自 build_param_dict。"""
        from src.Strategy.strategy_manager import get_user_strategy

        config = get_user_strategy("test")
        if config is None:
            pytest.skip("本地 strategies.json 无 test 策略")
        payload = _payload(0, {"short_period": [3, 5]})
        payload.pop("strategy_id")
        payload["strategy_kind"] = "template"
        payload["strategy_name"] = "test"
        result = tuning.create_tuning_task(payload)
        detail = _wait_terminal(result["id"])
        assert detail["status"] == "succeeded"
        assert detail["combos"][0]["is_baseline"] is True
        assert "short_period" in detail["combos"][0]["params"]


# ---------------------------------------------------------------------------
# 应用参数（唯一回写入口）
# ---------------------------------------------------------------------------
class TestApply:
    def test_apply_merges_only_grid_keys(self, fake_core):
        sid = _make_strategy("调优-应用")
        result = tuning.create_tuning_task(_payload(sid, {"window": [8, 30]}))
        detail = _wait_terminal(result["id"])
        best = detail["best_combo_index"]
        best_params = next(c["params"] for c in detail["combos"] if c["combo_index"] == best)
        applied = tuning.apply_tuning_params(result["id"], best)
        assert applied["applied_params"] == {"window": best_params["window"]}
        after = lib.get_strategy_detail(sid)
        assert after["params"]["window"] == best_params["window"]
        assert after["params"]["threshold"] == 0.5  # 非网格键不动
        # 应用会经 update_code_strategy 自动快照版本
        versions = lib.list_versions(sid)
        assert any("应用调优组合" in (v["note"] or "") for v in versions)

    def test_apply_rejects_running_task(self):
        sid = _make_strategy("调优-未结束")
        # 直接建行不提交执行，任务稳定处于 queued 态（不依赖执行时序）
        task_id = store.create_tuning_task(
            {
                "strategy_kind": "code", "strategy_id": sid, "strategy_name": "调优-未结束",
                "market": "zh_a", "stock_code": "000001",
                "start_date": "2024-01-01", "end_date": "2024-03-31",
                "initial_capital": 100000.0, "commission_rate": 0.0003,
                "param_grid_json": '{"window": [9]}', "grid_keys_json": '["window"]',
                "target_metric": "总收益率", "target_metric_desc": 1,
            },
            [{"combo_index": 0, "is_baseline": 1, "params": {"window": 10}}],
        )
        with pytest.raises(ValueError, match="尚未结束"):
            tuning.apply_tuning_params(task_id, 0)

    def test_apply_rejects_failed_combo(self, monkeypatch):
        monkeypatch.setattr(
            "src.backtest.backtest_manager._run_backtest_core", _fake_core_factory(fail_on={3}))
        sid = _make_strategy("调优-失败组合应用")
        result = tuning.create_tuning_task(_payload(sid, {"window": [3, 4]}))
        detail = _wait_terminal(result["id"])
        failed_combo = next(c["combo_index"] for c in detail["combos"]
                            if c["status"] == "failed" and not c["is_baseline"])
        with pytest.raises(ValueError, match="未成功完成"):
            tuning.apply_tuning_params(result["id"], failed_combo)

    def test_apply_unknown_task(self):
        with pytest.raises(ValueError, match="不存在"):
            tuning.apply_tuning_params(999999, 0)


# ---------------------------------------------------------------------------
# 重启清扫 + 看门狗
# ---------------------------------------------------------------------------
class TestLifecycle:
    def test_restart_sweep_marks_tuning_failed(self, monkeypatch):
        monkeypatch.setattr(
            "src.backtest.backtest_manager._run_backtest_core", _fake_core_factory())
        sid = _make_strategy("调优-重启清扫")
        result = tuning.create_tuning_task(_payload(sid, {"window": [11]}))
        # 模拟重启：复位初始化标记后重新 init_db（触发清扫）
        store.reset_for_tests()
        store.init_db()
        row = store.get_tuning_task_row(result["id"])
        assert row["status"] == "failed"
        runs = store.list_tuning_run_rows(result["id"])
        assert all(r["status"] == "failed" for r in runs)

    def test_watchdog_custom_abandon_callback(self):
        fired = Event()
        task_runner.submit_task(
            987654321, lambda: time.sleep(0.3), 0.05,
            on_abandon=lambda tid: fired.set(),
        )
        assert fired.wait(2.0), "自定义放弃回调未被触发"

    def test_get_tuning_detail_missing(self):
        assert tuning.get_tuning_detail(999999) is None
