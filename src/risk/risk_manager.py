import pandas as pd
import numpy as np
from scipy import stats
from typing import Dict, List, Tuple, Optional, Union
import warnings
from datetime import datetime, timedelta

warnings.filterwarnings('ignore')

class PositionSizer:
    """
    仓位管理器
    """
    
    def __init__(self, initial_capital: float = 100000.0):
        """
        初始化仓位管理器
        :param initial_capital: 初始资金
        """
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        self.max_position_size = 0.1  # 最大单票仓位比例
        self.max_sector_exposure = 0.3  # 最大行业暴露比例
        self.max_concentration_ratio = 0.5  # 最大集中度比例
    
    def set_position_limits(self, max_position_size: float = 0.1, max_sector_exposure: float = 0.3, max_concentration_ratio: float = 0.5):
        """
        设置仓位限制
        :param max_position_size: 最大单票仓位比例
        :param max_sector_exposure: 最大行业暴露比例
        :param max_concentration_ratio: 最大集中度比例
        """
        self.max_position_size = max_position_size
        self.max_sector_exposure = max_sector_exposure
        self.max_concentration_ratio = max_concentration_ratio
    
    def calculate_position_size(
        self, 
        price: float, 
        account_value: float, 
        risk_per_trade: float = 0.02,
        stop_loss_distance: float = 0.05,
        volatility: Optional[float] = None
    ) -> int:
        """
        计算仓位大小
        :param price: 当前价格
        :param account_value: 账户价值
        :param risk_per_trade: 单笔交易风险比例
        :param stop_loss_distance: 止损距离
        :param volatility: 波动率（可选，用于波动率调整）
        :return: 仓位大小（股数）
        """
        if price <= 0:
            return 0
        
        # 基于固定比例的风险管理
        risk_amount = account_value * risk_per_trade
        
        # 如果提供了止损距离，基于止损距离计算仓位
        if stop_loss_distance > 0:
            risk_per_share = price * stop_loss_distance
            position_size = risk_amount / risk_per_share
        else:
            # 如果没有止损距离，使用固定比例
            max_investment = account_value * self.max_position_size
            position_size = max_investment / price
        
        # 如果提供了波动率，进行波动率调整
        if volatility is not None and volatility > 0:
            # 波动率越高，仓位越小
            vol_adjustment = 0.1 / volatility  # 基于0.1作为基准波动率
            position_size = position_size * min(vol_adjustment, 1.0)
        
        # 确保仓位为正数且不超过最大限制
        position_size = max(0, min(position_size, account_value * self.max_position_size / price))
        
        # 转换为整数股数
        position_size = int(position_size)
        
        return position_size
    
    def check_sector_exposure(self, current_positions: Dict[str, Dict], new_position: Dict) -> bool:
        """
        检查行业暴露是否超标
        :param current_positions: 当前持仓字典 {股票代码: {quantity: 数量, price: 价格, sector: 行业}}
        :param new_position: 新增持仓 {stock: 股票代码, quantity: 数量, price: 价格, sector: 行业}
        :return: 是否允许新增持仓
        """
        # 计算当前各行业暴露
        sector_values = {}
        total_value = 0
        
        for stock, pos in current_positions.items():
            value = pos['quantity'] * pos['price']
            sector = pos.get('sector', '未知')
            sector_values[sector] = sector_values.get(sector, 0) + value
            total_value += value
        
        # 计算新增持仓价值
        new_value = new_position['quantity'] * new_position['price']
        new_sector = new_position.get('sector', '未知')
        
        # 检查新增后是否超过行业暴露限制
        new_sector_value = sector_values.get(new_sector, 0) + new_value
        new_total_value = total_value + new_value
        
        if new_total_value > 0 and (new_sector_value / new_total_value) > self.max_sector_exposure:
            return False  # 行业暴露超标
        
        return True  # 允许新增持仓

