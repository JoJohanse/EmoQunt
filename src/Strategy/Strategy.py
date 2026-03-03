
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


class SimpleMAStrategy(StrategyBase):
    """
    简单移动平均线策略示例
    当短期均线上穿长期均线时买入，当短期均线下穿长期均线时卖出
    """
    params = (
        ('short_period', 5),   # 短期均线周期
        ('long_period', 20),    # 长期均线周期
    )

    def __init__(self):
        """
        初始化策略
        """
        super().__init__()
        # 计算移动平均线
        self.short_ma = bt.indicators.SimpleMovingAverage(self.data.close, period=self.p.short_period)
        self.long_ma = bt.indicators.SimpleMovingAverage(self.data.close, period=self.p.long_period)
        # 计算均线交叉信号
        self.crossover = bt.indicators.CrossOver(self.short_ma, self.long_ma)

    def next(self):
        """
        每个时间步执行的逻辑
        """
        # 检查是否有未完成的订单
        if self.order:
            return

        # 检查买入信号（短期均线上穿长期均线）
        if self.crossover > 0:
            logger.info(f'买入信号: 价格={self.data.close[0]}, 短期均线={self.short_ma[0]}, 长期均线={self.long_ma[0]}')
            self.trading_strategy_buy()
            self.buy_signals_count += 1
        # 检查卖出信号（短期均线下穿长期均线）
        elif self.crossover < 0:
            logger.info(f'卖出信号: 价格={self.data.close[0]}, 短期均线={self.short_ma[0]}, 长期均线={self.long_ma[0]}')
            self.trading_strategy_sell()
            self.sell_signals_count += 1

    def trading_strategy_buy(self):
        """
        具体的买入策略实现
        """
        # 计算可用于购买的资金
        total_asset_value = self.broker.getvalue()
        available_cash = self.broker.getcash()
        max_single_trade_cash = total_asset_value * self.max_single_buy_percent
        max_portfolio_value = total_asset_value * self.max_portfolio_percent
        
        # 计算实际可用购买金额
        usable_cash = min(available_cash, max_single_trade_cash, max_portfolio_value)

        # 计算可购买的股数
        price = self.data.close[0]
        if price > 0 and usable_cash >= price * self.min_order_size:
            # 计算基于可用资金的股数
            shares_based_on_cash = usable_cash // price
            # 确保股数为最小交易单位的整数倍
            buy_size = max(shares_based_on_cash, self.min_order_size)
            buy_size = buy_size // self.min_order_size * self.min_order_size
            
            if buy_size >= self.min_order_size:
                logger.info(
                    f"【买入挂单】: 可用资金={available_cash:.2f}, 总资产={total_asset_value:.2f}, 买入股数={buy_size}, "
                    f"价格={price:.2f}, 预计花费={buy_size * price:.2f}"
                )
                # 计算手续费
                trade_commission = self.calculate_commission(buy_size, price)
                if trade_commission:
                    logger.info(f"【预计手续费】: {trade_commission['total_commission']:.2f}")
                self.order = self.buy(size=buy_size)
            else:
                logger.info(f"资金不足，无法购买至少{self.min_order_size}股")
        else:
            logger.info(f"资金不足，可用资金={usable_cash:.2f}，至少需要{price * self.min_order_size:.2f}")

    def trading_strategy_sell(self):
        """
        具体的卖出策略实现
        """
        # 有持仓时才卖出
        if self.position:
            current_position_size = self.position.size
            # 确保卖出股数为最小交易单位的整数倍
            sell_size = current_position_size // self.min_order_size * self.min_order_size
            
            if sell_size >= self.min_order_size:
                price = self.data.close[0]
                logger.info(
                    f"【卖出挂单】: 当前持仓={current_position_size}, 卖出股数={sell_size}, "
                    f"价格={price:.2f}, 预计收入={sell_size * price:.2f}"
                )
                # 计算手续费
                trade_commission = self.calculate_commission(sell_size, price)
                if trade_commission:
                    logger.info(f"【预计手续费】: {trade_commission['total_commission']:.2f}")
                self.order = self.sell(size=sell_size)
            else:
                logger.info(f"持仓不足，无法卖出至少{self.min_order_size}股")
        else:
            logger.info("当前无持仓，无法卖出")


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

# 注册默认策略
global_strategy_manager.register_strategy('simple_ma', SimpleMAStrategy)

# 尝试注册情感分析策略
try:
    from .SentimentMAStrategy import SentimentMAStrategy
    global_strategy_manager.register_strategy('sentiment_ma', SentimentMAStrategy)
except ImportError as e:
    print(f"导入情感分析策略失败: {e}")


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
