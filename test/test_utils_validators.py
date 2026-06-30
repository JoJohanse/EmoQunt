# coding=utf-8
"""输入验证模块 (src/utils/validators.py) 单元测试。

注意：股票代码路由 / 美股校验 / 回测参数透传已在 test/test_backtest.py 覆盖，
本文件聚焦其余校验器：日期、日期范围、初始资金、佣金费率、策略名称、
字符串清理、API 密钥、正整数、浮点范围、批量校验 validate_all，
并补充 A 股代码的细节校验。

运行：pytest test/test_utils_validators.py -v
"""
import os
import sys

import pytest

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from src.utils.validators import (
    validate_date,
    validate_date_range,
    validate_initial_capital,
    validate_commission_rate,
    validate_strategy_name,
    sanitize_string,
    validate_api_key,
    validate_positive_integer,
    validate_float_range,
    validate_all,
    validate_stock_code,
    MIN_INITIAL_CAPITAL,
    MAX_INITIAL_CAPITAL,
)


class TestValidateDate:
    """日期格式与范围校验。"""

    def test_valid(self):
        assert validate_date("2024-06-01") == (True, None)

    def test_custom_name(self):
        ok, err = validate_date("", date_name="开始日期")
        assert ok is False
        assert "开始日期" in err

    def test_empty(self):
        assert validate_date("")[0] is False

    def test_bad_format(self):
        assert validate_date("2024/06/01")[0] is False
        assert validate_date("20240601")[0] is False

    def test_too_early(self):
        # MIN_DATE = 2000-01-01
        assert validate_date("1999-12-31")[0] is False

    def test_too_late(self):
        # MAX_DATE = 2030-12-31
        assert validate_date("2031-01-01")[0] is False

    def test_invalid_calendar_date(self):
        # 格式正确但日历上不存在
        assert validate_date("2024-02-31")[0] is False


class TestValidateDateRange:
    """日期范围校验。"""

    def test_valid(self):
        assert validate_date_range("2024-01-01", "2024-06-01") == (True, None)

    def test_start_after_end(self):
        assert validate_date_range("2024-06-01", "2024-01-01")[0] is False

    def test_too_short(self):
        # 跨度不足 30 天
        assert validate_date_range("2024-01-01", "2024-01-15")[0] is False

    def test_too_long(self):
        # 跨度超过 5 年
        assert validate_date_range("2018-01-01", "2024-12-31")[0] is False

    def test_invalid_start_propagates(self):
        ok, err = validate_date_range("bad", "2024-06-01")
        assert ok is False
        assert "开始日期" in err


class TestValidateInitialCapital:
    """初始资金校验。"""

    def test_valid(self):
        assert validate_initial_capital(100000.0)[0] is True
        assert validate_initial_capital(50000)[0] is True  # int 也接受

    def test_below_min(self):
        assert validate_initial_capital(MIN_INITIAL_CAPITAL - 1)[0] is False

    def test_above_max(self):
        assert validate_initial_capital(MAX_INITIAL_CAPITAL + 1)[0] is False

    def test_non_numeric(self):
        assert validate_initial_capital("not_a_number")[0] is False


class TestValidateCommissionRate:
    """佣金费率校验。"""

    def test_valid(self):
        assert validate_commission_rate(0.001)[0] is True
        assert validate_commission_rate(0.0)[0] is True

    def test_negative(self):
        assert validate_commission_rate(-0.01)[0] is False

    def test_too_high(self):
        # MAX_COMMISSION_RATE = 0.1
        assert validate_commission_rate(0.2)[0] is False

    def test_non_numeric(self):
        assert validate_commission_rate("x")[0] is False


class TestValidateStrategyName:
    """策略名称校验。"""

    def test_valid(self):
        assert validate_strategy_name("均线策略_1")[0] is True
        assert validate_strategy_name("MA-Strategy")[0] is True
        assert validate_strategy_name("情绪MA")[0] is True

    def test_too_short(self):
        assert validate_strategy_name("a")[0] is False  # <2

    def test_too_long(self):
        assert validate_strategy_name("a" * 51)[0] is False  # >50

    def test_bad_chars(self):
        assert validate_strategy_name("name@bad")[0] is False
        assert validate_strategy_name("name with space")[0] is False

    def test_empty(self):
        assert validate_strategy_name("")[0] is False


class TestSanitizeString:
    """字符串清理测试。"""

    def test_strips_whitespace(self):
        assert sanitize_string("  hello  ") == "hello"

    def test_truncates(self):
        assert sanitize_string("a" * 200, max_length=10) == "a" * 10

    def test_removes_dangerous_chars(self):
        # < > ' 被移除
        out = sanitize_string("<script>alert('x')</script>")
        assert out == "scriptalertx/script"

    def test_non_string_returns_empty(self):
        assert sanitize_string(123) == ""
        assert sanitize_string(None) == ""


class TestValidateApiKey:
    """API 密钥校验。"""

    def test_valid(self):
        assert validate_api_key("sk-1234567890")[0] is True  # len>=10

    def test_too_short(self):
        assert validate_api_key("short")[0] is False

    def test_empty(self):
        assert validate_api_key("")[0] is False


class TestValidatePositiveInteger:
    """正整数校验。"""

    @pytest.mark.parametrize("val", [5, 1, 100])
    def test_valid(self, val):
        assert validate_positive_integer(val)[0] is True

    @pytest.mark.parametrize("val", [0, -3])
    def test_non_positive(self, val):
        assert validate_positive_integer(val)[0] is False

    def test_string_numeric(self):
        assert validate_positive_integer("10")[0] is True

    def test_non_numeric(self):
        assert validate_positive_integer("abc")[0] is False


class TestValidateFloatRange:
    """浮点范围校验。"""

    def test_in_range(self):
        assert validate_float_range(5, 0, 10)[0] is True
        assert validate_float_range(0, 0, 10)[0] is True
        assert validate_float_range(10, 0, 10)[0] is True

    def test_out_of_range(self):
        assert validate_float_range(-1, 0, 10)[0] is False
        assert validate_float_range(11, 0, 10)[0] is False

    def test_non_numeric(self):
        assert validate_float_range("x", 0, 10)[0] is False


class TestValidateAll:
    """批量校验测试。"""

    def test_all_valid(self):
        ok, err = validate_all(
            code=("000001", "stock_code"),
            capital=(100000.0, "initial_capital"),
        )
        assert ok is True
        assert err is None

    def test_first_error_returned(self):
        ok, err = validate_all(
            code=("abc", "stock_code"),
            capital=(100000.0, "initial_capital"),
        )
        assert ok is False
        assert "code" in err

    def test_unknown_validator_skipped(self):
        ok, err = validate_all(x=("any", "nonexistent_validator"))
        assert ok is True


class TestValidateStockCodeAShare:
    """A 股代码细节校验（补充 test_backtest.py 未覆盖部分）。"""

    @pytest.mark.parametrize("code", ["sh600000", "sz000001", "600000", "000001", "300001"])
    def test_valid(self, code):
        assert validate_stock_code(code)[0] is True

    @pytest.mark.parametrize("code", ["123456", "500001", "abc123", "12345", ""])
    def test_invalid(self, code):
        assert validate_stock_code(code)[0] is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
