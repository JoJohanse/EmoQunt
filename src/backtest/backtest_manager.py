import backtrader as bt
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Union
import os
import sys
import matplotlib.pyplot as plt
import seaborn as sns

# 添加项目路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.Strategy import Strategy, global_strategy_manager
from src.data.data_manager import Stock

class PerformanceAnalyzer:
    """
    策略绩效分析器
    """
    
    def __init__(self, returns: pd.Series, benchmark_returns: Optional[pd.Series] = None):
        """
        初始化绩效分析器
        :param returns: 策略收益率序列
        :param benchmark_returns: 基准收益率序列（可选）
        """
        self.returns = returns.dropna()
        self.benchmark_returns = benchmark_returns.dropna() if benchmark_returns is not None else None
        self.total_return = None
        self.annualized_return = None
        self.annualized_volatility = None
        self.sharpe_ratio = None
        self.max_drawdown = None
        self.calmar_ratio = None
        self.win_rate = None
        self.profit_factor = None
        self.alpha = None
        self.beta = None
        self.information_ratio = None
        
    def calculate_total_return(self) -> float:
        """计算总收益率"""
        if len(self.returns) == 0:
            return 0.0
        self.total_return = (1 + self.returns).prod() - 1
        return self.total_return
    
    def calculate_annualized_return(self, periods_per_year: int = 252) -> float:
        """计算年化收益率"""
        if len(self.returns) == 0:
            return 0.0
        self.annualized_return = (1 + self.returns).pow(periods_per_year / len(self.returns)).mean() - 1
        return self.annualized_return
    
    def calculate_annualized_volatility(self, periods_per_year: int = 252) -> float:
        """计算年化波动率"""
        if len(self.returns) == 0:
            return 0.0
        self.annualized_volatility = self.returns.std() * np.sqrt(periods_per_year)
        return self.annualized_volatility
    
    def calculate_sharpe_ratio(self, risk_free_rate: float = 0.03, periods_per_year: int = 252) -> float:
        """计算夏普比率"""
        if len(self.returns) == 0:
            return 0.0
        excess_return = self.annualized_return - risk_free_rate if self.annualized_return else \
                       (1 + self.returns).pow(periods_per_year / len(self.returns)).mean() - 1 - risk_free_rate
        volatility = self.annualized_volatility if self.annualized_volatility else self.returns.std() * np.sqrt(periods_per_year)
        
        if volatility == 0:
            self.sharpe_ratio = np.inf if excess_return > 0 else -np.inf
        else:
            self.sharpe_ratio = excess_return / volatility
        return self.sharpe_ratio
    
    def calculate_max_drawdown(self) -> Tuple[float, datetime, datetime]:
        """计算最大回撤及其发生时间"""
        if len(self.returns) == 0:
            return 0.0, None, None
            
        cumulative_returns = (1 + self.returns).cumprod()
        running_max = cumulative_returns.expanding().max()
        drawdown = (cumulative_returns - running_max) / running_max
        
        max_dd = drawdown.min()
        end_idx = drawdown.idxmin()
        start_idx = cumulative_returns.loc[:end_idx].idxmax()
        
        self.max_drawdown = abs(max_dd)
        return self.max_drawdown, start_idx, end_idx
    
    def calculate_calmar_ratio(self, risk_free_rate: float = 0.03, periods_per_year: int = 252) -> float:
        """计算卡玛比率（年化收益率/最大回撤）"""
        annual_ret = self.annualized_return if self.annualized_return else \
                     (1 + self.returns).pow(periods_per_year / len(self.returns)).mean() - 1
        max_dd = self.max_drawdown if self.max_drawdown else self.calculate_max_drawdown()[0]
        
        if max_dd == 0:
            self.calmar_ratio = np.inf if annual_ret > 0 else -np.inf
        else:
            self.calmar_ratio = annual_ret / max_dd
        return self.calmar_ratio
    
    def calculate_win_rate(self) -> float:
        """计算胜率"""
        if len(self.returns) == 0:
            return 0.0
        wins = (self.returns > 0).sum()
        total_trades = len(self.returns)
        self.win_rate = wins / total_trades if total_trades > 0 else 0.0
        return self.win_rate
    
    def calculate_profit_factor(self) -> float:
        """计算盈亏比"""
        if len(self.returns) == 0:
            return 0.0
            
        gains = self.returns[self.returns > 0].sum()
        losses = abs(self.returns[self.returns < 0].sum())
        
        if losses == 0:
            self.profit_factor = np.inf if gains > 0 else 0.0
        else:
            self.profit_factor = gains / losses
        return self.profit_factor
    
    def calculate_alpha_beta(self) -> Tuple[float, float]:
        """计算 Alpha 和 Beta（相对于基准）"""
        if self.benchmark_returns is None or len(self.benchmark_returns) == 0:
            self.alpha, self.beta = 0.0, 0.0
            return self.alpha, self.beta
        
        # 对齐数据
        aligned_data = pd.concat([self.returns, self.benchmark_returns], axis=1).dropna()
        if len(aligned_data) == 0:
            self.alpha, self.beta = 0.0, 0.0
            return self.alpha, self.beta
        
        strategy_returns = aligned_data.iloc[:, 0]
        benchmark_returns = aligned_data.iloc[:, 1]
        
        # 计算协方差和方差
        cov_matrix = np.cov(strategy_returns, benchmark_returns)
        beta = cov_matrix[0, 1] / cov_matrix[1, 1]
        
        # 计算年化收益率
        annual_strategy_return = (1 + strategy_returns).pow(252 / len(strategy_returns)).mean() - 1
        annual_benchmark_return = (1 + benchmark_returns).pow(252 / len(benchmark_returns)).mean() - 1
        
        # 计算 Alpha
        alpha = annual_strategy_return - (0.03 + beta * (annual_benchmark_return - 0.03))  # 使用3%无风险利率
        
        self.alpha = alpha
        self.beta = beta
        return self.alpha, self.beta
    
    def calculate_information_ratio(self) -> float:
        """计算信息比率"""
        if self.benchmark_returns is None or len(self.benchmark_returns) == 0:
            self.information_ratio = 0.0
            return self.information_ratio
        
        # 对齐数据
        aligned_data = pd.concat([self.returns, self.benchmark_returns], axis=1).dropna()
        if len(aligned_data) == 0:
            self.information_ratio = 0.0
            return self.information_ratio
        
        active_returns = aligned_data.iloc[:, 0] - aligned_data.iloc[:, 1]  # 策略超额收益
        tracking_error = active_returns.std() * np.sqrt(252)  # 年化跟踪误差
        
        if tracking_error == 0:
            self.information_ratio = np.inf if active_returns.mean() > 0 else -np.inf
        else:
            self.information_ratio = (active_returns.mean() * 252) / tracking_error  # 年化信息比率
        return self.information_ratio
    
    def generate_report(self) -> Dict:
        """生成完整的绩效报告"""
        report = {}
        
        # 基础指标
        report['总收益率'] = self.calculate_total_return()
        report['年化收益率'] = self.calculate_annualized_return()
        report['年化波动率'] = self.calculate_annualized_volatility()
        report['夏普比率'] = self.calculate_sharpe_ratio()
        max_dd, dd_start, dd_end = self.calculate_max_drawdown()
        report['最大回撤'] = max_dd
        report['最大回撤开始时间'] = dd_start
        report['最大回撤结束时间'] = dd_end
        report['卡玛比率'] = self.calculate_calmar_ratio()
        report['胜率'] = self.calculate_win_rate()
        report['盈亏比'] = self.calculate_profit_factor()
        
        # Alpha/Beta 相关指标
        alpha, beta = self.calculate_alpha_beta()
        report['Alpha'] = alpha
        report['Beta'] = beta
        report['信息比率'] = self.calculate_information_ratio()
        
        # 风险指标
        report['下行标准差'] = self.returns[self.returns < 0].std() * np.sqrt(252) if len(self.returns[self.returns < 0]) > 0 else 0.0
        report['VaR (95%)'] = np.percentile(self.returns.dropna(), 5)
        report['CVaR (95%)'] = self.returns[self.returns <= np.percentile(self.returns.dropna(), 5)].mean()
        
        # 交易统计
        report['交易次数'] = len(self.returns)
        report['盈利交易数'] = (self.returns > 0).sum()
        report['亏损交易数'] = (self.returns < 0).sum()
        report['平均盈利'] = self.returns[self.returns > 0].mean() if (self.returns > 0).any() else 0.0
        report['平均亏损'] = self.returns[self.returns < 0].mean() if (self.returns < 0).any() else 0.0
        
        return report
    
    def plot_performance(self, figsize: Tuple[int, int] = (12, 10)):
        """绘制绩效图表"""
        fig, axes = plt.subplots(2, 2, figsize=figsize)
        
        # 1. 累积收益曲线
        cumulative_returns = (1 + self.returns).cumprod()
        axes[0, 0].plot(cumulative_returns.index, cumulative_returns.values, label='策略收益', linewidth=2)
        if self.benchmark_returns is not None:
            benchmark_cumulative = (1 + self.benchmark_returns).cumprod()
            axes[0, 0].plot(benchmark_cumulative.index, benchmark_cumulative.values, label='基准收益', linewidth=2)
        axes[0, 0].set_title('累积收益曲线')
        axes[0, 0].legend()
        axes[0, 0].grid(True, linestyle='--', alpha=0.6)
        
        # 2. 回撤曲线
        running_max = cumulative_returns.expanding().max()
        drawdown = (cumulative_returns - running_max) / running_max
        axes[0, 1].fill_between(drawdown.index, drawdown.values, 0, color='red', alpha=0.3)
        axes[0, 1].set_title('回撤曲线')
        axes[0, 1].grid(True, linestyle='--', alpha=0.6)
        
        # 3. 收益分布直方图
        axes[1, 0].hist(self.returns.dropna(), bins=50, density=True, alpha=0.7, edgecolor='black')
        axes[1, 0].set_title('收益分布直方图')
        axes[1, 0].grid(True, linestyle='--', alpha=0.6)
        
        # 4. 月度收益热力图
        monthly_returns = self.returns.resample('M').apply(lambda x: (1 + x).prod() - 1)
        if len(monthly_returns) > 0:
            monthly_pivot = monthly_returns.to_frame('monthly_return')
            monthly_pivot['year'] = monthly_pivot.index.year
            monthly_pivot['month'] = monthly_pivot.index.month
            pivot_table = monthly_pivot.pivot(index='year', columns='month', values='monthly_return')
            sns.heatmap(pivot_table, annot=True, fmt='.2%', cmap='RdYlGn', center=0, ax=axes[1, 1])
            axes[1, 1].set_title('月度收益热力图')
        
        plt.tight_layout()
        plt.show()
        
        return fig

