# coding=utf-8
"""用户策略管理模块 (src/Strategy/strategy_manager.py) 单元测试。

覆盖：
- load_user_strategies：无文件返回空、有文件返回字典
- save_user_strategies：原子写入与读取回环
- save_user_strategy：自动添加标记与更新时间
- get_user_strategy / is_user_strategy / delete_user_strategy

为避免触碰真实 strategies.json，通过 monkeypatch 将 SAVE_DIR 重定向到临时目录。

运行：pytest test/test_strategy_manager.py -v
"""
import os
import sys

import pytest

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import src.Strategy.strategy_manager as sm


@pytest.fixture
def isolated_save_dir(tmp_path, monkeypatch):
    """将 strategy_manager 的 SAVE_DIR 重定向到临时目录。"""
    monkeypatch.setattr(sm, "SAVE_DIR", str(tmp_path))
    return tmp_path


class TestLoadUserStrategies:
    """加载用户策略测试。"""

    def test_empty_when_no_file(self, isolated_save_dir):
        assert sm.load_user_strategies() == {}

    def test_load_existing(self, isolated_save_dir):
        sm.save_user_strategies({"s1": {"template": "sentiment_ma"}})
        loaded = sm.load_user_strategies()
        assert "s1" in loaded
        assert loaded["s1"]["template"] == "sentiment_ma"


class TestSaveUserStrategies:
    """保存全部策略测试。"""

    def test_save_returns_true(self, isolated_save_dir):
        assert sm.save_user_strategies({"a": {"template": "sentiment_ma"}}) is True

    def test_roundtrip_preserves_data(self, isolated_save_dir):
        data = {
            "mystrat": {
                "template": "sentiment_ma",
                "parameters": [{"name": "short_period", "value": 7, "type": "int"}],
            },
        }
        sm.save_user_strategies(data)
        loaded = sm.load_user_strategies()
        assert loaded == data

    def test_overwrites_existing(self, isolated_save_dir):
        sm.save_user_strategies({"a": {"v": 1}})
        sm.save_user_strategies({"b": {"v": 2}})
        loaded = sm.load_user_strategies()
        assert "a" not in loaded
        assert "b" in loaded


class TestSaveUserStrategy:
    """保存单个策略测试。"""

    def test_adds_marker_and_timestamp(self, isolated_save_dir):
        sm.save_user_strategy("s1", {"template": "sentiment_ma"})
        got = sm.get_user_strategy("s1")
        assert got is not None
        assert got[sm.USER_STRATEGY_MARKER] is True
        assert "updated_at" in got

    def test_does_not_mutate_input_dict(self, isolated_save_dir):
        """保存时不应修改调用方传入的字典（内部应做拷贝）。"""
        cfg = {"template": "sentiment_ma"}
        cfg_copy = dict(cfg)
        sm.save_user_strategy("s1", cfg)
        assert sm.USER_STRATEGY_MARKER not in cfg
        assert cfg == cfg_copy


class TestGetAndCheck:
    """获取与判断测试。"""

    def test_get_missing_returns_none(self, isolated_save_dir):
        assert sm.get_user_strategy("nope") is None

    def test_is_user_strategy(self, isolated_save_dir):
        sm.save_user_strategy("s1", {"template": "sentiment_ma"})
        assert sm.is_user_strategy("s1") is True
        assert sm.is_user_strategy("nope") is False


class TestDeleteUserStrategy:
    """删除策略测试。"""

    def test_delete_existing(self, isolated_save_dir):
        sm.save_user_strategy("s1", {"template": "sentiment_ma"})
        assert sm.delete_user_strategy("s1") is True
        assert sm.get_user_strategy("s1") is None

    def test_delete_missing_returns_false(self, isolated_save_dir):
        assert sm.delete_user_strategy("nope") is False


class TestStrategyTemplateAccess:
    """模板访问代理测试。"""

    def test_get_strategy_templates(self):
        templates = sm.get_strategy_templates()
        assert "sentiment_ma" in templates

    def test_get_strategy_template_by_name(self):
        assert sm.get_strategy_template("sentiment_ma") is not None
        assert sm.get_strategy_template("nonexistent") is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
