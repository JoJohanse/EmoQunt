"""
策略模块

包含策略基类、策略管理器和各种交易策略实现
"""

from .Strategy import (
    StrategyBase,
    SimpleMAStrategy,
    StrategyManager,
    global_strategy_manager,
    Strategy,
    TradeRecordManager,
    TradeRecord
)

from .SentimentMAStrategy import SentimentMAStrategy

__all__ = [
    'StrategyBase',
    'SimpleMAStrategy',
    'SentimentMAStrategy',
    'StrategyManager',
    'global_strategy_manager',
    'Strategy',
    'TradeRecordManager',
    'TradeRecord'
]
