"""src/store/db.py 业务存储层测试。

策略库（代码策略）CRUD、回测运行状态机、重启清扫、压缩时序回读。
通过 QDT_STORE_DB_PATH 指向临时库，与开发/生产数据完全隔离。
"""
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_TMPDIR = tempfile.mkdtemp(prefix="emoqunt_store_test_")

from src.store import db as store  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def _isolated_db():
    # 环境变量在 fixture 内设置（运行期），并用 reset_for_tests 丢弃其它模块的线程连接
    os.environ["QDT_STORE_DB_PATH"] = os.path.join(_TMPDIR, "test_store.db")
    store.reset_for_tests()
    store.init_db()
    yield
    store.reset_for_tests()


SOURCE_A = "STRATEGY_PARAMS = {\"n\": 10}\n\ndef initialize(context):\n    pass\n\n\ndef handle_data(context, data):\n    pass\n"


def test_init_db_idempotent():
    store.init_db()
    store.init_db()  # 二次调用不抛异常
    conn = store.get_conn()
    tables = {r["name"] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    assert {"strategies", "backtest_runs", "strategy_versions"} <= tables


def test_strategy_crud_roundtrip():
    sid = store.insert_strategy("t策略甲", "zh_a", "描述", SOURCE_A, {"n": 10}, tags="趋势")
    row = store.get_strategy_row(sid)
    assert row is not None and row["name"] == "t策略甲"
    assert store.get_strategy_row_by_name("t策略甲")["id"] == sid

    assert store.update_strategy_row(sid, {"description": "新描述", "params_json": "{\"n\": 20}"})
    assert store.get_strategy_row(sid)["description"] == "新描述"

    names = [r["name"] for r in store.list_strategy_rows(q="策略甲")]
    assert "t策略甲" in names

    assert store.delete_strategy_row(sid)
    assert store.get_strategy_row(sid) is None


def test_run_lifecycle_and_conditional_updates():
    params = {"strategy_name": "s", "stock_code": "000001", "start_date": "2024-01-02",
              "end_date": "2024-03-01", "initial_capital": 100000.0,
              "commission_rate": 0.0003, "market": "zh_a"}
    run_id = store.create_run(params, strategy_kind="code", strategy_id=7)

    # queued → running（只允许一次）
    store.set_run_running(run_id)
    assert store.get_run_row(run_id)["status"] == "running"

    # 失败（超时看门狗路径）后，迟到的成功结果不得覆盖 failed
    store.fail_run_if_active(run_id, "回测超时")
    assert store.get_run_row(run_id)["status"] == "failed"
    store.finish_run_if_active(run_id, {"总收益率": 0.1}, ["2024-01-02"], [100000.0],
                               [], [{"stage": "backtest", "ms": 5}], 12)
    assert store.get_run_row(run_id)["status"] == "failed"

    # 正常路径：queued → running → succeeded
    run_id2 = store.create_run(params)
    store.set_run_running(run_id2)
    store.finish_run_if_active(run_id2, {"总收益率": 0.1}, ["2024-01-02", "2024-01-03"],
                               [100000.0, 101000.0], [{"date": "2024-01-02"}],
                               [{"stage": "fetch_data", "ms": 3}], 20)
    detail = store.row_to_run_dict(store.get_run_row(run_id2), unpack_series=True)
    assert detail["status"] == "succeeded"
    assert detail["equity_curve"] == [100000.0, 101000.0]
    assert detail["stages"][0]["stage"] == "fetch_data"


def test_restart_sweep_marks_active_runs_failed():
    params = {"strategy_name": "s", "stock_code": "000001", "start_date": "2024-01-02",
              "end_date": "2024-03-01", "initial_capital": 100000.0,
              "commission_rate": 0.0003, "market": "zh_a"}
    queued = store.create_run(params)
    running = store.create_run(params)
    store.set_run_running(running)
    succeeded = store.create_run(params)
    store.set_run_running(succeeded)
    store.finish_run_if_active(succeeded, {}, [], [], [], [], 1)

    # 模拟重启：复位初始化标记后再 init_db 触发清扫
    store._initialized = False
    store.init_db()

    assert store.get_run_row(queued)["status"] == "failed"
    assert store.get_run_row(running)["status"] == "failed"
    assert store.get_run_row(succeeded)["status"] == "succeeded"


def test_pack_unpack_series_roundtrip():
    values = [100000.0 + i * 1.5 for i in range(500)]
    packed = store._pack_series(values)
    assert isinstance(packed, str) and len(packed) < len(str(values))
    assert store._unpack_series(packed) == values