class StopLossHandler:
    """
    止损处理器
    """
    
    def __init__(self, stop_loss_pct: float = 0.05, trailing_stop: bool = False):
        """
        初始化止损处理器
        :param stop_loss_pct: 止损百分比
        :param trailing_stop: 是否使用移动止损
        """
        self.stop_loss_pct = stop_loss_pct
        self.trailing_stop = trailing_stop
        self.entry_prices = {}  # 记录入场价格 {股票代码: 价格}
        self.highest_prices = {}  # 记录最高价格（用于移动止损）
    
    def set_entry_price(self, stock: str, price: float):
        """
        设置入场价格
        :param stock: 股票代码
        :param price: 入场价格
        """
        self.entry_prices[stock] = price
        if self.trailing_stop:
            self.highest_prices[stock] = price
    
    def should_stop_loss(self, stock: str, current_price: float) -> Tuple[bool, str]:
        """
        判断是否触发止损
        :param stock: 股票代码
        :param current_price: 当前价格
        :return: (是否止损, 止损原因)
        """
        if stock not in self.entry_prices:
            return False, "未记录入场价格"
        
        entry_price = self.entry_prices[stock]
        
        if self.trailing_stop:
            # 更新最高价
            if stock not in self.highest_prices or current_price > self.highest_prices[stock]:
                self.highest_prices[stock] = current_price
            
            # 移动止损：从最高价回撤超过止损比例
            if stock in self.highest_prices:
                trailing_stop_price = self.highest_prices[stock] * (1 - self.stop_loss_pct)
                if current_price <= trailing_stop_price:
                    return True, f"移动止损触发: 从最高价{self.highest_prices[stock]:.2f}回撤{self.stop_loss_pct:.2%}"
        else:
            # 固定止损：从入场价回撤超过止损比例
            stop_price = entry_price * (1 - self.stop_loss_pct)
            if current_price <= stop_price:
                return True, f"固定止损触发: 从入场价{entry_price:.2f}回撤{self.stop_loss_pct:.2%}"
        
        return False, "未触发止损"

class VaRCalculator:
    """
    VaR计算器
    """
    
    def __init__(self, confidence_level: float = 0.95, method: str = 'historical'):
        """
        初始化VaR计算器
        :param confidence_level: 置信水平
        :param method: 计算方法 ('historical', 'variance-covariance', 'monte-carlo')
        """
        self.confidence_level = confidence_level
        self.method = method
    
    def calculate_var_historical(self, returns: pd.Series, portfolio_value: float) -> float:
        """
        历史模拟法计算VaR
        :param returns: 收益率序列
        :param portfolio_value: 投资组合价值
        :return: VaR值
        """
        if len(returns) == 0:
            return 0.0
        
        # 计算指定置信水平下的分位数
        var_quantile = 1 - self.confidence_level
        var_return = returns.quantile(var_quantile)
        
        # VaR = 投资组合价值 × (-预期最坏收益率)
        var = portfolio_value * abs(var_return)
        
        return var
    
    def calculate_var_parametric(self, returns: pd.Series, portfolio_value: float) -> float:
        """
        参数法（方差-协方差法）计算VaR
        :param returns: 收益率序列
        :param portfolio_value: 投资组合价值
        :return: VaR值
        """
        if len(returns) == 0:
            return 0.0
        
        # 计算收益率的均值和标准差
        mean_return = returns.mean()
        std_return = returns.std()
        
        if std_return == 0:
            return 0.0
        
        # 计算置信水平对应的分位数（正态分布）
        z_score = stats.norm.ppf(1 - self.confidence_level)
        
        # VaR = 投资组合价值 × (均值 - Z分数 × 标准差)
        var_return = mean_return - z_score * std_return
        var = portfolio_value * abs(var_return)
        
        return var
    
    def calculate_var(self, returns: pd.Series, portfolio_value: float) -> Dict:
        """
        计算VaR（多种方法）
        :param returns: 收益率序列
        :param portfolio_value: 投资组合价值
        :return: VaR计算结果字典
        """
        results = {}
        
        # 历史模拟法
        results['historical_var'] = self.calculate_var_historical(returns, portfolio_value)
        
        # 参数法
        results['parametric_var'] = self.calculate_var_parametric(returns, portfolio_value)
        
        # 计算CVaR（条件VaR）
        if len(returns) > 0:
            var_quantile = 1 - self.confidence_level
            threshold = returns.quantile(var_quantile)
            cvar_returns = returns[returns <= threshold]
            if len(cvar_returns) > 0:
                cvar_return = cvar_returns.mean()
                results['cvar'] = portfolio_value * abs(cvar_return)
            else:
                results['cvar'] = results['historical_var']  # 如果没有低于阈值的值，使用VaR
        
        results['confidence_level'] = self.confidence_level
        
        return results

