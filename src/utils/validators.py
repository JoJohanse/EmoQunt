"""
输入验证模块

提供各种输入验证函数，用于验证Web接口参数

文案国际化：所有面向用户的消息在**产出点**用 ``vmsg(key, 中文模板, **params)``
翻译（en 走 src/utils/i18n_data/validators.py 目录，zh 逐字不变）。
"""

import re
from datetime import datetime
from typing import Tuple, Optional, List
import logging

from src.utils.i18n import vmsg

logger = logging.getLogger(__name__)


class ValidationError(Exception):
    """验证错误异常"""
    pass


def _localized_param(name: str, kind: str) -> str:
    """
    本地化「本身是中文的参数」（日期名 dateName / 字段名 fieldName）。

    zh 下原样返回入参（消息逐字不变），en 下查目录换成英文（如 开始日期 → start date）。

    :param name: 中文参数值（如 "开始日期"）
    :param kind: 目录前缀（"dateName" 或 "fieldName"）
    :return: 当前语言下的参数文案
    """
    return vmsg(f"validator.{kind}.{name}", name)


# 常量定义
STOCK_CODE_PATTERN = re.compile(r'^[0-9]{6}$')
# 美股 ticker：1-6 个字符，字母/数字/点（如 AAPL, BRK.B），且不能纯数字
US_STOCK_CODE_PATTERN = re.compile(r'^(?![0-9.]+$)[A-Za-z0-9.]{1,6}$')
DATE_PATTERN = re.compile(r'^\d{4}-\d{2}-\d{2}$')
MIN_DATE = datetime(2000, 1, 1)
MAX_DATE = datetime(2030, 12, 31)

# 回测参数限制
MIN_INITIAL_CAPITAL = 10000.0
MAX_INITIAL_CAPITAL = 100000000.0
MIN_COMMISSION_RATE = 0.0
MAX_COMMISSION_RATE = 0.1


def validate_us_stock_code(stock_code: str) -> Tuple[bool, Optional[str]]:
    """
    验证美股股票代码（ticker）格式。

    规则：1-6 个字符，仅含字母/数字/点（如 AAPL, MSFT, BRK.B），大写化；
    拒绝纯数字（避免与 A 股 6 位代码混淆）。

    :param stock_code: 美股代码
    :return: (是否有效, 错误信息)
    """
    if not stock_code:
        return False, vmsg("validator.usCodeEmpty", "美股代码不能为空")

    clean_code = stock_code.strip()
    if not US_STOCK_CODE_PATTERN.match(clean_code):
        return False, vmsg(
            "validator.usCodeFormat",
            "美股代码格式错误: {code}，应为1-6位字母/数字（如 AAPL、BRK.B），不能纯数字",
            code=stock_code,
        )

    return True, None


def validate_stock_code(stock_code: str, market: str = 'zh_a') -> Tuple[bool, Optional[str]]:
    """
    验证股票代码格式

    :param stock_code: 股票代码（A股6位数字；美股字母代码如 AAPL）
    :param market: 市场，'zh_a'（A股，默认）或 'us'（美股）
    :return: (是否有效, 错误信息)
    """
    if market == 'us':
        return validate_us_stock_code(stock_code)

    if not stock_code:
        return False, vmsg("validator.codeEmpty", "股票代码不能为空")

    # 去除可能的前缀
    clean_code = stock_code.strip()
    if clean_code.startswith(('sh', 'sz')):
        clean_code = clean_code[2:]

    if not STOCK_CODE_PATTERN.match(clean_code):
        return False, vmsg(
            "validator.codeFormat", "股票代码格式错误: {code}，应为6位数字", code=stock_code,
        )

    # 验证股票代码开头
    first_digit = clean_code[0]
    if first_digit not in ('0', '3', '6'):
        return False, vmsg(
            "validator.codeInvalid", "股票代码 {code} 不是有效的A股代码", code=stock_code,
        )

    return True, None


def validate_date(date_str: str, date_name: str = "日期") -> Tuple[bool, Optional[str]]:
    """
    验证日期格式和范围
    
    :param date_str: 日期字符串 (YYYY-MM-DD)
    :param date_name: 日期名称（用于错误信息）
    :return: (是否有效, 错误信息)
    """
    if not date_str:
        return False, vmsg("validator.dateEmpty", "{name}不能为空", name=_localized_param(date_name, "dateName"))

    if not DATE_PATTERN.match(date_str):
        return False, vmsg(
            "validator.dateFormat", "{name}格式错误: {date}，应为 YYYY-MM-DD",
            name=_localized_param(date_name, "dateName"), date=date_str,
        )

    try:
        date_obj = datetime.strptime(date_str, '%Y-%m-%d')
    except ValueError as e:
        return False, vmsg(
            "validator.dateInvalid", "{name}无效: {date}",
            name=_localized_param(date_name, "dateName"), date=date_str,
        )

    if date_obj < MIN_DATE:
        return False, vmsg(
            "validator.dateTooEarly", "{name}不能早于 {min}",
            name=_localized_param(date_name, "dateName"),
            min=MIN_DATE.strftime('%Y-%m-%d'),
        )

    if date_obj > MAX_DATE:
        return False, vmsg(
            "validator.dateTooLate", "{name}不能晚于 {max}",
            name=_localized_param(date_name, "dateName"),
            max=MAX_DATE.strftime('%Y-%m-%d'),
        )

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
        return False, vmsg(
            "validator.dateRangeOrder", "开始日期 {start} 不能晚于结束日期 {end}",
            start=start_date, end=end_date,
        )

    # 验证时间跨度不超过5年
    days_diff = (end - start).days
    if days_diff > 365 * 5:
        return False, vmsg("validator.dateRangeTooLong", "回测时间跨度不能超过5年")

    if days_diff < 30:
        return False, vmsg("validator.dateRangeTooShort", "回测时间跨度不能少于30天")

    return True, None


