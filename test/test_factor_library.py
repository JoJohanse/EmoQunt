"""src/services/factor_library.py 因子库服务测试（v2 方案 D5）。

CRUD/版本、compute 源码校验（含恶意代码拦截）、编译执行契约、
zh_a 限定、分析管线接线（合成面板离线跑通 IC/分层）。
使用独立临时库（与 test_store_db 同款隔离模式）。
"""
import os
import sys
import tempfile

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_TMPDIR = tempfile.mkdtemp(prefix="emoqunt_factorlib_test_")

from src.store import db as store  # noqa: E402
from src.services import factor_library as flib  # noqa: E402

MOMENTUM = '''import pandas as pd

FACTOR_PARAMS = {"window": 20}


def compute(df):
    """动量因子：过去 window 日收益率。"""
    window = int(FACTOR_PARAMS.get("window", 20))
    close = pd.to_numeric(df["收盘"], errors="coerce")
    return close.pct_change(window).dropna()
'''

BAD_IMPORT = "import os\n" + MOMENTUM
BAD_EVAL = MOMENTUM.replace("window = int(FACTOR_PARAMS.get(\"window\", 20))",
                            "x = eval('1+1')")
BAD_WILDCARD = "from pandas import *\n" + MOMENTUM
MISSING_COMPUTE = "import pandas as pd\n\nX = 1\n"
BAD_RETURN = MOMENTUM.replace(
    "return close.pct_change(window).dropna()",
    "return list(close.pct_change(window).dropna())")


@pytest.fixture(scope="module", autouse=True)
def _isolated_db():
    os.environ["QDT_STORE_DB_PATH"] = os.path.join(_TMPDIR, "test_factorlib.db")
    store.reset_for_tests()
    store.init_db()
    yield
    store.reset_for_tests()


# ---------------------------------------------------------------------------
# 源码校验（恶意/错误代码拦截）
# ---------------------------------------------------------------------------
class TestValidateSource:
    def test_valid_momentum_ok(self):
        result = flib.validate_factor_source(MOMENTUM)
        assert result["ok"] is True and result["errors"] == []

    def test_banned_import_blocked(self):
        assert flib.validate_factor_source(BAD_IMPORT)["ok"] is False

    def test_banned_eval_blocked(self):
        assert flib.validate_factor_source(BAD_EVAL)["ok"] is False

    def test_wildcard_import_blocked(self):
        assert flib.validate_factor_source(BAD_WILDCARD)["ok"] is False

    def test_missing_compute_blocked(self):
        result = flib.validate_factor_source(MISSING_COMPUTE)
        assert result["ok"] is False and any("compute" in e for e in result["errors"])

    def test_empty_source_factor_wording(self):
        result = flib.validate_factor_source("")
        assert result["ok"] is False and "因子代码" in result["errors"][0]

    def test_open_blocked(self):
        bad = MOMENTUM.replace('window = int(FACTOR_PARAMS.get("window", 20))',
                               "f = open('x.txt')")
        assert flib.validate_factor_source(bad)["ok"] is False


# ---------------------------------------------------------------------------
# 编译与执行契约
# ---------------------------------------------------------------------------
def _synth_ohlcv(days: int = 120, drift: float = 0.001) -> pd.DataFrame:
    idx = pd.date_range("2024-01-01", periods=days, freq="B")
    close = 100 * (1 + drift) ** np.arange(days)
    return pd.DataFrame(
        {"开盘": close, "最高": close * 1.01, "最低": close * 0.99,
         "收盘": close, "成交量": 1_000_000.0},
        index=idx,
    )


class TestCompileAndRun:
    def test_momentum_returns_series(self):
        compute = flib.compile_factor(MOMENTUM)
        out = flib.run_compute(compute, _synth_ohlcv())
        assert isinstance(out, pd.Series) and len(out) == 100  # 120 - 20 窗口

    def test_bad_return_type(self):
        compute = flib.compile_factor(BAD_RETURN)
        with pytest.raises(ValueError, match="pandas Series"):
            flib.run_compute(compute, _synth_ohlcv())

    def test_runtime_error_localized(self):
        bad = MOMENTUM.replace('df["收盘"]', 'df["不存在的列"]')
        compute = flib.compile_factor(bad)
        with pytest.raises(ValueError, match="因子计算失败"):
            flib.run_compute(compute, _synth_ohlcv())

    def test_empty_result_rejected(self):
        bad = MOMENTUM.replace("close.pct_change(window).dropna()",
                               "close.pct_change(999).dropna()")
        compute = flib.compile_factor(bad)
        with pytest.raises(ValueError, match="全为空"):
            flib.run_compute(compute, _synth_ohlcv())

    def test_non_date_index_rejected(self):
        bad = MOMENTUM.replace(
            "return close.pct_change(window).dropna()",
            "return close.pct_change(window).dropna().reset_index(drop=True)")
        compute = flib.compile_factor(bad)
        with pytest.raises(ValueError, match="索引"):
            flib.run_compute(compute, _synth_ohlcv())


