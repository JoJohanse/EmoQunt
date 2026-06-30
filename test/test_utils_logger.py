# coding=utf-8
"""日志系统模块 (src/utils/logger.py) 单元测试。

覆盖：
- setup_global_logger / get_logger 获取日志器
- LogExceptionHandler 装饰器（reraise / 吞掉异常）
- log_function_call 装饰器返回值
- replace_print_with_logging
- set_log_level 有效/无效级别

运行：pytest test/test_utils_logger.py -v
"""
import logging
import os
import sys

import pytest

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from src.utils.logger import (
    global_logger,
    get_logger,
    setup_global_logger,
    set_log_level,
    LogExceptionHandler,
    log_function_call,
    replace_print_with_logging,
    LOG_LEVEL_MAP,
)


class TestGetLogger:
    """日志器获取测试。"""

    def test_get_logger_default_returns_global(self):
        assert get_logger() is global_logger

    def test_setup_global_logger_returns_logger(self):
        logger = setup_global_logger("QdtUnitTestLogger")
        assert isinstance(logger, logging.Logger)
        assert logger.name == "QdtUnitTestLogger"

    def test_named_logger_via_get_logger(self):
        named = get_logger("QdtNamedLoggerTest")
        assert isinstance(named, logging.Logger)
        assert named.name == "QdtNamedLoggerTest"

    def test_repeated_setup_no_duplicate_handlers(self):
        """同名日志器重复设置不应无限累加处理器。"""
        logger = setup_global_logger("QdtDedupLoggerTest")
        n_before = len(logger.handlers)
        setup_global_logger("QdtDedupLoggerTest")
        assert len(logger.handlers) == n_before


class TestLogExceptionHandler:
    """异常处理装饰器测试。"""

    def test_reraise_propagates(self):
        @LogExceptionHandler(logger=global_logger, reraise=True)
        def boom():
            raise ValueError("boom")

        with pytest.raises(ValueError):
            boom()

    def test_swallow_returns_none(self):
        @LogExceptionHandler(logger=global_logger, reraise=False)
        def boom():
            raise ValueError("boom")

        assert boom() is None

    def test_normal_pass_through(self):
        @LogExceptionHandler(logger=global_logger, reraise=True)
        def ok(x):
            return x * 2

        assert ok(21) == 42


class TestLogFunctionCall:
    """函数调用日志装饰器测试。"""

    def test_returns_result(self):
        @log_function_call(logger=global_logger)
        def add(a, b):
            return a + b

        assert add(2, 3) == 5

    def test_propagates_exception(self):
        @log_function_call(logger=global_logger)
        def boom():
            raise RuntimeError("x")

        with pytest.raises(RuntimeError):
            boom()


class TestReplacePrintWithLogging:
    """print 替代函数测试。"""

    def test_returns_callable_and_logger(self):
        fn, logger = replace_print_with_logging("QdtReplacePrintTest")
        assert callable(fn)
        assert logger.name == "QdtReplacePrintTest"
        # 调用不应抛异常
        fn("hello", "world")


class TestSetLogLevel:
    """日志级别设置测试。"""

    def test_valid_level(self):
        original = global_logger.level
        try:
            set_log_level("DEBUG")
            assert global_logger.level == logging.DEBUG
            set_log_level("WARNING")
            assert global_logger.level == logging.WARNING
        finally:
            global_logger.setLevel(original)

    def test_invalid_level_keeps_current(self):
        original = global_logger.level
        try:
            set_log_level("NOT_A_LEVEL")
            # 无效级别不应改变当前级别
            assert global_logger.level == original
        finally:
            global_logger.setLevel(original)

    def test_log_level_map_keys(self):
        for key in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
            assert key in LOG_LEVEL_MAP


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
