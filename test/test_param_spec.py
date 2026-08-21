"""参数单点解析测试。

覆盖 resolve_param 的 prefer 双向、双缺 fallback，以及
resolve_sentiment_weight 的域封装与 float 转换回退。
"""

import os
import sys

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)


class TestResolveParam:
    def test_prefer_value_returns_value_when_present(self):
        from src.Strategy.param_spec import resolve_param
        assert resolve_param({"value": 7, "default": 3}, fallback=None, prefer="value") == 7

    def test_prefer_value_falls_back_to_default(self):
        from src.Strategy.param_spec import resolve_param
        assert resolve_param({"default": 3}, fallback=None, prefer="value") == 3
        # value 显式为 None 视为缺失，同样回退
        assert resolve_param({"value": None, "default": 3}, fallback=None, prefer="value") == 3

    def test_prefer_value_both_missing_returns_fallback(self):
        from src.Strategy.param_spec import resolve_param
        assert resolve_param({}, fallback=42, prefer="value") == 42
        assert resolve_param({"name": "x"}, fallback="fb", prefer="value") == "fb"
        assert resolve_param({"value": None, "default": None}, fallback=99, prefer="value") == 99

    def test_prefer_value_preserves_falsy_non_none(self):
        from src.Strategy.param_spec import resolve_param
        # 0 / False / "" 均为合法值，不应触发回退
        assert resolve_param({"value": 0, "default": 5}, fallback=99, prefer="value") == 0
        assert resolve_param({"value": False, "default": True}, fallback=None, prefer="value") is False
        assert resolve_param({"value": "", "default": "x"}, fallback="fb", prefer="value") == ""

    def test_prefer_default_returns_default_when_present(self):
        from src.Strategy.param_spec import resolve_param
        assert resolve_param({"value": 7, "default": 3}, fallback=None, prefer="default") == 3

    def test_prefer_default_falls_back_to_value(self):
        from src.Strategy.param_spec import resolve_param
        assert resolve_param({"value": 7}, fallback=None, prefer="default") == 7
        # default 显式为 None 视为缺失，同样回退到 value
        assert resolve_param({"value": 7, "default": None}, fallback=None, prefer="default") == 7

    def test_prefer_default_both_missing_returns_fallback(self):
        from src.Strategy.param_spec import resolve_param
        assert resolve_param({}, fallback=0.3, prefer="default") == 0.3
        assert resolve_param({"value": None, "default": None}, fallback=0.3, prefer="default") == 0.3

    def test_prefer_default_preserves_falsy_non_none(self):
        from src.Strategy.param_spec import resolve_param
        assert resolve_param({"default": 0, "value": 5}, fallback=99, prefer="default") == 0

    def test_non_dict_returns_fallback(self):
        from src.Strategy.param_spec import resolve_param
        assert resolve_param(None, fallback=1, prefer="value") == 1
        assert resolve_param("not a dict", fallback=2, prefer="default") == 2


class TestResolveSentimentWeight:
    def test_default_priority_over_value(self):
        from src.Strategy.param_spec import resolve_sentiment_weight
        params = [{"name": "sentiment_weight", "default": 0.5, "value": 0.8}]
        assert resolve_sentiment_weight(params) == 0.5

    def test_value_fallback_when_default_missing(self):
        from src.Strategy.param_spec import resolve_sentiment_weight
        params = [{"name": "sentiment_weight", "value": 0.8}]
        assert resolve_sentiment_weight(params) == 0.8

    def test_default_only(self):
        from src.Strategy.param_spec import resolve_sentiment_weight
        params = [{"name": "sentiment_weight", "default": 0.6}]
        assert resolve_sentiment_weight(params) == 0.6

    def test_both_missing_returns_0_3(self):
        from src.Strategy.param_spec import resolve_sentiment_weight
        assert resolve_sentiment_weight([]) == 0.3
        assert resolve_sentiment_weight([{"name": "other", "default": 0.9}]) == 0.3
        # sentiment_weight 存在但两者皆缺
        assert resolve_sentiment_weight([{"name": "sentiment_weight"}]) == 0.3

    def test_float_conversion_failure_fallback(self):
        from src.Strategy.param_spec import resolve_sentiment_weight
        assert resolve_sentiment_weight([{"name": "sentiment_weight", "default": "bad"}]) == 0.3
        assert resolve_sentiment_weight([{"name": "sentiment_weight", "default": None, "value": "also-bad"}]) == 0.3
        assert resolve_sentiment_weight([{"name": "sentiment_weight", "default": "not_a_number"}]) == 0.3

    def test_string_numeric_converted(self):
        from src.Strategy.param_spec import resolve_sentiment_weight
        assert resolve_sentiment_weight([{"name": "sentiment_weight", "default": "0.7"}]) == 0.7

    def test_last_match_wins(self):
        from src.Strategy.param_spec import resolve_sentiment_weight
        # 与原 for 循环覆盖语义一致，最后一条生效
        params = [
            {"name": "sentiment_weight", "default": 0.1},
            {"name": "sentiment_weight", "default": 0.9},
        ]
        assert resolve_sentiment_weight(params) == 0.9

    def test_non_list_returns_0_3(self):
        from src.Strategy.param_spec import resolve_sentiment_weight
        assert resolve_sentiment_weight(None) == 0.3
        assert resolve_sentiment_weight("bad") == 0.3

    def test_consistent_with_original_inline_semantics(self):
        """与原 inline 逻辑 default > value > 0.3 保持一致（含 float 容错）。"""
        from src.Strategy.param_spec import resolve_sentiment_weight
        # 原逻辑：float(param.get('default', param.get('value', 0.3)))
        # 以下等价于原逻辑的各种分支，但封装后 float 失败多一层 0.3 兜底
        assert resolve_sentiment_weight([{"name": "sentiment_weight", "default": 0.4, "value": 0.2}]) == 0.4
        assert resolve_sentiment_weight([{"name": "sentiment_weight", "value": 0.2}]) == 0.2
        assert resolve_sentiment_weight([{"name": "sentiment_weight"}]) == 0.3


class TestExtractParamValueDelegation:
    """验证 extract_param_value 仍保持 value 优先语义（委托后行为不变）。"""

    def test_still_value_priority(self):
        from src.Strategy.Strategy import extract_param_value
        assert extract_param_value({"name": "x", "value": 7, "default": 3, "type": "int"}) == ("x", 7)
        assert extract_param_value({"name": "x", "default": 3, "type": "int"}) == ("x", 3)
        assert extract_param_value({"name": "a", "value": "5", "type": "int"}) == ("a", 5)
