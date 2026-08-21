
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


def parse_bool(value) -> bool:
    """Parse common bool representations from strategy JSON parameters."""
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "yes", "on")
    return bool(value)


def extract_param_value(param_dict):
    """
    从单个参数描述字典中提取 (name, value)，做类型转换。

    修复点：strategies.json 中参数写的是 ``"value"`` 键，而旧代码只读 ``"default"``，
    导致用户配置的策略参数被静默忽略，策略永远跑模板默认值。这里同时识别两个键，
    优先 ``"value"``（用户实际配置），回退 ``"default"``（模板）。

    :param param_dict: 形如 ``{"name": "short_period", "value": 5, "type": "int"}``
                      或 ``{"name": "short_period", "default": 5, "type": "int"}``
    :return: (name, value) 或 (None, None) 表示该参数缺失/无值
    """
    from .param_spec import resolve_param

    name = param_dict.get("name") if isinstance(param_dict, dict) else None
    raw_value = resolve_param(param_dict, fallback=None, prefer="value")
    if not name or raw_value is None:
        return None, None

    param_type = param_dict.get("type", "int") if isinstance(param_dict, dict) else "int"
    if param_type == "int":
        return name, int(raw_value)
    if param_type == "float":
        return name, float(raw_value)
    if param_type == "bool":
        return name, parse_bool(raw_value)
    return name, raw_value


def build_param_dict(user_config):
    """
    从用户策略配置构建参数字典 {name: value}。

    模板默认参数（STRATEGY_TEMPLATES[...]["base_params"]）作为基底，
    用户在 strategies.json 中显式配置的同名参数会覆盖模板默认值。

    :param user_config: 用户策略配置字典
    :return: {param_name: typed_value}
    """
    template_name = user_config.get("template", "sentiment_ma")
    template = STRATEGY_TEMPLATES.get(template_name, {})
    base_params = template.get("base_params", [])

    param_dict = {}
    # 先填模板默认值
    for p in base_params:
        name, value = extract_param_value(p)
        if name is not None:
            param_dict[name] = value
    # 用户配置覆盖模板默认值
    for p in user_config.get("parameters", []):
        name, value = extract_param_value(p)
        if name is not None:
            param_dict[name] = value
    return param_dict


def create_user_strategy_class(user_config, sentiment_series=None, sentiment_sector=None):
    """
    根据用户配置动态创建策略类。

    :param user_config: 用户策略配置字典
    :param sentiment_series: 可选，行业情绪时间序列（pd.Series, index=快照日期），
                             用于情绪过滤。为 None 时回退为关闭情绪过滤（中性 0）。
    :param sentiment_sector: sentiment_series 对应的行业名。为 None 时不应用过滤。
    :return: 策略类
    """
    import backtrader as bt

    param_dict = build_param_dict(user_config)
    param_tuples = tuple((name, value) for name, value in param_dict.items())

    # 通过闭包把情绪数据传入策略实例（backtrader 的 params 不便直接放 pd.Series）
    _sentiment_series = sentiment_series
    _sentiment_sector = sentiment_sector
    
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

        def _sentiment_at(self, current_date):
            """
            取截至 current_date 最近的情绪快照分数（避免未来函数）。
            无可用快照时返回 0.0（中性，等价于关闭过滤）。
            """
            if _sentiment_series is None or _sentiment_sector is None:
                return 0.0
            try:
                prior = _sentiment_series[_sentiment_series.index <= current_date]
                if prior.empty:
                    return 0.0
                return float(prior.iloc[-1])
            except Exception:
                return 0.0

        def next(self):
            if self.order:
                return

            use_filter = getattr(self.p, "use_sentiment_filter", False)
            threshold = getattr(self.p, "sentiment_threshold", 0.0)
            weight = getattr(self.p, "sentiment_weight", 1.0)

            if self.crossover > 0:
                # 金叉 -> 买入意图
                if use_filter:
                    # 取当日最近情绪快照，要求情绪 >= -threshold（非过度悲观）
                    current_date = self.data.datetime.date(0)
                    score = self._sentiment_at(current_date)
                    # 软加权：score 越低越倾向于放弃这笔买入
                    if score < -threshold and weight >= 1.0:
                        return  # 完全过滤
                self.order = self.buy()
            elif self.crossover < 0:
                if self.position:
                    if use_filter:
                        current_date = self.data.datetime.date(0)
                        score = self._sentiment_at(current_date)
                        if score > threshold and weight >= 1.0:
                            return  # 情绪仍偏强，过滤卖出信号
                    self.order = self.sell()

    return DynamicUserStrategy


def get_strategy_template(template_name):
    """获取策略模板"""
    return STRATEGY_TEMPLATES.get(template_name)


def get_all_strategy_templates():
    """获取所有策略模板"""
    return STRATEGY_TEMPLATES
