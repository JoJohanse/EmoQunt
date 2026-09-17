"""src/Strategy/code_validator.py ast 白名单校验器测试。

覆盖：正常样本通过并提取 STRATEGY_PARAMS；危险 import/调用/通配导入/
dunder 属性链/缺失生命周期函数/非字面量参数/语法错误 各自被拦截。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.Strategy.code_validator import validate_source  # noqa: E402


GOOD = '''STRATEGY_PARAMS = {
    "short_window": 5,
    "trade_percent": 0.9,
    "use_filter": True,
    "note": "双均线",
}


def initialize(context):
    context.seen = 0


def handle_data(context, data):
    context.seen += 1
    if data.close > 0:
        pass
'''


def test_good_source_passes_and_extracts_params():
    errors, params = validate_source(GOOD)
    assert errors == []
    assert params == {"short_window": 5, "trade_percent": 0.9, "use_filter": True, "note": "双均线"}


def test_banned_import_rejected():
    errors, _ = validate_source(GOOD + "\nimport os\n")
    assert any("os" in e for e in errors)
    errors, _ = validate_source(GOOD + "\nfrom requests import get\n")
    assert len(errors) == 1
    errors, _ = validate_source(GOOD + "\nfrom emoquant.api import *\n")
    assert any("通配" in e or "*" in e for e in errors)


def test_allowed_import_passes():
    errors, _ = validate_source(
        GOOD + "\nimport numpy as np\nfrom math import sqrt\nfrom emoquant.api import buy\n"
    )
    assert errors == []


def test_banned_calls_rejected():
    for snippet in ("eval('1+1')", "open('x')", "getattr(object(), 'x')",
                    "exec('pass')", "__import__('os')"):
        errors, _ = validate_source(GOOD + "\n" + snippet + "\n")
        assert errors, f"{snippet} 应被拦截"


def test_dunder_attribute_chain_rejected():
    errors, _ = validate_source(GOOD + "\nx = ().__class__\n")
    assert any("__class__" in e for e in errors)
    errors, _ = validate_source(GOOD + "\ny = {}.__globals__ if 0 else None\n")
    assert any("__globals__" in e for e in errors)


def test_missing_required_functions():
    errors, _ = validate_source("STRATEGY_PARAMS = {}\n\n\ndef initialize(context):\n    pass\n")
    assert any("handle_data" in e for e in errors)
    errors, _ = validate_source("pass\n")
    assert any("initialize" in e for e in errors) and any("handle_data" in e for e in errors)


def test_non_literal_params_rejected():
    errors, _ = validate_source(
        "STRATEGY_PARAMS = dict(a=1)\n\n\ndef initialize(c):\n    pass\n\n\ndef handle_data(c, d):\n    pass\n"
    )
    assert any("STRATEGY_PARAMS" in e for e in errors)
    errors, _ = validate_source(
        "import math\nSTRATEGY_PARAMS = {'n': math.sqrt(4)}\n\n\ndef initialize(c):\n    pass\n\n\ndef handle_data(c, d):\n    pass\n"
    )
    assert any("STRATEGY_PARAMS" in e for e in errors)


def test_syntax_error_reported_with_line():
    errors, _ = validate_source("def broken(:\n    pass\n")
    assert len(errors) == 1 and "语法错误" in errors[0]


def test_empty_and_oversize_rejected():
    errors, _ = validate_source("")
    assert errors == ["策略代码不能为空"]
    errors, _ = validate_source("x = 1\n" * 30000)
    assert any("上限" in e for e in errors)
