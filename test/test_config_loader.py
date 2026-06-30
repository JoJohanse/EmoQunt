# coding=utf-8
"""配置加载器模块 (config/config_loader.py) 单元测试。

覆盖：
- 配置文件缺失时回退默认配置
- get 点号路径访问与默认值
- set 嵌套设置与读取
- _parse_env_value 类型解析（布尔/整型/浮点/JSON/字符串）
- 环境变量覆盖（QDT_ 前缀）
- save_config 读写回环
- load_sentiment_config / load_scoring_config 默认配置

为避免污染全局单例与真实 .env，测试均直接实例化 ConfigLoader，
并使用独立的 env_prefix 防止环境变量冲突。

运行：pytest test/test_config_loader.py -v
"""
import os
import sys

import pytest
import yaml

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from config.config_loader import ConfigLoader


@pytest.fixture
def loader(tmp_path):
    """一个使用临时（不存在）配置路径的 ConfigLoader，加载默认配置。"""
    return ConfigLoader(
        config_path=str(tmp_path / "nonexistent.yaml"),
        env_prefix="QDTTESTCFG_",
    )


class TestLoadConfig:
    """配置加载测试。"""

    def test_default_config_when_file_missing(self, loader):
        # 默认配置包含预期的顶层键
        assert loader.get("data.default_market") == "zh_a"
        assert loader.get("backtest.initial_capital") == 100000.0
        assert loader.get("strategy.min_order_size") == 100

    def test_default_config_has_all_sections(self, loader):
        sections = loader.config_data.keys()
        for s in ["data", "strategy", "backtest", "risk_management",
                  "factor", "api", "logging", "environment"]:
            assert s in sections

    def test_load_real_yaml(self, tmp_path):
        cfg = {"data": {"storage_path": "/custom", "default_market": "us"}}
        p = tmp_path / "c.yaml"
        with open(p, "w", encoding="utf-8") as f:
            yaml.dump(cfg, f, allow_unicode=True)
        cl = ConfigLoader(config_path=str(p), env_prefix="QDTTESTREAL_")
        assert cl.get("data.storage_path") == "/custom"
        assert cl.get("data.default_market") == "us"


class TestGetSet:
    """get / set 测试。"""

    def test_get_missing_returns_default(self, loader):
        assert loader.get("nonexistent.key", "fallback") == "fallback"
        assert loader.get("a.b.c.d") is None

    def test_set_and_get(self, loader):
        loader.set("data.custom", 123)
        assert loader.get("data.custom") == 123

    def test_set_creates_nested_path(self, loader):
        loader.set("new_section.new_key", "value")
        assert loader.get("new_section.new_key") == "value"

    def test_section_accessors(self, loader):
        assert isinstance(loader.get_data_config(), dict)
        assert isinstance(loader.get_strategy_config(), dict)
        assert isinstance(loader.get_backtest_config(), dict)
        assert isinstance(loader.get_risk_management_config(), dict)
        assert isinstance(loader.get_factor_config(), dict)
        assert "zhi_tu" in loader.get_api_config()
        assert isinstance(loader.get_logging_config(), dict)
        assert isinstance(loader.get_environment_config(), dict)


class TestParseEnvValue:
    """_parse_env_value 类型解析测试。"""

    @pytest.mark.parametrize("val,expected", [
        ("true", True), ("TRUE", True), ("1", True), ("yes", True), ("on", True),
        ("false", False), ("FALSE", False), ("0", False), ("no", False), ("off", False),
        ("", False),
    ])
    def test_bool(self, loader, val, expected):
        assert loader._parse_env_value(val) is expected

    @pytest.mark.parametrize("val,expected", [("42", 42), ("-7", -7), ("0", 0)])
    def test_int(self, loader, val, expected):
        assert loader._parse_env_value(val) == expected
        assert isinstance(loader._parse_env_value(val), int)

    @pytest.mark.parametrize("val,expected", [("3.14", 3.14), ("-0.5", -0.5)])
    def test_float(self, loader, val, expected):
        assert loader._parse_env_value(val) == pytest.approx(expected)
        assert isinstance(loader._parse_env_value(val), float)

    def test_json(self, loader):
        assert loader._parse_env_value("[1, 2, 3]") == [1, 2, 3]
        assert loader._parse_env_value('{"a": 1}') == {"a": 1}

    def test_plain_string(self, loader):
        assert loader._parse_env_value("hello world") == "hello world"
        assert loader._parse_env_value("/a/b/c") == "/a/b/c"


class TestEnvOverride:
    """环境变量覆盖测试。"""

    def test_env_var_overrides_config(self, tmp_path, monkeypatch):
        cfg = {"data": {"storage_path": "./orig", "default_market": "zh_a"}}
        p = tmp_path / "c.yaml"
        with open(p, "w", encoding="utf-8") as f:
            yaml.dump(cfg, f, allow_unicode=True)

        cl = ConfigLoader(config_path=str(p), env_prefix="QDTOVR_")
        assert cl.get("data.storage_path") == "./orig"

        monkeypatch.setenv("QDTOVR_DATA_STORAGE_PATH", "/overridden/path")
        cl.reload()
        assert cl.get("data.storage_path") == "/overridden/path"


class TestSaveConfig:
    """save_config 读写回环测试。"""

    def test_save_and_reload(self, tmp_path):
        cl = ConfigLoader(
            config_path=str(tmp_path / "c.yaml"), env_prefix="QDTSAVE_"
        )
        cl.set("data.storage_path", "/saved")
        out = tmp_path / "out.yaml"
        cl.save_config(str(out))

        assert out.exists()
        cl2 = ConfigLoader(config_path=str(out), env_prefix="QDTSAVE2_")
        assert cl2.get("data.storage_path") == "/saved"


class TestSentimentScoringConfig:
    """情感 / 评分配置加载测试（使用默认配置，避免依赖真实文件）。"""

    def test_load_sentiment_config_has_words(self, loader):
        cfg = loader.load_sentiment_config()
        assert "positive_words" in cfg
        assert "negative_words" in cfg
        assert "sentiment_thresholds" in cfg

    def test_load_scoring_config_has_weights(self, loader):
        cfg = loader.load_scoring_config()
        assert "composite_weights" in cfg
        assert "price_change_scoring" in cfg


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