# ---------------------------------------------------------------------------
# CRUD 与版本
# ---------------------------------------------------------------------------
class TestCrud:
    def test_create_and_roundtrip(self):
        created = flib.create_factor("动量20", "20 日动量", "zh_a", MOMENTUM, "动量")
        detail = flib.get_factor_detail(created["id"])
        assert detail["source"] == MOMENTUM
        assert detail["market"] == "zh_a"
        listed = flib.list_factors()
        assert all("source" not in f for f in listed)
        assert any(f["id"] == created["id"] for f in listed)

    def test_duplicate_name_rejected(self):
        flib.create_factor("重复名因子", "", "zh_a", MOMENTUM)
        with pytest.raises(ValueError, match="已存在"):
            flib.create_factor("重复名因子", "", "zh_a", MOMENTUM)

    def test_us_market_rejected(self):
        with pytest.raises(ValueError, match="A 股"):
            flib.create_factor("美股因子", "", "us", MOMENTUM)

    def test_name_validation(self):
        with pytest.raises(ValueError, match="不能为空"):
            flib.create_factor("", "", "zh_a", MOMENTUM)
        with pytest.raises(ValueError, match="少于"):
            flib.create_factor("x", "", "zh_a", MOMENTUM)

    def test_invalid_source_rejected_on_create(self):
        with pytest.raises(ValueError):
            flib.create_factor("坏源码因子", "", "zh_a", BAD_IMPORT)

    def test_update_snapshots_version_and_restore(self):
        created = flib.create_factor("版本因子", "", "zh_a", MOMENTUM)
        changed = MOMENTUM.replace('"window": 20', '"window": 10')
        flib.update_factor(created["id"], source=changed, note="窗口改 10")
        detail = flib.get_factor_detail(created["id"])
        assert '"window": 10' in detail["source"]
        versions = flib.list_versions(created["id"])
        assert len(versions) == 1 and versions[0]["note"] == "窗口改 10"
        restored = flib.restore_version(created["id"], versions[0]["id"])
        assert restored["restored_from"] == versions[0]["id"]
        detail = flib.get_factor_detail(created["id"])
        assert '"window": 20' in detail["source"]  # 回滚到旧源码
        # 更新快照 + 回滚前快照
        assert len(flib.list_versions(created["id"])) == 2

    def test_delete_snapshots(self):
        created = flib.create_factor("删除因子", "", "zh_a", MOMENTUM)
        flib.delete_factor(created["id"])
        assert flib.get_factor_detail(created["id"]) is None

    def test_not_found(self):
        with pytest.raises(ValueError, match="不存在"):
            flib.update_factor(999999, description="x")
        assert flib.get_factor_detail(999999) is None


# ---------------------------------------------------------------------------
# 分析管线接线（合成面板离线跑通）
# ---------------------------------------------------------------------------
def _patch_universe(monkeypatch, n_stocks: int = 6, days: int = 150):
    """合成 n 只横截面股票：drift 随 i 递增 → 动量与前瞻收益强正相关。"""
    idx = pd.date_range("2024-01-01", periods=days, freq="B")

    def fake_fetch(code, start_date, end_date):
        i = int(code)
        close = 100 * (1 + 0.0008 * i) ** np.arange(days)
        return pd.DataFrame(
            {"开盘": close, "最高": close, "最低": close,
             "收盘": close, "成交量": 1e6}, index=idx,
        )

    from src.data import data_manager
    from src.services import factor as fservices

    monkeypatch.setattr(data_manager, "get_hs300_stocks", lambda: [str(i) for i in range(n_stocks)])
    monkeypatch.setattr(fservices, "_fetch_one", fake_fetch)


class TestAnalyze:
    def test_analyze_user_factor_offline(self, monkeypatch):
        _patch_universe(monkeypatch, n_stocks=6, days=150)
        created = flib.create_factor("动量分析因子", "", "zh_a", MOMENTUM)
        result = flib.analyze_user_factor(created["id"], "2024-01-01", "2024-12-31",
                                          n_quantiles=3, forward_period=5)
        assert "error" not in result, result.get("error")
        assert result["factor_type"] == "动量分析因子"
        assert result["universe_size"] == 6
        assert result["ic_stats"]["ic_mean"] is not None
        assert len(result["ic_series"]) > 0
        assert len(result["quantile_stats"]) == 3
        assert len(result["quantile_cumreturns"]) > 0
        assert len(result["quantile_labels"]) == 3
        # drift 递增 → 动量与前瞻收益强正相关，IC 应显著为正
        assert result["ic_stats"]["ic_mean"] > 0.5
        assert "monotonic" in result["monotonicity"]

    def test_analyze_rejects_us_factor(self, monkeypatch):
        created = flib.create_factor("市场限定因子", "", "zh_a", MOMENTUM)
        from src.store import db as store

        store.update_factor_row(created["id"], {"market": "us"})
        with pytest.raises(ValueError, match="A 股"):
            flib.analyze_user_factor(created["id"], "2024-01-01", "2024-12-31")

    def test_analyze_not_found(self):
        with pytest.raises(ValueError, match="不存在"):
            flib.analyze_user_factor(999999, "2024-01-01", "2024-12-31")


# ---------------------------------------------------------------------------
# get_hs300_stocks 前导零回归（P3 E2E 发现：CSV 数值列把 002600 读成 2600）
# ---------------------------------------------------------------------------
class TestHs300Codes:
    def test_codes_zero_padded(self, monkeypatch):
        import pandas as pd
        from src.data import data_manager

        df = pd.DataFrame({"股票代码": [601298, 2600, 1391], "股票简称": ["a", "b", "c"], "行业": ["x"] * 3})
        monkeypatch.setattr(pd, "read_csv", lambda *a, **k: df)
        codes = data_manager.get_hs300_stocks()
        assert codes == ["601298", "002600", "001391"]
