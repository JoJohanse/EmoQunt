# coding=utf-8
"""环境变量载入模块 (src/utils/env.py) 单元测试。

覆盖：
- load_env 幂等性（仅首次实际加载）
- get_env 读取环境变量与默认值
- get_env_bool / get_env_int / get_env_float 的解析与回退

运行：pytest test/test_utils_env.py -v
"""
import os
import sys

import pytest

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)


class TestLoadEnv:
    """load_env 幂等性测试。"""

    def test_load_env_idempotent(self, monkeypatch):
        """重复调用只实际加载一次。"""
        import src.utils.env as env

        calls = {"n": 0}

        def fake_load_dotenv(*args, **kwargs):
            calls["n"] += 1

        monkeypatch.setattr(env, "load_dotenv", fake_load_dotenv)
        monkeypatch.setattr(env, "_loaded", False)

        env.load_env()
        env.load_env()
        env.load_env()

        assert calls["n"] == 1
        assert env._loaded is True

    def test_load_env_with_override_flag(self, monkeypatch):
        """override 参数透传给 load_dotenv。"""
        import src.utils.env as env

        captured = {}

        def fake_load_dotenv(dotenv_path=None, override=False):
            captured["override"] = override

        monkeypatch.setattr(env, "load_dotenv", fake_load_dotenv)
        monkeypatch.setattr(env, "_loaded", False)

        env.load_env(override=True)
        assert captured["override"] is True


class TestGetEnv:
    """get_env 基础读取测试。"""

    def test_returns_env_value(self, monkeypatch):
        import src.utils.env as env

        monkeypatch.setenv("QDT_TEST_GETENV_VALUE", "hello")
        assert env.get_env("QDT_TEST_GETENV_VALUE") == "hello"

    def test_returns_default_when_missing(self, monkeypatch):
        import src.utils.env as env

        monkeypatch.delenv("QDT_TEST_GETENV_MISSING", raising=False)
        assert env.get_env("QDT_TEST_GETENV_MISSING") is None
        assert env.get_env("QDT_TEST_GETENV_MISSING", "fallback") == "fallback"


class TestGetEnvBool:
    """get_env_bool 布尔解析测试。"""

    @pytest.mark.parametrize(
        "val,expected",
        [
            ("true", True), ("TRUE", True), ("True", True),
            ("1", True), ("yes", True), ("on", True),
            ("false", False), ("FALSE", False),
            ("0", False), ("no", False), ("off", False),
            ("maybe", False), ("", False),
        ],
    )
    def test_bool_parsing(self, monkeypatch, val, expected):
        import src.utils.env as env

        monkeypatch.setenv("QDT_TEST_BOOL", val)
        assert env.get_env_bool("QDT_TEST_BOOL") is expected

    def test_default_when_missing(self, monkeypatch):
        import src.utils.env as env

        monkeypatch.delenv("QDT_TEST_BOOL_MISSING", raising=False)
        assert env.get_env_bool("QDT_TEST_BOOL_MISSING", True) is True
        assert env.get_env_bool("QDT_TEST_BOOL_MISSING", False) is False


class TestGetEnvInt:
    """get_env_int 整型解析测试。"""

    @pytest.mark.parametrize("val,expected", [("5", 5), ("-3", -3), ("0", 0), ("  42  ", 42)])
    def test_int_parsing(self, monkeypatch, val, expected):
        import src.utils.env as env

        monkeypatch.setenv("QDT_TEST_INT", val)
        assert env.get_env_int("QDT_TEST_INT") == expected
        assert isinstance(env.get_env_int("QDT_TEST_INT"), int)

    def test_invalid_returns_default(self, monkeypatch):
        import src.utils.env as env

        monkeypatch.setenv("QDT_TEST_INT", "not_a_number")
        assert env.get_env_int("QDT_TEST_INT", 99) == 99

    def test_empty_returns_default(self, monkeypatch):
        import src.utils.env as env

        monkeypatch.setenv("QDT_TEST_INT", "   ")
        assert env.get_env_int("QDT_TEST_INT", 7) == 7

    def test_default_when_missing(self, monkeypatch):
        import src.utils.env as env

        monkeypatch.delenv("QDT_TEST_INT_MISSING", raising=False)
        assert env.get_env_int("QDT_TEST_INT_MISSING", 42) == 42


class TestGetEnvFloat:
    """get_env_float 浮点解析测试。"""

    @pytest.mark.parametrize("val,expected", [("3.14", 3.14), ("-0.5", -0.5), ("10", 10.0)])
    def test_float_parsing(self, monkeypatch, val, expected):
        import src.utils.env as env

        monkeypatch.setenv("QDT_TEST_FLOAT", val)
        assert env.get_env_float("QDT_TEST_FLOAT") == pytest.approx(expected)
        assert isinstance(env.get_env_float("QDT_TEST_FLOAT"), float)

    def test_invalid_returns_default(self, monkeypatch):
        import src.utils.env as env

        monkeypatch.setenv("QDT_TEST_FLOAT", "nan_str")
        assert env.get_env_float("QDT_TEST_FLOAT", 1.5) == 1.5

    def test_default_when_missing(self, monkeypatch):
        import src.utils.env as env

        monkeypatch.delenv("QDT_TEST_FLOAT_MISSING", raising=False)
        assert env.get_env_float("QDT_TEST_FLOAT_MISSING", 2.5) == 2.5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
