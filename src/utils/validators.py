"""
输入验证模块

提供各种输入验证函数，用于验证Web接口参数
"""

import re
from datetime import datetime
from typing import Tuple, Optional, List
import logging

logger = logging.getLogger(__name__)


class ValidationError(Exception):
    """验证错误异常"""
    pass


# 常量定义
STOCK_CODE_PATTERN = re.compile(r'^[0-9]{6}$')
DATE_PATTERN = re.compile(r'^\d{4}-\d{2}-\d{2}$')
MIN_DATE = datetime(2000, 1, 1)
MAX_DATE = datetime(2030, 12, 31)

# 回测参数限制
MIN_INITIAL_CAPITAL = 10000.0
MAX_INITIAL_CAPITAL = 100000000.0
MIN_COMMISSION_RATE = 0.0
MAX_COMMISSION_RATE = 0.1


def validate_stock_code(stock_code: str) -> Tuple[bool, Optional[str]]:
    """
    验证股票代码格式
    
    :param stock_code: 股票代码
    :return: (是否有效, 错误信息)
    """
    if not stock_code:
        return False, "股票代码不能为空"
    
    # 去除可能的前缀
    clean_code = stock_code.strip()
    if clean_code.startswith(('sh', 'sz')):
        clean_code = clean_code[2:]
    
    if not STOCK_CODE_PATTERN.match(clean_code):
        return False, f"股票代码格式错误: {stock_code}，应为6位数字"
    
    # 验证股票代码开头
    first_digit = clean_code[0]
    if first_digit not in ('0', '3', '6'):
        return False, f"股票代码 {stock_code} 不是有效的A股代码"
    
    return True, None


def validate_date(date_str: str, date_name: str = "日期") -> Tuple[bool, Optional[str]]:
    """
    验证日期格式和范围
    
    :param date_str: 日期字符串 (YYYY-MM-DD)
    :param date_name: 日期名称（用于错误信息）
    :return: (是否有效, 错误信息)
    """
    if not date_str:
        return False, f"{date_name}不能为空"
    
    if not DATE_PATTERN.match(date_str):
        return False, f"{date_name}格式错误: {date_str}，应为 YYYY-MM-DD"
    
    try:
        date_obj = datetime.strptime(date_str, '%Y-%m-%d')
    except ValueError as e:
        return False, f"{date_name}无效: {date_str}"
    
    if date_obj < MIN_DATE:
        return False, f"{date_name}不能早于 {MIN_DATE.strftime('%Y-%m-%d')}"
    
    if date_obj > MAX_DATE:
        return False, f"{date_name}不能晚于 {MAX_DATE.strftime('%Y-%m-%d')}"
    
    return True, None


def validate_date_range(start_date: str, end_date: str) -> Tuple[bool, Optional[str]]:
    """
    验证日期范围
    
    :param start_date: 开始日期
    :param end_date: 结束日期
    :return: (是否有效, 错误信息)
    """
    # 先验证各自格式
    valid, error = validate_date(start_date, "开始日期")
    if not valid:
        return False, error
    
    valid, error = validate_date(end_date, "结束日期")
    if not valid:
        return False, error
    
    # 验证范围
    start = datetime.strptime(start_date, '%Y-%m-%d')
    end = datetime.strptime(end_date, '%Y-%m-%d')
    
    if start > end:
        return False, f"开始日期 {start_date} 不能晚于结束日期 {end_date}"
    
    # 验证时间跨度不超过5年
    days_diff = (end - start).days
    if days_diff > 365 * 5:
        return False, f"回测时间跨度不能超过5年"
    
    if days_diff < 30:
        return False, f"回测时间跨度不能少于30天"
    
    return True, None


def validate_initial_capital(capital: float) -> Tuple[bool, Optional[str]]:
    """
    验证初始资金
    
    :param capital: 初始资金
    :return: (是否有效, 错误信息)
    """
    if not isinstance(capital, (int, float)):
        return False, f"初始资金必须是数字"
    
    if capital < MIN_INITIAL_CAPITAL:
        return False, f"初始资金不能少于 {MIN_INITIAL_CAPITAL:,.0f} 元"
    
    if capital > MAX_INITIAL_CAPITAL:
        return False, f"初始资金不能超过 {MAX_INITIAL_CAPITAL:,.0f} 元"
    
    return True, None


def validate_commission_rate(rate: float) -> Tuple[bool, Optional[str]]:
    """
    验证佣金费率
    
    :param rate: 佣金费率
    :return: (是否有效, 错误信息)
    """
    if not isinstance(rate, (int, float)):
        return False, f"佣金费率必须是数字"
    
    if rate < MIN_COMMISSION_RATE:
        return False, f"佣金费率不能为负数"
    
    if rate > MAX_COMMISSION_RATE:
        return False, f"佣金费率不能超过 {MAX_COMMISSION_RATE * 100}%"
    
    return True, None