def validate_initial_capital(capital: float) -> Tuple[bool, Optional[str]]:
    """
    验证初始资金
    
    :param capital: 初始资金
    :return: (是否有效, 错误信息)
    """
    if not isinstance(capital, (int, float)):
        return False, vmsg("validator.capitalNotNumber", "初始资金必须是数字")

    if capital < MIN_INITIAL_CAPITAL:
        return False, vmsg(
            "validator.capitalTooSmall", "初始资金不能少于 {min} 元",
            min=f"{MIN_INITIAL_CAPITAL:,.0f}",
        )

    if capital > MAX_INITIAL_CAPITAL:
        return False, vmsg(
            "validator.capitalTooLarge", "初始资金不能超过 {max} 元",
            max=f"{MAX_INITIAL_CAPITAL:,.0f}",
        )

    return True, None


def validate_commission_rate(rate: float) -> Tuple[bool, Optional[str]]:
    """
    验证佣金费率
    
    :param rate: 佣金费率
    :return: (是否有效, 错误信息)
    """
    if not isinstance(rate, (int, float)):
        return False, vmsg("validator.commissionNotNumber", "佣金费率必须是数字")

    if rate < MIN_COMMISSION_RATE:
        return False, vmsg("validator.commissionNegative", "佣金费率不能为负数")

    if rate > MAX_COMMISSION_RATE:
        return False, vmsg(
            "validator.commissionTooHigh", "佣金费率不能超过 {max}%",
            max=f"{MAX_COMMISSION_RATE * 100}",
        )

    return True, None


def validate_strategy_name(name: str) -> Tuple[bool, Optional[str]]:
    """
    验证策略名称
    
    :param name: 策略名称
    :return: (是否有效, 错误信息)
    """
    if not name:
        return False, vmsg("validator.nameEmpty", "策略名称不能为空")

    name = name.strip()

    if len(name) < 2:
        return False, vmsg("validator.nameTooShort", "策略名称长度不能少于2个字符")

    if len(name) > 50:
        return False, vmsg("validator.nameTooLong", "策略名称长度不能超过50个字符")

    # 检查非法字符
    if not re.match(r'^[\w\u4e00-\u9fa5\-]+$', name):
        return False, vmsg("validator.nameBadChars", "策略名称只能包含中文、英文、数字、下划线和连字符")

    return True, None


def validate_backtest_params(
    stock_code: str,
    start_date: str,
    end_date: str,
    initial_capital: float,
    commission_rate: float,
    market: str = 'zh_a'
) -> Tuple[bool, Optional[str]]:
    """
    验证回测参数

    :param stock_code: 股票代码（A股6位数字；美股字母代码）
    :param start_date: 开始日期
    :param end_date: 结束日期
    :param initial_capital: 初始资金
    :param commission_rate: 佣金费率
    :param market: 市场，'zh_a'（A股，默认）或 'us'（美股）
    :return: (是否有效, 错误信息)
    """
    # 验证股票代码
    valid, error = validate_stock_code(stock_code, market=market)
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
        return False, vmsg("validator.apiKeyEmpty", "API密钥不能为空")

    if len(api_key) < 10:
        return False, vmsg("validator.apiKeyFormat", "API密钥格式错误")

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
            return False, vmsg(
                "validator.positiveInt", "{name}必须是正整数",
                name=_localized_param(field_name, "fieldName"),
            )
        return True, None
    except (ValueError, TypeError):
        return False, vmsg(
            "validator.intRequired", "{name}必须是整数",
            name=_localized_param(field_name, "fieldName"),
        )


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
            return False, vmsg(
                "validator.floatRange", "{name}必须在 {min} 和 {max} 之间",
                name=_localized_param(field_name, "fieldName"),
                min=min_val, max=max_val,
            )
        return True, None
    except (ValueError, TypeError):
        return False, vmsg(
            "validator.numberRequired", "{name}必须是数字",
            name=_localized_param(field_name, "fieldName"),
        )


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
