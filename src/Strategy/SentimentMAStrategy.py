import backtrader as bt
from .Strategy import StrategyBase, logger
import os
import json


class SentimentMAStrategy(StrategyBase):
    """
    情绪因子结合移动平均线策略
    
    策略逻辑：
    1. 使用传统技术指标（均线交叉）作为基础交易信号
    2. 结合行业情绪得分进行过滤和增强
    3. 当情绪得分为正时，增强买入信号，减弱卖出信号
    4. 当情绪得分为负时，减弱买入信号，增强卖出信号
    
    情绪数据来源：
    - 从 nes_data/sector_sentiment.json 读取最新的行业情绪得分
    - 根据股票所属行业的 sentiment_score 调整交易信号强度
    """
    
    params = (
        ('short_period', 5),      # 短期均线周期
        ('long_period', 20),      # 长期均线周期
        ('sentiment_threshold', 0.1),  # 情绪阈值，绝对值大于此值才考虑情绪因子
        ('sentiment_weight', 0.3),     # 情绪因子权重（0-1，0 表示完全忽略情绪）
        ('use_sentiment_filter', True), # 是否使用情绪过滤
    )
    
    def __init__(self):
        """
        初始化策略
        """
        super().__init__()
        
        # 计算移动平均线
        self.short_ma = bt.indicators.SimpleMovingAverage(
            self.data.close, period=self.p.short_period
        )
        self.long_ma = bt.indicators.SimpleMovingAverage(
            self.data.close, period=self.p.long_period
        )
        
        # 计算均线交叉信号
        self.crossover = bt.indicators.CrossOver(self.short_ma, self.long_ma)
        
        # RSI 指标用于辅助判断
        self.rsi = bt.indicators.RSI(self.data.close, period=14)
        
        # 加载情绪数据
        self.sector_sentiment = self._load_sector_sentiment()
        
        # 获取当前股票所属行业（需要从外部传入或通过其他方式获取）
        self.stock_sector = self._get_stock_sector()
        
        # 当前股票的情绪得分
        self.current_sentiment_score = self._get_current_sentiment()
        
        logger.info(f"股票行业：{self.stock_sector}, 情绪得分：{self.current_sentiment_score}")
    
    def _load_sector_sentiment(self):
        """
        加载行业情绪得分数据
        :return: 行业情绪得得分字典
        """
        try:
            # 尝试从常见路径加载情绪数据
            possible_paths = [
                os.path.join(os.path.dirname(__file__), '..', '..', '..', 'nes_data', 'sector_sentiment.json'),
                os.path.join(os.path.dirname(__file__), '..', '..', 'nes_data', 'sector_sentiment.json'),
                r'd:\workplace\codeplace\junkcode\Qdt_test\nes_data\sector_sentiment.json',
            ]
            
            for path in possible_paths:
                if os.path.exists(path):
                    with open(path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        logger.info(f"成功加载情绪数据：{path}")
                        return data.get('sectors', {})
            
            logger.warning("未找到情绪数据文件，将不使用情绪因子")
            return {}
            
        except Exception as e:
            logger.error(f"加载情绪数据失败：{e}")
            return {}
    
    def _get_stock_sector(self):
        """
        获取股票所属行业
        这里需要根据实际情况实现，目前返回 None
        实际使用时应该：
        1. 通过参数传入行业信息
        2. 或者从外部数据源查询（如股票基本信息）
        
        :return: 行业名称
        """
        # TODO: 实现股票行业获取逻辑
        # 现在尝试从数据代码中获取（简化版本）
        if hasattr(self, 'data') and hasattr(self.data, '_name'):
            stock_code = self.data._name
            # 这里可以根据股票代码查询行业
            # 现在返回 None，使用默认情绪
            return None
        
        return None
    
    def _get_current_sentiment(self):
        """
        获取当前股票的情绪得分
        :return: 情绪得分（-1 到 1 之间）
        """
        if not self.stock_sector or self.stock_sector not in self.sector_sentiment:
            # 如果没有行业信息或该行业不在情绪数据中，返回中性情绪
            return 0.0
        
        sector_data = self.sector_sentiment[self.stock_sector]
        return sector_data.get('score', 0.0)
    
    def _adjust_signal_by_sentiment(self, base_signal):
        """
        根据情绪调整交易信号强度
        :param base_signal: 基础信号（来自技术指标）
        :return: 调整后的信号强度
        """
        if not self.p.use_sentiment_filter:
            return base_signal
        
        # 计算情绪调整因子
        sentiment_adjustment = self.current_sentiment_score * self.p.sentiment_weight
        
        # 如果是买入信号（crossover > 0）
        if base_signal > 0:
            # 正面情绪增强买入信号，负面情绪减弱买入信号
            adjusted_signal = base_signal * (1 + sentiment_adjustment)
        
        # 如果是卖出信号（crossover < 0）
        elif base_signal < 0:
            # 正面情绪减弱卖出信号，负面情绪增强卖出信号
            adjusted_signal = base_signal * (1 - sentiment_adjustment)
        
        else:
            adjusted_signal = 0
        
        return adjusted_signal
    
    def _should_buy(self):
        """
        判断是否应该买入
        :return: (是否买入，买入强度)
        """
        # 基础均线交叉买入信号
        if self.crossover <= 0:
            return False, 0
        
        # 检查 RSI 是否超买（> 70）
        if self.rsi[0] > 70:
            logger.info(f"RSI 超买 ({self.rsi[0]:.2f})，暂缓买入")
            return False, 0
        
        # 计算调整后的信号
        adjusted_signal = self._adjust_signal_by_sentiment(self.crossover[0])
        
        # 如果调整后信号仍然为正，则买入
        if adjusted_signal > 0:
            # 计算买入强度（考虑情绪）
            buy_strength = min(1.0, abs(adjusted_signal) / 10.0)
            
            # 情绪得分过低时可能不买入
            if self.p.use_sentiment_filter and self.current_sentiment_score < -self.p.sentiment_threshold:
                logger.info(f"情绪过于负面 ({self.current_sentiment_score:.2f})，取消买入")
                return False, 0
            
            return True, buy_strength
        
        return False, 0
    
    def _should_sell(self):
        """
        判断是否应该卖出
        :return: (是否卖出，卖出强度)
        """
        # 基础均线交叉卖出信号
        if self.crossover >= 0:
            return False, 0
        
        # 检查 RSI 是否超卖（< 30）
        if self.rsi[0] < 30:
            logger.info(f"RSI 超卖 ({self.rsi[0]:.2f})，暂缓卖出")
            return False, 0
        
        # 计算调整后的信号
        adjusted_signal = self._adjust_signal_by_sentiment(self.crossover[0])
        
        # 如果调整后信号仍然为负，则卖出
        if adjusted_signal < 0:
            # 计算卖出强度
            sell_strength = min(1.0, abs(adjusted_signal) / 10.0)
            
            # 情绪得分过高时可能不卖出
            if self.p.use_sentiment_filter and self.current_sentiment_score > self.p.sentiment_threshold:
                logger.info(f"情绪过于正面 ({self.current_sentiment_score:.2f})，取消卖出")
                return False, 0
            
            return True, sell_strength
        
        return False, 0
    
    def next(self):
        """
        每个时间步执行的逻辑
        """
        # 检查是否有未完成的订单
        if self.order:
            return
        
        # 检查买入信号
        should_buy, buy_strength = self._should_buy()
        if should_buy:
            logger.info(
                f'【买入信号】: 价格={self.data.close[0]:.2f}, '
                f'短期均线={self.short_ma[0]:.2f}, 长期均线={self.long_ma[0]:.2f}, '
                f'情绪得分={self.current_sentiment_score:.2f}, 买入强度={buy_strength:.2f}'
            )
            self.trading_strategy_buy(buy_strength)
            self.buy_signals_count += 1
        
        # 检查卖出信号
        should_sell, sell_strength = self._should_sell()
        if should_sell:
            logger.info(
                f'【卖出信号】: 价格={self.data.close[0]:.2f}, '
                f'短期均线={self.short_ma[0]:.2f}, 长期均线={self.long_ma[0]:.2f}, '
                f'情绪得分={self.current_sentiment_score:.2f}, 卖出强度={sell_strength:.2f}'
            )
            self.trading_strategy_sell(sell_strength)
            self.sell_signals_count += 1
    
    def trading_strategy_buy(self, strength=1.0):
        """
        具体的买入策略实现
        :param strength: 买入强度（0-1），考虑情绪因子后的调整结果
        """
        # 计算可用于购买的资金
        total_asset_value = self.broker.getvalue()
        available_cash = self.broker.getcash()
        max_single_trade_cash = total_asset_value * self.max_single_buy_percent
        max_portfolio_value = total_asset_value * self.max_portfolio_percent
        
        # 计算实际可用购买金额
        usable_cash = min(available_cash, max_single_trade_cash, max_portfolio_value)
        
        # 根据情绪强度调整购买金额
        if strength < 1.0:
            usable_cash *= strength
            logger.info(f"情绪调整：买入强度={strength:.2f}, 调整后金额={usable_cash:.2f}")
        
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
                    f"【买入挂单】: 可用资金={available_cash:.2f}, 总资产={total_asset_value:.2f}, "
                    f"买入股数={buy_size}, 价格={price:.2f}, 预计花费={buy_size * price:.2f}"
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
    
    def trading_strategy_sell(self, strength=1.0):
        """
        具体的卖出策略实现
        :param strength: 卖出强度（0-1），考虑情绪因子后的调整结果
        """
        # 有持仓时才卖出
        if self.position:
            current_position_size = self.position.size
            
            # 根据情绪强度调整卖出比例
            if strength < 1.0:
                # 情绪正面时，只卖出一部分
                sell_size = int(current_position_size * strength)
                # 确保为最小交易单位的整数倍
                sell_size = sell_size // self.min_order_size * self.min_order_size
                # 至少卖出最小单位
                sell_size = max(sell_size, self.min_order_size)
            else:
                # 全部卖出
                sell_size = current_position_size // self.min_order_size * self.min_order_size
            
            if sell_size >= self.min_order_size and sell_size <= current_position_size:
                price = self.data.close[0]
                logger.info(
                    f"【卖出挂单】: 当前持仓={current_position_size}, 卖出股数={sell_size}, "
                    f"价格={price:.2f}, 预计收入={sell_size * price:.2f}, 卖出强度={strength:.2f}"
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