class RiskManager:
    """
    风险管理器
    """
    
    def __init__(self, initial_capital: float = 100000.0):
        """
        初始化风险管理器
        :param initial_capital: 初始资金
        """
        self.position_sizer = PositionSizer(initial_capital)
        self.stop_loss_handler = StopLossHandler()
        self.var_calculator = VaRCalculator()
        
        # 风险限额
        self.max_daily_loss = 0.05  # 最大日亏损比例
        self.max_drawdown = 0.15    # 最大回撤比例
        self.max_leverage = 1.0     # 最大杠杆比例
        
        # 风险监控数据
        self.daily_pnl = []         # 日收益
        self.drawdown = 0.0         # 当前回撤
        self.max_equity_seen = initial_capital  # 见过的最高权益
        self.blacklist = set()      # 黑名单
        self.risk_limits = {}       # 个股风险限额
    
    def set_risk_limits(self, max_daily_loss: float = 0.05, max_drawdown: float = 0.15, max_leverage: float = 1.0):
        """
        设置风险限额
        :param max_daily_loss: 最大日亏损比例
        :param max_drawdown: 最大回撤比例
        :param max_leverage: 最大杠杆比例
        """
        self.max_daily_loss = max_daily_loss
        self.max_drawdown = max_drawdown
        self.max_leverage = max_leverage
    
    def add_to_blacklist(self, securities: Union[str, List[str]]):
        """
        添加到黑名单
        :param securities: 证券代码或代码列表
        """
        if isinstance(securities, str):
            securities = [securities]
        
        for sec in securities:
            self.blacklist.add(sec)
    
    def is_blacklisted(self, security: str) -> bool:
        """
        检查是否在黑名单中
        :param security: 证券代码
        :return: 是否在黑名单中
        """
        return security in self.blacklist
    
    def update_portfolio_value(self, current_equity: float):
        """
        更新投资组合价值
        :param current_equity: 当前权益
        """
        # 更新最大权益
        if current_equity > self.max_equity_seen:
            self.max_equity_seen = current_equity
        
        # 计算当前回撤
        if self.max_equity_seen > 0:
            self.drawdown = (self.max_equity_seen - current_equity) / self.max_equity_seen
        else:
            self.drawdown = 0.0
    
    def check_trading_restrictions(self, current_equity: float, today_pnl: float = 0.0) -> Tuple[bool, List[str]]:
        """
        检查交易限制
        :param current_equity: 当前权益
        :param today_pnl: 今日盈亏
        :return: (是否允许交易, 限制原因列表)
        """
        restrictions = []
        
        # 检查最大回撤
        if self.drawdown > self.max_drawdown:
            restrictions.append(f"超过最大回撤限制: {self.drawdown:.2%} > {self.max_drawdown:.2%}")
        
        # 检查日亏损
        if today_pnl != 0 and current_equity > 0:
            daily_loss_pct = abs(today_pnl) / (current_equity - today_pnl)
            if daily_loss_pct > self.max_daily_loss:
                restrictions.append(f"超过最大日亏损限制: {daily_loss_pct:.2%} > {self.max_daily_loss:.2%}")
        
        # 检查初始资金是否大幅下降
        initial_capital = self.position_sizer.initial_capital
        if initial_capital > 0:
            total_loss_pct = (initial_capital - current_equity) / initial_capital
            if total_loss_pct > 0.5:  # 总损失超过50%
                restrictions.append(f"总损失过大: {total_loss_pct:.2%}")
        
        allow_trading = len(restrictions) == 0
        return allow_trading, restrictions
    
    def calculate_position_with_risk(self, stock_info: Dict, account_value: float) -> int:
        """
        基于风险管理计算仓位
        :param stock_info: 股票信息 {'symbol': 代码, 'price': 价格, 'volatility': 波动率}
        :param account_value: 账户价值
        :return: 建议仓位
        """
        # 检查是否在黑名单
        if self.is_blacklisted(stock_info['symbol']):
            return 0
        
        # 使用仓位管理器计算仓位
        vol = stock_info.get('volatility', 0.2)  # 默认20%波动率
        position_size = self.position_sizer.calculate_position_size(
            price=stock_info['price'],
            account_value=account_value,
            volatility=vol
        )
        
        return position_size
    
    def should_liquidate_position(self, stock_info: Dict, current_price: float) -> Tuple[bool, str]:
        """
        判断是否应该清仓某个持仓
        :param stock_info: 股票信息
        :param current_price: 当前价格
        :return: (是否清仓, 原因)
        """
        symbol = stock_info['symbol']
        
        # 检查是否在黑名单
        if self.is_blacklisted(symbol):
            return True, "股票在黑名单中"
        
        # 检查是否触发止损
        should_stop, reason = self.stop_loss_handler.should_stop_loss(symbol, current_price)
        if should_stop:
            return True, reason
        
        # 检查基本面恶化（如果提供了相关信息）
        fundamentals = stock_info.get('fundamentals', {})
        if 'pe_ratio' in fundamentals and fundamentals['pe_ratio'] < 0:
            return True, "市盈率为负，基本面恶化"
        
        if 'debt_to_equity' in fundamentals and fundamentals['debt_to_equity'] > 1.0:
            return True, "资产负债率过高"
        
        return False, "持仓正常"
    
    def stress_test(self, portfolio_returns: pd.Series, stress_scenarios: Optional[List[Dict]] = None) -> Dict:
        """
        压力测试
        :param portfolio_returns: 投资组合收益率序列
        :param stress_scenarios: 压力情景列表
        :return: 压力测试结果
        """
        if stress_scenarios is None:
            # 默认压力情景
            stress_scenarios = [
                {'name': '市场下跌20%', 'shock': -0.20},
                {'name': '波动率增加50%', 'vol_multiplier': 1.5},
                {'name': '流动性危机', 'liquidity_shock': 0.3}  # 30%强制平仓
            ]
        
        results = {}
        
        # 基准情况
        baseline_var = self.var_calculator.calculate_var_historical(portfolio_returns, 100000)
        results['baseline_var'] = baseline_var
        
        # 对每个压力情景进行测试
        for scenario in stress_scenarios:
            scenario_name = scenario['name']
            stressed_returns = portfolio_returns.copy()
            
            if 'shock' in scenario:
                # 市场下跌情景
                stressed_returns = stressed_returns + scenario['shock']
            elif 'vol_multiplier' in scenario:
                # 波动率增加情景
                mean_return = stressed_returns.mean()
                stressed_returns = (stressed_returns - mean_return) * scenario['vol_multiplier'] + mean_return
            elif 'liquidity_shock' in scenario:
                # 流动性危机情景
                # 这里简化处理，假设收益率受到流动性影响
                stressed_returns = stressed_returns * (1 - scenario['liquidity_shock'])
            
            # 计算压力情景下的VaR
            scenario_var = self.var_calculator.calculate_var_historical(stressed_returns, 100000)
            results[f"{scenario_name}_var"] = scenario_var
            results[f"{scenario_name}_change"] = scenario_var - baseline_var
        
        return results
    
    def generate_risk_report(self, portfolio_value: float, returns: pd.Series) -> Dict:
        """
        生成风险报告
        :param portfolio_value: 投资组合价值
        :param returns: 收益率序列
        :return: 风险报告
        """
        # 计算VaR
        var_results = self.var_calculator.calculate_var(returns, portfolio_value)
        
        # 计算其他风险指标
        report = {
            'portfolio_value': portfolio_value,
            'current_drawdown': self.drawdown,
            'max_drawdown_limit': self.max_drawdown,
            'var_analysis': var_results,
            'volatility': returns.std() if len(returns) > 0 else 0,
            'sharpe_ratio': (returns.mean() / returns.std()) * np.sqrt(252) if len(returns) > 0 and returns.std() != 0 else 0,
            'blacklist_count': len(self.blacklist),
            'risk_limits': {
                'max_daily_loss': self.max_daily_loss,
                'max_leverage': self.max_leverage
            }
        }
        
        return report

