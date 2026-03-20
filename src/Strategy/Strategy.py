
import datetime
import pandas as pd
import backtrader as bt
import numpy as np

# 日志记录功能（简化版，实际项目中可替换为更完善的日志系统）
def create_log(name):
    import logging
    logger = logging.getLogger(name)
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    return logger

logger = create_log("strategy")


class TradeRecordManager:
    """
    交易记录管理器，用于管理和存储交易记录
    """
    def __init__(self):
        self.trade_records = []

    def add_trade_record(self, trade_id, date, action, price, size, total_amount, commission, order_type, status):
        """
        添加交易记录
        :param trade_id: 交易唯一标识
        :param date: 交易日期
        :param action: 交易动作（'B'表示买入，'S'表示卖出）
        :param price: 交易价格
        :param size: 交易数量
        :param total_amount: 交易总金额
        :param commission: 佣金费用
        :param order_type: 订单类型（'buy'或'sell'）
        :param status: 订单状态
        """
        self.trade_records.append(
            TradeRecord(trade_id, date, action, price, size, total_amount, commission, order_type, status))

    def transform_to_dataframe(self):
        """
        将交易记录转换为DataFrame格式
        :return: 交易记录的DataFrame
        """
        return pd.DataFrame([record.__dict__ for record in self.trade_records])


class TradeRecord:
    """
    交易记录类，用于存储单条交易记录的详细信息
    """
    def __init__(self, trade_id, date, action, price, size, total_amount, commission, order_type, status):
        """
        初始化交易记录
        :param trade_id: 交易唯一标识
        :param date: 交易日期
        :param action: 交易动作（'B'表示买入，'S'表示卖出）
        :param price: 交易价格
        :param size: 交易数量
        :param total_amount: 交易总金额
        :param commission: 佣金费用
        :param order_type: 订单类型（'buy'或'sell'）
        :param status: 订单状态
        """
        if type(date) is datetime.date:
            # 将datetime.date转换为pandas Timestamp
            self.date = pd.Timestamp(date)
        elif type(date) is str:
            # 将字符串转换为pandas Timestamp
            self.date = pd.Timestamp(date)
        else:
            logger.info(type(date))
            raise ValueError('date must be datetime.date or str')
        self.trade_id = trade_id
        self.action = action
        self.price = price
        self.size = size
        self.total_amount = total_amount
        self.commission = commission
        self.order_type = order_type
        self.status = status


class StrategyBase(bt.Strategy):
    """
    交易策略基类，所有交易策略都应继承此类

    子类可自定义方法：
    - trading_strategy_buy:自定义买入策略
    - trading_strategy_sell:自定义卖出策略
    """
    params = (
        # 交易股票最小单位（股）
        ('min_order_size', 100),
        # 最大持仓比例 = 总持仓股票数量 * 持仓股票价格 / 总资产
        ('max_portfolio_percent', 0.8),
        # 单笔交易百分比（买） = 单笔交易费用 / 总资产
        ('max_single_buy_percent', 0.2),
        # 单笔交易百分比（卖） = 单笔交易费用 / 总资产
        ('max_single_sell_percent', 0.3),
    )

    def __init__(self):
        """
        初始化策略
        """
        self.trade_record_manager = TradeRecordManager()
        # 初始化交易参数
        self.min_order_size = self.p.min_order_size
        self.max_portfolio_percent = self.p.max_portfolio_percent
        self.max_single_buy_percent = self.p.max_single_buy_percent
        self.max_single_sell_percent = self.p.max_single_sell_percent
        self.indicator = None
        self.order = None

        # 交易信号计数器
        self.buy_signals_count = 0
        self.sell_signals_count = 0
        self.executed_buys_count = 0
        self.executed_sells_count = 0

    def set_indicator(self, indicator):
        """
        设置交易策略使用的信号指标
        :param indicator: 指标对象
        """
        self.indicator = indicator

    def next(self):
        """
        每个时间步执行的逻辑，子类应覆盖此方法
        """
        super().next()

    def trading_strategy_buy(self):
        """
        买入策略，子类应覆盖此方法实现具体的买入逻辑
        """
        pass

    def trading_strategy_sell(self):
        """
        卖出策略，子类应覆盖此方法实现具体的卖出逻辑
        """
        pass

    def notify_order(self, order):
        """
        订单状态通知，每笔订单状态改变都会触发
        :param order: 订单对象
        """
        if order.status in [order.Submitted, order.Accepted]:
            # 订单已提交或已接受，不做处理
            return

        if order.status in [order.Completed]:
            # 计算实际佣金
            actual_commission = self.calculate_commission(order.executed.size, order.executed.price)
            order_date = self.data.datetime.date(0)
            
            if order.isbuy():
                logger.info(f'【买入成交】: 价格={order.executed.price:.2f}, 数量={order.executed.size}')
                self.executed_buys_count += 1
                self.trade_record_manager.add_trade_record(
                    trade_id=order.ref,
                    date=order_date,
                    action='B',
                    price=order.executed.price,
                    size=abs(order.executed.size),
                    total_amount=order.executed.price * order.executed.size,
                    commission=actual_commission['total_commission'],
                    order_type='buy',
                    status=order.status
                )
            elif order.issell():
                logger.info(f'【卖出成交】: 价格={order.executed.price:.2f}, 数量={order.executed.size}')
                self.executed_sells_count += 1
                self.trade_record_manager.add_trade_record(
                    trade_id=order.ref,
                    date=order_date,
                    action='S',
                    price=order.executed.price,
                    size=abs(order.executed.size),
                    total_amount=order.executed.price * order.executed.size,
                    commission=actual_commission['total_commission'],
                    order_type='sell',
                    status=order.status
                )

            logger.info(f"【交易手续费】: {actual_commission['total_commission']:.2f}")
        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            logger.info('订单 取消/保证金不足/拒绝')

        self.order = None

    def notify_trade(self, trade):
        """
        交易状态通知，平仓完成才会触发
        :param trade: 交易对象
        """
        if not trade.isclosed:
            return

        logger.info(f'【交易完成】: 毛利润={trade.pnl:.2f}, 净利润={trade.pnlcomm:.2f}')

    def calculate_commission(self, size, price):
        """
        计算交易佣金
        :param size: 交易数量
        :param price: 交易价格
        :return: 包含总佣金的字典
        """
        # 获取当前使用的佣金模型
        comminfo = self.broker.getcommissioninfo(self.data)
        # 计算总手续费
        total_commission = comminfo._getcommission(size, price, pseudoexec=False)

        return {
            'total_commission': total_commission
        }