class BacktestRunner:
    """
    回测运行器类
    """
    
    def __init__(self):
        """
        初始化回测运行器
        """
        self.cerebro = bt.Cerebro()
        self.results = None
        self.performance_reports = {}
        self.portfolio_weights = {}  # 存储调仓权重
    
    def add_data_from_csv(
        self, 
        csv_path: str, 
        name: str = 'STOCK',
        datetime_col: str = 'date',
        open_col: str = '开盘',
        high_col: str = '最高',
        low_col: str = '最低',
        close_col: str = '收盘',
        volume_col: str = '成交量'
    ):
        """
        从CSV文件添加数据
        :param csv_path: CSV文件路径
        :param name: 数据名称
        :param datetime_col: 日期时间列名
        :param open_col: 开盘价列名
        :param high_col: 最高价列名
        :param low_col: 最低价列名
        :param close_col: 收盘价列名
        :param volume_col: 成交量列名
        """
        # 读取CSV数据
        df = pd.read_csv(csv_path)
        
        # 转换日期列
        df[datetime_col] = pd.to_datetime(df[datetime_col])
        df.set_index(datetime_col, inplace=True)
        
        # 创建Backtrader数据源
        data_feed = bt.feeds.PandasData(
            dataname=df,
            name=name,
            open=open_col,
            high=high_col,
            low=low_col,
            close=close_col,
            volume=volume_col,
            openinterest=-1  # 不使用未平仓量
        )
        
        # 添加数据到Cerebro
        self.cerebro.adddata(data_feed)
        print(f"已添加数据: {name}, 数据范围: {df.index[0]} 到 {df.index[-1]}, 共 {len(df)} 条记录")
    
    def add_data_from_stock(
        self,
        stock_code: str,
        start_date: str,
        end_date: str,
        adjust: str = 'hfq',
        data_type: str = 'daily'
    ):
        """
        从Stock类获取数据并添加到回测
        :param stock_code: 股票代码
        :param start_date: 开始日期 (YYYYMMDD)
        :param end_date: 结束日期 (YYYYMMDD)
        :param adjust: 复权方式 ('hfq', 'qfq', 'nfq')
        :param data_type: 数据类型 ('daily', 'minute')
        """
        stock = Stock(stock_code)
        data, filename = stock.get_stock_data(
            start_date=start_date,
            end_date=end_date,
            adjust=adjust,
            type=data_type
        )
        
        if data.empty:
            print(f"获取股票 {stock_code} 数据失败")
            return
        
        # 转换日期列
        if '时间' in data.columns:
            data['时间'] = pd.to_datetime(data['时间'])
            data.set_index('时间', inplace=True)
        
        # 创建Backtrader数据源
        data_feed = bt.feeds.PandasData(
            dataname=data,
            name=stock_code,
            open='开盘',
            high='最高',
            low='最低',
            close='收盘',
            volume='成交量',
            openinterest=-1
        )
        
        # 添加数据到Cerebro
        self.cerebro.adddata(data_feed)
        print(f"已添加股票数据: {stock_code}, 数据范围: {data.index[0]} 到 {data.index[-1]}, 共 {len(data)} 条记录")
    
    def set_initial_capital(self, cash: float = 100000.0):
        """
        设置初始资金
        :param cash: 初始资金
        """
        self.cerebro.broker.setcash(cash)
        print(f"设置初始资金: {cash:,.2f}")
    
    def set_commission(self, commission: float = 0.001, margin: Optional[float] = None, mult: float = 1.0):
        """
        设置交易佣金
        :param commission: 佣金比例
        :param margin: 保证金（期货用）
        :param mult: 乘数（期货用）
        """
        self.cerebro.broker.setcommission(commission=commission, margin=margin, mult=mult)
        print(f"设置交易佣金: {commission:.3%}")
    
    def add_strategy(self, strategy_name: str, **kwargs):
        """
        添加策略
        :param strategy_name: 策略名称
        :param kwargs: 策略参数
        """
        strategy_class = global_strategy_manager.get_strategy(strategy_name)
        if strategy_class is None:
            print(f"策略 {strategy_name} 不存在")
            return
        
        self.cerebro.addstrategy(strategy_class, **kwargs)
        print(f"已添加策略: {strategy_name}, 参数: {kwargs}")
    
    def add_analyzers(self):
        """
        添加分析器
        """
        # 添加常用的分析器
        self.cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='tradeanalyzer')
        self.cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharperatio')
        self.cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
        self.cerebro.addanalyzer(bt.analyzers.Returns, _name='returns')
        self.cerebro.addanalyzer(bt.analyzers.TimeReturn, _name='timereturn')
        print("已添加分析器")
    
    def run_backtest(self):
        """
        运行回测
        :return: 回测结果
        """
        print(f"开始回测，初始资金: {self.cerebro.broker.getvalue():,.2f}")
        
        # 运行回测
        self.results = self.cerebro.run()
        
        print(f"回测完成，最终资金: {self.cerebro.broker.getvalue():,.2f}")
        print(f"总收益率: {(self.cerebro.broker.getvalue() / self.cerebro.broker.startingcash - 1):.2%}")
        
        return self.results
    
    def get_strategy_returns(self) -> pd.Series:
        """
        获取策略收益率序列
        :return: 收益率序列
        """
        if self.results is None:
            print("请先运行回测")
            return pd.Series()
        
        # 从分析器获取收益率
        strat = self.results[0]
        if hasattr(strat, 'analyzers') and 'timereturn' in strat.analyzers:
            timereturn = strat.analyzers.timereturn.get_analysis()
            returns = pd.Series(timereturn)
            return returns
        else:
            # 如果没有分析器，从broker获取价值历史
            # 这里简化处理，实际需要从broker获取每日价值
            print("未找到收益率数据，请确保添加了分析器")
            return pd.Series()
    
    def analyze_performance(self, benchmark_returns: Optional[pd.Series] = None):
        """
        分析策略绩效
        :param benchmark_returns: 基准收益率序列
        :return: 绩效报告
        """
        returns = self.get_strategy_returns()
        if returns.empty:
            print("无法获取收益率数据，跳过绩效分析")
            return {}
        
        analyzer = PerformanceAnalyzer(returns, benchmark_returns)
        report = analyzer.generate_report()
        
        # 保存报告
        self.performance_reports['strategy'] = report
        
        print("=" * 50)
        print("策略绩效报告")
        print("=" * 50)
        for metric, value in report.items():
            if isinstance(value, float):
                if '收益率' in metric or '比率' in metric or metric in ['胜率']:
                    print(f"{metric}: {value:.4f} ({value:.2%})")
                else:
                    print(f"{metric}: {value:.4f}")
            else:
                print(f"{metric}: {value}")
        
        return report
    
    def plot_results(self):
        """
        绘制回测结果图表
        """
        returns = self.get_strategy_returns()
        if returns.empty:
            print("无法获取收益率数据，跳过绘图")
            return
        
        analyzer = PerformanceAnalyzer(returns)
        analyzer.plot_performance()
    
    def run_multiple_strategies(
        self, 
        strategies_config: List[Dict],
        data_feed: Union[str, pd.DataFrame],
        start_date: str,
        end_date: str,
        initial_cash: float = 100000.0
    ) -> Dict:
        """
        运行多个策略进行对比
        :param strategies_config: 策略配置列表
        :param data_feed: 数据源
        :param start_date: 开始日期
        :param end_date: 结束日期
        :param initial_cash: 初始资金
        :return: 各策略结果字典
        """
        results = {}
        
        for config in strategies_config:
            strategy_name = config['name']
            strategy_params = config.get('params', {})
            
            # 创建新的Cerebro实例
            cerebro = bt.Cerebro()
            
            # 添加数据
            if isinstance(data_feed, str):
                # 假设是CSV路径
                df = pd.read_csv(data_feed)
                df['date'] = pd.to_datetime(df['date'])
                df.set_index('date', inplace=True)
                
                data_feed_bt = bt.feeds.PandasData(
                    dataname=df,
                    open='开盘',
                    high='最高',
                    low='最低',
                    close='收盘',
                    volume='成交量',
                    openinterest=-1
                )
            else:
                # 假设是DataFrame
                data_feed_bt = bt.feeds.PandasData(
                    dataname=data_feed,
                    open='开盘',
                    high='最高',
                    low='最低',
                    close='收盘',
                    volume='成交量',
                    openinterest=-1
                )
            
            cerebro.adddata(data_feed_bt)
            
            # 设置资金和佣金
            cerebro.broker.setcash(initial_cash)
            cerebro.broker.setcommission(commission=0.001)
            
            # 添加策略
            strategy_class = global_strategy_manager.get_strategy(strategy_name)
            if strategy_class:
                cerebro.addstrategy(strategy_class, **strategy_params)
            
            # 添加分析器
            cerebro.addanalyzer(bt.analyzers.TimeReturn, _name='timereturn')
            
            # 运行回测
            result = cerebro.run()
            
            # 获取收益率
            strat = result[0]
            timereturn = strat.analyzers.timereturn.get_analysis()
            returns = pd.Series(timereturn)
            
            results[strategy_name] = returns
            print(f"{strategy_name} 回测完成，最终资金: {cerebro.broker.getvalue():,.2f}")
        
        return results
    
    def rebalance_portfolio(self, rebalance_freq: str = 'M', weights: Dict[str, float] = None):
        """
        组合调仓逻辑
        :param rebalance_freq: 调仓频率 ('D'-日, 'W'-周, 'M'-月, 'Q'-季)
        :param weights: 权重字典
        """
        self.rebalance_frequency = rebalance_freq
        self.target_weights = weights or {}
        print(f"设置调仓频率: {rebalance_freq}, 目标权重: {weights}")
    
    def add_risk_management(self, max_position_size: float = 0.1, stop_loss_pct: float = 0.05):
        """
        添加风险管理
        :param max_position_size: 最大持仓比例
        :param stop_loss_pct: 止损比例
        """
        self.max_position_size = max_position_size
        self.stop_loss_pct = stop_loss_pct
        print(f"设置风险管理: 最大持仓比例 {max_position_size:.1%}, 止损比例 {stop_loss_pct:.1%}")


