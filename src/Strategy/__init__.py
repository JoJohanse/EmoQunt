"""
策略模块

包含策略基类、策略管理器和各种交易策略实现
"""

from .Strategy import (
    StrategyBase,
    StrategyManager,
    global_strategy_manager,
    Strategy,
    TradeRecordManager,
    TradeRecord,
    parse_bool,
    extract_param_value,
    build_param_dict,
    create_user_strategy_class,
    STRATEGY_TEMPLATES,
)

__all__ = [
    'StrategyBase',
    'StrategyManager',
    'global_strategy_manager',
    'Strategy',
    'TradeRecordManager',
    'TradeRecord',
    'parse_bool',
    'extract_param_value',
    'build_param_dict',
    'create_user_strategy_class',
    'STRATEGY_TEMPLATES',
]