class StrategyManager:
    """
    策略管理器，用于管理所有可用的交易策略
    """
    def __init__(self):
        self.strategies = {}

    def register_strategy(self, strategy_name, strategy_class):
        """
        注册交易策略
        :param strategy_name: 策略名称
        :param strategy_class: 策略类
        """
        self.strategies[strategy_name] = strategy_class

    def get_strategy(self, strategy_name):
        """
        获取交易策略类
        :param strategy_name: 策略名称
        :return: 策略类
        """
        return self.strategies.get(strategy_name)

    def get_all_strategies(self):
        """
        获取所有可用的交易策略
        :return: 策略字典
        """
        return self.strategies


# 创建全局策略管理器实例
global_strategy_manager = StrategyManager()

class Strategy:
    """
    策略类，作为策略系统的入口点
    """
    def __init__(self):
        self.strategy_manager = global_strategy_manager

    def get_strategy(self, strategy_name):
        """
        获取策略类
        :param strategy_name: 策略名称
        :return: 策略类
        """
        return self.strategy_manager.get_strategy(strategy_name)

    def get_all_strategies(self):
        """
        获取所有可用策略
        :return: 策略字典
        """
        return self.strategy_manager.get_all_strategies()

    def register_strategy(self, strategy_name, strategy_class):
        """
        注册新策略
        :param strategy_name: 策略名称
        :param strategy_class: 策略类
        """
        self.strategy_manager.register_strategy(strategy_name, strategy_class)


STRATEGY_TEMPLATES = {
    "sentiment_ma": {
        "name": "情绪均线策略",
        "description": "结合行业情绪的移动平均线策略",
        "class": "UserStrategy",
        "base_params": [
            {"name": "short_period", "type": "int", "default": 5, "min": 1, "max": 50, "label": "短期均线周期"},
            {"name": "long_period", "type": "int", "default": 20, "min": 5, "max": 200, "label": "长期均线周期"},
            {"name": "sentiment_threshold", "type": "float", "default": 0.1, "min": 0, "max": 1.0, "label": "情绪阈值"},
            {"name": "sentiment_weight", "type": "float", "default": 0.3, "min": 0, "max": 1.0, "label": "情绪权重"},
            {"name": "use_sentiment_filter", "type": "bool", "default": True, "label": "启用情绪过滤"},
            {"name": "min_order_size", "type": "int", "default": 100, "min": 100, "label": "最小交易单位"},
            {"name": "max_portfolio_percent", "type": "float", "default": 0.8, "min": 0.1, "max": 1.0, "label": "最大持仓比例"},
            {"name": "max_single_buy_percent", "type": "float", "default": 0.2, "min": 0.01, "max": 1.0, "label": "单笔买入比例"},
            {"name": "max_single_sell_percent", "type": "float", "default": 0.3, "min": 0.01, "max": 1.0, "label": "单笔卖出比例"},
        ]
    }
}


def create_user_strategy_class(user_config):
    """根据用户配置动态创建策略类"""
    import backtrader as bt
    
    template_name = user_config.get("template", "sentiment_ma")
    template = STRATEGY_TEMPLATES.get(template_name, {})
    base_params = template.get("base_params", [])
    
    user_params = user_config.get("parameters", [])
    param_dict = {}
    for p in user_params:
        name = p.get("name")
        default = p.get("default")
        if name and default is not None:
            param_type = p.get("type", "int")
            if param_type == "int":
                param_dict[name] = int(default)
            elif param_type == "float":
                param_dict[name] = float(default)
            elif param_type == "bool":
                param_dict[name] = bool(default) if isinstance(default, bool) else (default == "true" or default == "True")
            else:
                param_dict[name] = default
    
    param_tuples = tuple((name, value) for name, value in param_dict.items())
    
    class DynamicUserStrategy(StrategyBase):
        params = param_tuples
        
        def __init__(self):
            super().__init__()
            import backtrader as bt
            self.short_ma = bt.indicators.SimpleMovingAverage(
                self.data.close, period=self.p.short_period
            )
            self.long_ma = bt.indicators.SimpleMovingAverage(
                self.data.close, period=self.p.long_period
            )
            self.crossover = bt.indicators.CrossOver(self.short_ma, self.long_ma)
            
        def next(self):
            if self.order:
                return
            if self.crossover > 0:
                self.order = self.buy()
            elif self.crossover < 0:
                if self.position:
                    self.order = self.sell()
    
    return DynamicUserStrategy


def get_strategy_template(template_name):
    """获取策略模板"""
    return STRATEGY_TEMPLATES.get(template_name)


def get_all_strategy_templates():
    """获取所有策略模板"""
    return STRATEGY_TEMPLATES