def apply_risk_controls(
    signals: pd.DataFrame, 
    risk_manager: RiskManager, 
    current_positions: Dict,
    account_value: float
) -> pd.DataFrame:
    """
    应用风险控制到交易信号
    :param signals: 交易信号 DataFrame
    :param risk_manager: 风险管理器
    :param current_positions: 当前持仓
    :param account_value: 账户价值
    :return: 经风险控制调整后的信号
    """
    adjusted_signals = signals.copy()
    
    for idx, signal in signals.iterrows():
        symbol = signal.get('symbol', '')
        
        # 检查是否允许交易
        allow_trade, restrictions = risk_manager.check_trading_restrictions(account_value)
        
        if not allow_trade:
            # 如果不允许交易，取消所有信号
            adjusted_signals.loc[idx, 'position_size'] = 0
            adjusted_signals.loc[idx, 'reason'] = f"交易限制: {'; '.join(restrictions)}"
            continue
        
        if risk_manager.is_blacklisted(symbol):
            # 如果在黑名单中，取消信号
            adjusted_signals.loc[idx, 'position_size'] = 0
            adjusted_signals.loc[idx, 'reason'] = "股票在黑名单中"
            continue
        
        # 应用仓位管理
        stock_info = {
            'symbol': symbol,
            'price': signal.get('price', 0),
            'volatility': signal.get('volatility', 0.2)
        }
        
        suggested_size = risk_manager.calculate_position_with_risk(stock_info, account_value)
        adjusted_signals.loc[idx, 'position_size'] = min(suggested_size, signal.get('position_size', suggested_size))
        
        # 检查行业暴露
        if 'sector' in signal:
            new_position = {
                'stock': symbol,
                'quantity': adjusted_signals.loc[idx, 'position_size'],
                'price': signal.get('price', 0),
                'sector': signal['sector']
            }
            
            if not risk_manager.position_sizer.check_sector_exposure(current_positions, new_position):
                adjusted_signals.loc[idx, 'position_size'] = 0
                adjusted_signals.loc[idx, 'reason'] = "超过行业暴露限制"
    
    return adjusted_signals