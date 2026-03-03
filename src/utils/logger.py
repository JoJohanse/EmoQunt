"""
日志系统模块

提供统一的日志管理功能，替代原有的print语句
"""

import logging
import logging.handlers
import os
from datetime import datetime
from typing import Optional
import sys


class LoggerSetup:
    """
    日志系统设置类
    """
    
    def __init__(self, name: str = "QdtLogger", level: int = logging.INFO):
        """
        初始化日志系统
        :param name: 日志器名称
        :param level: 日志级别
        """
        self.logger = logging.getLogger(name)
        self.logger.setLevel(level)
        
        # 避免重复添加处理器
        if not self.logger.handlers:
            self._setup_handlers()
    
    def _setup_handlers(self):
        """
        设置日志处理器
        """
        # 创建格式化器
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(funcName)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # 控制台处理器
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)
        
        # 文件处理器 - 按日期轮转
        log_dir = os.path.join(os.getcwd(), 'logs')
        os.makedirs(log_dir, exist_ok=True)
        
        # 错误日志文件
        error_file_handler = logging.handlers.TimedRotatingFileHandler(
            filename=os.path.join(log_dir, 'error.log'),
            when='midnight',
            interval=1,
            backupCount=30,  # 保留30天的日志
            encoding='utf-8'
        )
        error_file_handler.setLevel(logging.ERROR)
        error_file_handler.setFormatter(formatter)
        self.logger.addHandler(error_file_handler)
        
        # 通用日志文件
        general_file_handler = logging.handlers.TimedRotatingFileHandler(
            filename=os.path.join(log_dir, 'app.log'),
            when='midnight',
            interval=1,
            backupCount=30,  # 保留30天的日志
            encoding='utf-8'
        )
        general_file_handler.setLevel(logging.DEBUG)
        general_file_handler.setFormatter(formatter)
        self.logger.addHandler(general_file_handler)
    
    def get_logger(self):
        """
        获取日志器实例
        :return: 日志器
        """
        return self.logger


def setup_global_logger(name: str = "QdtTest", level: int = logging.INFO) -> logging.Logger:
    """
    设置全局日志器
    :param name: 日志器名称
    :param level: 日志级别
    :return: 日志器实例
    """
    logger_setup = LoggerSetup(name, level)
    return logger_setup.get_logger()


def replace_print_with_logging(module_name: str = "QdtTest"):
    """
    创建一个包装器，将print替换为logging
    注意：这不是直接替换print，而是提供一个推荐的替代方案
    :param module_name: 模块名称
    """
    logger = setup_global_logger(module_name)
    
    def logged_print(*args, **kwargs):
        """
        记录日志的print函数替代品
        """
        message = ' '.join(str(arg) for arg in args)
        logger.info(message)
    
    return logged_print, logger


# 创建全局日志器
global_logger = setup_global_logger("QdtTest")


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """
    获取日志器
    :param name: 日志器名称，如果不提供则返回全局日志器
    :return: 日志器实例
    """
    if name is None:
        return global_logger
    else:
        return setup_global_logger(name)


# 便捷的日志函数
def debug(msg: str, *args, **kwargs):
    """DEBUG级别日志"""
    global_logger.debug(msg, *args, **kwargs)


def info(msg: str, *args, **kwargs):
    """INFO级别日志"""
    global_logger.info(msg, *args, **kwargs)


def warning(msg: str, *args, **kwargs):
    """WARNING级别日志"""
    global_logger.warning(msg, *args, **kwargs)


def error(msg: str, *args, **kwargs):
    """ERROR级别日志"""
    global_logger.error(msg, *args, **kwargs)


def critical(msg: str, *args, **kwargs):
    """CRITICAL级别日志"""
    global_logger.critical(msg, *args, **kwargs)


def log_exception(msg: str = "An exception occurred"):
    """
    记录异常信息
    :param msg: 异常消息
    """
    global_logger.exception(msg)


class LogExceptionHandler:
    """
    异常处理装饰器，自动记录异常日志
    """
    
    def __init__(self, logger: Optional[logging.Logger] = None, reraise: bool = True):
        """
        初始化异常处理装饰器
        :param logger: 日志器实例
        :param reraise: 是否重新抛出异常
        """
        self.logger = logger or global_logger
        self.reraise = reraise
    
    def __call__(self, func):
        """
        装饰器实现
        """
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                self.logger.error(f"函数 {func.__name__} 发生异常: {str(e)}", exc_info=True)
                if self.reraise:
                    raise
                return None
        return wrapper


def log_function_call(logger: Optional[logging.Logger] = None, level: int = logging.DEBUG):
    """
    函数调用日志装饰器
    :param logger: 日志器实例
    :param level: 日志级别
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            _logger = logger or global_logger
            _logger.log(level, f"调用函数 {func.__name__}，参数: args={args}, kwargs={kwargs}")
            result = func(*args, **kwargs)
            _logger.log(level, f"函数 {func.__name__} 返回: {result}")
            return result
        return wrapper
    return decorator


# 配置日志级别映射
LOG_LEVEL_MAP = {
    'DEBUG': logging.DEBUG,
    'INFO': logging.INFO,
    'WARNING': logging.WARNING,
    'ERROR': logging.ERROR,
    'CRITICAL': logging.CRITICAL
}


def set_log_level(level: str):
    """
    设置全局日志级别
    :param level: 日志级别字符串 ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL')
    """
    if level.upper() in LOG_LEVEL_MAP:
        global_logger.setLevel(LOG_LEVEL_MAP[level.upper()])
        info(f"全局日志级别已设置为: {level.upper()}")
    else:
        warning(f"无效的日志级别: {level}，使用默认级别 INFO")


if __name__ == "__main__":
    # 示例使用
    print("日志系统示例")
    print("=" * 50)
    
    # 获取日志器
    logger = get_logger("TestLogger")
    
    # 测试不同级别的日志
    debug("这是调试信息")
    info("这是普通信息")
    warning("这是警告信息")
    error("这是错误信息")
    critical("这是严重错误信息")
    
    # 测试异常记录
    try:
        1 / 0
    except ZeroDivisionError:
        log_exception("捕获到除零错误")
    
    # 测试装饰器
    @LogExceptionHandler(logger=logger)
    def test_function():
        print("这是一个测试函数")
        raise ValueError("测试异常")
    
    # test_function()  # 取消注释以测试异常处理
    
    # 测试函数调用日志
    @log_function_call(logger=logger, level=logging.INFO)
    def sample_function(x, y, operation="add"):
        if operation == "add":
            return x + y
        elif operation == "multiply":
            return x * y
        else:
            raise ValueError(f"不支持的操作: {operation}")
    
    result = sample_function(5, 3, operation="multiply")
    print(f"计算结果: {result}")
    
    # 测试设置日志级别
    set_log_level('DEBUG')
    
    print("=" * 50)
    print("日志系统示例完成")