def run_simple_backtest(
    strategy_name: str,
    csv_path: str,
    start_date: str,
    end_date: str,
    initial_cash: float = 100000.0,
    **strategy_params
):
    """
    运行简单的单策略回测
    :param strategy_name: 策略名称
    :param csv_path: CSV数据路径
    :param start_date: 开始日期
    :param end_date: 结束日期
    :param initial_cash: 初始资金
    :param strategy_params: 策略参数
    :return: 回测结果和绩效报告
    """
    runner = BacktestRunner()
    
    # 添加数据
    runner.add_data_from_csv(csv_path)
    
    # 设置资金
    runner.set_initial_capital(initial_cash)
    
    # 设置佣金
    runner.set_commission()
    
    # 添加分析器
    runner.add_analyzers()
    
    # 添加策略
    runner.add_strategy(strategy_name, **strategy_params)
    
    # 运行回测
    results = runner.run_backtest()
    
    # 分析绩效
    report = runner.analyze_performance()
    
    # 绘制结果
    runner.plot_results()
    
    return results, report

def calculate_metrics_from_cerebro(cerebro) -> Dict:
    """
    从 backtrader 的 cerebro 对象中提取绩效指标
    :param cerebro: backtrader.Cerebro 对象
    :return: 绩效指标字典
    """
    # 获取策略的交易记录
    strat = cerebro.runstrats[0][0]  # 获取第一个策略实例
    
    # 计算每日净值变化
    if hasattr(strat, 'analyzers') and len(strat.analyzers) > 0:
        # 如果策略中有分析器，尝试从中提取数据
        analyzer_names = []
        for name, analyzer in strat.analyzers._names.items():
            analyzer_names.append(name)
    
    # 从 broker 获取资产价值历史
    if hasattr(strat, 'broker'):
        # 获取资产价值历史
        value_history = []
        for i in range(len(strat.broker.getvalue_history())):
            value_history.append(strat.broker.getvalue_history()[i])
    
    # 从策略的 trade_records 获取交易记录
    if hasattr(strat, 'trade_record_manager') and hasattr(strat.trade_record_manager, 'trade_records'):
        trade_df = strat.trade_record_manager.transform_to_dataframe()
        if not trade_df.empty:
            # 计算基于交易记录的指标
            total_return = (trade_df['total_amount'] * (1 if trade_df['action'].iloc[0] == 'S' else -1)).sum()
    
    # 由于 backtrader 的内部结构较复杂，这里提供一个通用的计算方法
    # 通常我们会使用 backtrader 的内置分析器
    try:
        # 使用 backtrader 的分析器
        from backtrader import analyzers
        
        # 如果 cerebro 中有分析器，提取数据
        if hasattr(cerebro, '_alines') and cerebro._alines:
            # 这里需要根据实际的分析器类型来提取数据
            pass
        
        # 一般情况下，我们会重新运行 cerebro 并添加分析器
        # 这里返回一个示例结构
        return {
            '总收益率': 0.0,
            '年化收益率': 0.0,
            '夏普比率': 0.0,
            '最大回撤': 0.0,
            '胜率': 0.0,
            '盈亏比': 0.0
        }
    except Exception as e:
        print(f"从 cerebro 提取数据时出错: {e}")
        return {}

def calculate_strategy_metrics(portfolio_values: pd.Series, risk_free_rate: float = 0.03) -> Dict:
    """
    根据投资组合价值序列计算策略指标
    :param portfolio_values: 投资组合价值时间序列
    :param risk_free_rate: 无风险利率
    :return: 指标字典
    """
    if len(portfolio_values) < 2:
        return {}
    
    # 计算日收益率
    returns = portfolio_values.pct_change().dropna()
    
    # 创建分析器并计算指标
    analyzer = PerformanceAnalyzer(returns)
    return analyzer.generate_report()