def validate_strategy_name(name: str) -> Tuple[bool, Optional[str]]:
    """
    验证策略名称
    
    :param name: 策略名称
    :return: (是否有效, 错误信息)
    """
    if not name:
        return False, "策略名称不能为空"
    
    name = name.strip()
    
    if len(name) < 2:
        return False, "策略名称长度不能少于2个字符"
    
    if len(name) > 50:
        return False, "策略名称长度不能超过50个字符"
    
    # 检查非法字符
    if not re.match(r'^[\w\u4e00-\u9fa5\-]+$', name):
        return False, "策略名称只能包含中文、英文、数字、下划线和连字符"
    
    return True, None


def validate_backtest_params(
    stock_code: str,
    start_date: str,
    end_date: str,
    initial_capital: float,
    commission_rate: float
) -> Tuple[bool, Optional[str]]:
    """
    验证回测参数
    
    :param stock_code: 股票代码
    :param start_date: 开始日期
    :param end_date: 结束日期
    :param initial_capital: 初始资金
    :param commission_rate: 佣金费率
    :return: (是否有效, 错误信息)
    """
    # 验证股票代码
    valid, error = validate_stock_code(stock_code)
    if not valid:
        return False, error
    
    # 验证日期范围
    valid, error = validate_date_range(start_date, end_date)
    if not valid:
        return False, error
    
    # 验证初始资金
    valid, error = validate_initial_capital(initial_capital)
    if not valid:
        return False, error
    
    # 验证佣金费率
    valid, error = validate_commission_rate(commission_rate)
    if not valid:
        return False, error
    
    return True, None


def sanitize_string(value: str, max_length: int = 100) -> str:
    """
    清理字符串输入，防止注入攻击
    
    :param value: 输入字符串
    :param max_length: 最大长度
    :return: 清理后的字符串
    """
    if not isinstance(value, str):
        return ""
    
    # 去除首尾空白
    value = value.strip()
    
    # 限制长度
    if len(value) > max_length:
        value = value[:max_length]
    
    # 去除潜在的危险字符
    # 保留常用字符：中英文、数字、空格、标点
    value = re.sub(r'[<>\"\'%;()&+\-\-\*\\]', '', value)
    
    return value


def validate_api_key(api_key: str) -> Tuple[bool, Optional[str]]:
    """
    验证API密钥格式
    
    :param api_key: API密钥
    :return: (是否有效, 错误信息)
    """
    if not api_key:
        return False, "API密钥不能为空"
    
    if len(api_key) < 10:
        return False, "API密钥格式错误"
    
    return True, None


def validate_positive_integer(value, field_name: str = "值") -> Tuple[bool, Optional[str]]:
    """
    验证正整数
    
    :param value: 待验证的值
    :param field_name: 字段名称
    :return: (是否有效, 错误信息)
    """
    try:
        num = int(value)
        if num <= 0:
            return False, f"{field_name}必须是正整数"
        return True, None
    except (ValueError, TypeError):
        return False, f"{field_name}必须是整数"


def validate_float_range(
    value,
    min_val: float,
    max_val: float,
    field_name: str = "值"
) -> Tuple[bool, Optional[str]]:
    """
    验证浮点数范围
    
    :param value: 待验证的值
    :param min_val: 最小值
    :param max_val: 最大值
    :param field_name: 字段名称
    :return: (是否有效, 错误信息)
    """
    try:
        num = float(value)
        if num < min_val or num > max_val:
            return False, f"{field_name}必须在 {min_val} 和 {max_val} 之间"
        return True, None
    except (ValueError, TypeError):
        return False, f"{field_name}必须是数字"


# 预定义的验证器
VALIDATORS = {
    'stock_code': validate_stock_code,
    'date': validate_date,
    'date_range': validate_date_range,
    'initial_capital': validate_initial_capital,
    'commission_rate': validate_commission_rate,
    'strategy_name': validate_strategy_name,
    'backtest_params': validate_backtest_params,
}


def validate_all(**kwargs) -> Tuple[bool, Optional[str]]:
    """
    批量验证多个参数
    
    用法：
        valid, error = validate_all(
            stock_code=(stock_code, 'stock_code'),
            start_date=(start_date, 'date', '开始日期'),
            end_date=(end_date, 'date', '结束日期')
        )
    
    :param kwargs: 参数名 -> (值, 验证器名, *额外参数)
    :return: (是否全部有效, 第一个错误信息)
    """
    for field_name, validation_spec in kwargs.items():
        if len(validation_spec) < 2:
            continue
        
        value = validation_spec[0]
        validator_name = validation_spec[1]
        extra_args = validation_spec[2:] if len(validation_spec) > 2 else ()
        
        validator = VALIDATORS.get(validator_name)
        if not validator:
            logger.warning(f"未知的验证器: {validator_name}")
            continue
        
        valid, error = validator(value, *extra_args) if extra_args else validator(value)
        if not valid:
            return False, f"{field_name}: {error}"
    
    return True, None
