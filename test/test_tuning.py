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
    # 默认 oos_ratio=0：既有用例只关心网格语义（90 天区间会被 OOS 最短天数拦下）；
    # OOS 用例经 kw 显式传 ratio
    kw.setdefault("oos_ratio", 0)
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


# ---------------------------------------------------------------------------
# 样本外验证（Round3，对标 freqtrade「IS 优化 + 未触碰 OOS 验证」实践）
# ---------------------------------------------------------------------------
OOS_END = "2024-12-31"


def _oos_fake_core_factory():
    """相位感知 fake：IS 指标 = 100-window（window 越小越优）；
    OOS 指标 = 100-10×|window-8|（样本外峰值在 w8——IS 次优组合，
    IS argmax(w=3) 在样本外塌陷，OOS 复排名应把它顶下来）。"""
    def _fake_core(**kwargs):
        params = kwargs.get("strategy_params") or {}
        window = float(params.get("window", 1))
        is_oos = str(kwargs.get("end_date", "")) == OOS_END
        value = ((100.0 - 10.0 * abs(window - 8.0)) if is_oos
                 else 100.0 - window) / 100.0
        return {
            "metrics_raw": {"总收益率": value, "夏普比率": value, "最大回撤": -0.2},
            "performance_report": None, "risk_report": None,
            "alpha": None, "beta": None, "info_ratio": None,
            "daily_returns": pd.Series([0.001] * 30, index=pd.date_range("2024-01-01", periods=30)),
            "equity": pd.Series([100000.0 * (1 + value * i / 100) for i in range(30)]),
            "stages": [],
        }
    return _fake_core


class TestOosValidation:
    """创建期校验：ratio 合法性、区间最短天数、切分日期。"""

    def test_default_ratio_enabled_and_split(self, fake_core):
        sid = _make_strategy("oos-default")
        detail = _wait_terminal(tuning.create_tuning_task(_payload(
            sid, {"window": [3, 5]},
            start_date="2024-01-01", end_date="2024-12-31",
            # 显式 0.3（helper 对既有用例 setdefault 0）：365×0.7=256 天 → IS 终点 2024-09-13
            oos_ratio=0.3,
        ))["id"])
        assert detail["oos_ratio"] == pytest.approx(0.3)
        assert detail["is_end_date"] == "2024-09-12"  # 2024 闰年：+256 天
        assert detail["status"] == "succeeded"

    def test_ratio_zero_disables(self, fake_core):
        sid = _make_strategy("oos-off")
        detail = _wait_terminal(tuning.create_tuning_task(_payload(
            sid, {"window": [3, 5]},
            start_date="2024-01-01", end_date="2024-12-31", oos_ratio=0,
        ))["id"])
        assert detail["oos_ratio"] == 0.0 and detail["is_end_date"] is None
        assert detail["oos_total"] == 0

    def test_ratio_out_of_range_rejected(self, fake_core):
        sid = _make_strategy("oos-bad-ratio")
        with pytest.raises(ValueError, match="oos_ratio"):
            tuning.create_tuning_task(_payload(
                sid, {"window": [3]}, start_date="2024-01-01",
                end_date="2024-12-31", oos_ratio=0.7))

    def test_short_range_rejected(self, fake_core):
        """90 天区间开 OOS（默认 0.3）应被最短天数拦截。"""
        sid = _make_strategy("oos-short")
        with pytest.raises(ValueError, match="区间过短"):
            tuning.create_tuning_task(_payload(sid, {"window": [3]}, oos_ratio=0.3))


class TestOosExecution:
    """OOS 阶段执行：Top-K+基准复跑、OOS 指标终排名、进度计数。"""

    def test_oos_rerank_beats_in_sample_argmax(self, monkeypatch):
        """IS 最优组合在 OOS 崩掉时，终排名应落到 OOS 最优（过拟合防线生效）。"""
        import src.backtest.backtest_manager as bm
        monkeypatch.setattr(bm, "_run_backtest_core", _oos_fake_core_factory())
        sid = _make_strategy("oos-rerank")
        detail = _wait_terminal(tuning.create_tuning_task(_payload(
            sid,
            {"window": [3, 5, 8, 10, 13, 21]},
            start_date="2024-01-01", end_date=OOS_END,
            # ratio 0.5（上限）：IS/OOS 各半年，OOS 候选含全部高 IS 组合
            oos_ratio=0.5,
        ))["id"])
        assert detail["status"] == "succeeded"
        by_idx = {c["combo_index"]: c for c in detail["combos"]}
        # IS 最优 = w3（combo 1）；OOS 峰值 = w8（combo 3，必在 IS Top-5 内）
        assert detail["best_combo_index"] == 3, "终排名必须按 OOS 指标而非 IS argmax"
        assert by_idx[3]["oos"]["status"] == "succeeded"
        assert by_idx[3]["oos"]["metrics"]["总收益率"] == pytest.approx(1.0)
        assert detail["oos_total"] == len([c for c in detail["combos"] if c.get("oos")])
        assert detail["oos_done"] == detail["oos_total"]

    def test_oos_all_failed_falls_back_to_is(self, monkeypatch):
        """OOS 复跑全失败时回退 IS 排名（可用性优先，任务不 failed）。"""
        import src.backtest.backtest_manager as bm

        def _oos_always_fail(**kwargs):
            if str(kwargs.get("end_date", "")) == OOS_END:
                raise RuntimeError("oos source down")
            return _fake_core_factory()(**kwargs)

        monkeypatch.setattr(bm, "_run_backtest_core", _oos_always_fail)
        sid = _make_strategy("oos-fallback")
        detail = _wait_terminal(tuning.create_tuning_task(_payload(
            sid, {"window": [3, 5]},
            start_date="2024-01-01", end_date=OOS_END, oos_ratio=0.3,
        ))["id"])
        assert detail["status"] == "succeeded"
        # 全部 OOS failed → 回退 IS 最优（_fake_core_factory 指标随 window 递增
        # → IS 最优 = 基准 w10 = combo 0）
        assert detail["best_combo_index"] == 0
        assert all(c["oos"]["status"] == "failed" for c in detail["combos"] if c.get("oos"))
