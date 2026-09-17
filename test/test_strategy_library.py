"""src/services/strategy_library.py 策略库服务测试。

代码策略 CRUD、源码校验集成、版本快照与回滚、按 id/名称解析。
使用独立临时库（与 test_store_db 同款隔离模式）。
"""
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_TMPDIR = tempfile.mkdtemp(prefix="emoqunt_library_test_")

from src.store import db as store  # noqa: E402
from src.services import strategy_library as lib  # noqa: E402

GOOD = '''STRATEGY_PARAMS = {"window": 10}


def initialize(context):
    pass


def handle_data(context, data):
    pass
'''


@pytest.fixture(scope="module", autouse=True)
def _isolated_db():
    os.environ["QDT_STORE_DB_PATH"] = os.path.join(_TMPDIR, "test_library.db")
    store.reset_for_tests()
    store.init_db()
    yield
    store.reset_for_tests()


def test_validate_source_service_shape():
    result = lib.validate_source(GOOD)
    assert result["ok"] is True and result["errors"] == []
    assert result["params"] == {"window": 10}
    bad = lib.validate_source("import os\n" + GOOD)
    assert bad["ok"] is False and bad["errors"]


def test_create_and_get_roundtrip():
    created = lib.create_code_strategy("svc测试策略", "描述", "zh_a", GOOD)
    assert created["id"] > 0
    detail = lib.get_strategy_detail(created["id"])
    assert detail["source"] == GOOD
    assert detail["params"] == {"window": 10}
    assert detail["default_params"] == {"window": 10}
    # 按名称解析（回测核心路径）
    by_name = lib.get_code_strategy(None, "svc测试策略")
    assert by_name["id"] == created["id"]
    by_id = lib.get_code_strategy(created["id"])
    assert by_id["name"] == "svc测试策略"


def test_create_rejects_bad_source_and_duplicate_name():
    with pytest.raises(ValueError):
        lib.create_code_strategy("坏源码策略", "", "zh_a", "import os\n" + GOOD)
    lib.create_code_strategy("重名策略", "", "zh_a", GOOD)
    with pytest.raises(ValueError, match="已存在"):
        lib.create_code_strategy("重名策略", "", "zh_a", GOOD)
    with pytest.raises(ValueError, match="market"):
        lib.create_code_strategy("坏市场策略", "", "hk", GOOD)


def test_update_snapshots_version_and_restore():
    created = lib.create_code_strategy("版本策略", "v1", "zh_a", GOOD)
    sid = created["id"]
    lib.update_code_strategy(sid, source=GOOD.replace("10", "20"), note="改参数")
    versions = lib.list_versions(sid)
    assert len(versions) == 1 and versions[0]["note"] == "改参数"
    # 当前源码已是新版
    assert lib.get_strategy_detail(sid)["source"].find("20") > 0
    # 回滚到快照（旧源码 window=10）
    lib.restore_version(sid, versions[0]["id"])
    restored = lib.get_strategy_detail(sid)
    assert restored["params"] == {"window": 10}
    # 回滚本身也产生快照
    assert len(lib.list_versions(sid)) == 2


def test_update_requires_existing_and_valid_source():
    with pytest.raises(ValueError, match="不存在"):
        lib.update_code_strategy(999999, description="x")
    sid = lib.create_code_strategy("更新校验策略", "", "zh_a", GOOD)["id"]
    with pytest.raises(ValueError):
        lib.update_code_strategy(sid, source="import socket\n" + GOOD)


def test_delete_snapshots_then_removes():
    sid = lib.create_code_strategy("待删策略", "", "zh_a", GOOD)["id"]
    lib.delete_code_strategy(sid)
    assert lib.get_code_strategy(sid) is None
    with pytest.raises(ValueError, match="不存在"):
        lib.list_versions(sid)
