# coding=utf-8
"""策略模块 (src/Strategy/Strategy.py) 单元测试。

注意：extract_param_value / build_param_dict 已在 test/test_backtest.py 覆盖，
本文件覆盖其余部分：
- TradeRecord 日期类型处理
- TradeRecordManager 转 DataFrame
- StrategyManager 注册 / 获取
- parse_bool 布尔解析
- STRATEGY_TEMPLATES 与模板访问
- create_user_strategy_class 动态生成策略类

运行：pytest test/test_strategy.py -v
"""
import datetime
import os
import sys

import pandas as pd
import pytest

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from src.Strategy.Strategy import (
    TradeRecord,
    TradeRecordManager,
    StrategyManager,
    StrategyBase,
    parse_bool,
    STRATEGY_TEMPLATES,
    get_strategy_template,
    get_all_strategy_templates,
    create_user_strategy_class,
)


class TestTradeRecord:
    """交易记录日期处理测试。"""

    def test_string_date_to_timestamp(self):
        r = TradeRecord(1, "2024-01-01", "B", 10.0, 100, 1000.0, 5.0, "buy", "Completed")
        assert r.date == pd.Timestamp("2024-01-01")
        assert r.action == "B"
        assert r.price == 10.0

    def test_datetime_date_to_timestamp(self):
        r = TradeRecord(1, datetime.date(2024, 1, 1), "S", 10.0, 100, 1000.0, 5.0, "sell", "Completed")
        assert isinstance(r.date, pd.Timestamp)

    def test_invalid_date_type_raises(self):
        with pytest.raises(ValueError):
            TradeRecord(1, 12345, "B", 10.0, 100, 1000.0, 5.0, "buy", "Completed")


class TestTradeRecordManager:
    """交易记录管理器测试。"""

    def test_add_and_transform(self):
        m = TradeRecordManager()
        m.add_trade_record(1, "2024-01-01", "B", 10.0, 100, 1000.0, 5.0, "buy", "Completed")
        m.add_trade_record(2, "2024-01-02", "S", 11.0, 100, 1100.0, 5.0, "sell", "Completed")
        df = m.transform_to_dataframe()
        assert len(df) == 2
        assert list(df["action"]) == ["B", "S"]
        assert set(df.columns) >= {"trade_id", "date", "action", "price", "size"}

    def test_empty_manager_returns_empty_df(self):
        m = TradeRecordManager()
        df = m.transform_to_dataframe()
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 0


class TestStrategyManager:
    """策略管理器注册 / 获取测试。"""

    def test_register_and_get(self):
        sm = StrategyManager()
        class Dummy:
            pass
        sm.register_strategy("dummy", Dummy)
        assert sm.get_strategy("dummy") is Dummy

    def test_get_missing_returns_none(self):
        sm = StrategyManager()
        assert sm.get_strategy("missing") is None

    def test_get_all_strategies(self):
        sm = StrategyManager()
        class A:
            pass
        class B:
            pass
        sm.register_strategy("a", A)
        sm.register_strategy("b", B)
        all_s = sm.get_all_strategies()
        assert all_s["a"] is A
        assert all_s["b"] is B
        assert len(all_s) == 2


class TestParseBool:
    """parse_bool 布尔解析测试。"""

    @pytest.mark.parametrize("val,expected", [
        (True, True), (False, False),
        (1, True), (0, False),
        ("1", True), ("true", True), ("TRUE", True), ("yes", True), ("on", True),
        ("0", False), ("false", False), ("no", False), ("off", False),
        ("maybe", False),
    ])
    def test_parse(self, val, expected):
        assert parse_bool(val) is expected

    def test_none_returns_false(self):
        # 非 bool/int/float/str 走 bool(value) 分支
        assert parse_bool(None) is False


class TestStrategyTemplates:
    """策略模板测试。"""

    def test_sentiment_ma_template_exists(self):
        assert "sentiment_ma" in STRATEGY_TEMPLATES
        t = STRATEGY_TEMPLATES["sentiment_ma"]
        assert "base_params" in t
        assert "name" in t

    def test_get_template(self):
        assert get_strategy_template("sentiment_ma") is not None
        assert get_strategy_template("nonexistent") is None

    def test_get_all_templates(self):
        assert get_all_strategy_templates() is STRATEGY_TEMPLATES

    def test_base_params_have_required_fields(self):
        params = STRATEGY_TEMPLATES["sentiment_ma"]["base_params"]
        names = {p["name"] for p in params}
        # 关键参数齐全
        assert {"short_period", "long_period", "sentiment_threshold",
                "use_sentiment_filter"} <= names
        # 每个参数都有 name/default/type
        for p in params:
            assert "name" in p and "type" in p and "default" in p


class TestCreateUserStrategyClass:
    """动态策略类生成测试。"""

    def test_returns_subclass_of_strategy_base(self):
        cls = create_user_strategy_class({"template": "sentiment_ma", "parameters": []})
        assert isinstance(cls, type)
        assert issubclass(cls, StrategyBase)

    def test_params_from_user_config_override_template(self):
        cfg = {
            "template": "sentiment_ma",
            "parameters": [
                {"name": "short_period", "value": 7, "type": "int"},
                {"name": "long_period", "value": 30, "type": "int"},
            ],
        }
        cls = create_user_strategy_class(cfg)
        # backtrader 将 params 元组编译为参数类，通过 _getpairs() 取 (name, value)
        p = dict(cls.params._getpairs())
        assert p["short_period"] == 7
        assert p["long_period"] == 30
        # 未覆盖的模板默认值保留
        assert p["use_sentiment_filter"] is True
        assert p["max_portfolio_percent"] == 0.8

    def test_no_sentiment_data_disables_filter(self):
        """未传入情绪数据时，策略类仍可生成（回退为关闭过滤）。"""
        cls = create_user_strategy_class(
            {"template": "sentiment_ma", "parameters": []},
            sentiment_series=None,
            sentiment_sector=None,
        )
        assert issubclass(cls, StrategyBase)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
