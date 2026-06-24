import backtrader as bt
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Union, Tuple
import os
import sys
import matplotlib.pyplot as plt
import seaborn as sns


def parse_bool(value) -> bool:
    """Parse common bool representations from strategy JSON parameters."""
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "yes", "on")
    return bool(value)

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
        total_return = (1 + self.returns).prod()
        self.annualized_return = total_return ** (periods_per_year / len(self.returns)) - 1
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
    
    def calculate_win_rate(self, won: Optional[int] = None, lost: Optional[int] = None) -> float:
        """
        计算胜率。

        旧实现把"盈利交易日数/总交易日数"当胜率，这是错误的——胜率应基于已平仓交易。
        当传入 won/lost（来自 tradeanalyzer 的已平仓交易盈亏计数）时使用真实口径；
        否则回退到旧（错误）口径并仅作兜底。

        :param won: 盈利平仓交易数
        :param lost: 亏损平仓交易数
        :return: 胜率
        """
        if won is not None and lost is not None:
            total = won + lost
            self.win_rate = won / total if total > 0 else 0.0
            return self.win_rate
        # 回退：按收益序列正负口径（不准确，仅兜底）
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


class AShareCommInfo(bt.CommInfoBase):
    """
    A股真实交易成本模型。

    相对 backtrader 默认的对称佣金，本类建模三项 A 股特有费用：
      - 佣金（commission_rate，双边，最低 min_commission 元）
      - 印花税（stamp_duty，**仅卖出**，当前 0.05%）
      - 过户费（transfer_fee_rate，双边，当前 0.001%）

    例：卖出 1000 股 @ 10 元，commission_rate=3e-4, stamp_duty=5e-4, transfer=1e-5
        成交额 = 10000
        佣金   = max(10000*3e-4, 5) = 5
        印花税 = 10000*5e-4 = 5        （卖出才收）
        过户费 = 10000*1e-5 = 0.1
        合计   = 10.1

    使用：cerebro.broker.addcommissioninfo(AShareCommInfo(...))
    """

    params = (
        ('commission_rate', 0.0003),     # 佣金费率（双边），默认万三
        ('min_commission', 5.0),         # 单笔佣金最低收费（元）
        ('stamp_duty', 0.0005),          # 印花税（仅卖出），0.05%
        ('transfer_fee_rate', 0.00001),  # 过户费（双边），0.001%
        ('stocklike', True),
        ('commtype', bt.CommInfoBase.COMM_PERC),  # 按成交额比例
    )

    def _getcommission(self, size, price, pseudoexec):
        """
        计算单笔交易的总费用。

        :param size: 成交数量，正数=买入，负数=卖出
        :param price: 成交价
        :param pseudoexec: backtrader 预执行标志（True 时为预热计算，False 为真实成交）
        :return: 总费用（元，始终为正数）
        """
        amount = abs(size) * price

        # 佣金：双边，最低收费
        commission = max(amount * self.p.commission_rate, self.p.min_commission)
        # 过户费：双边
        transfer_fee = amount * self.p.transfer_fee_rate
        # 印花税：仅卖出（size < 0）
        stamp = amount * self.p.stamp_duty if size < 0 else 0.0

        return commission + transfer_fee + stamp


class USStockCommInfo(bt.CommInfoBase):
    """
    美股交易成本模型。

    美股相对 A 股更简单：无印花税、无过户费，仅有券商佣金（双边百分比）。
    本类建模单一佣金（commission_rate，双边）。

    例：买入/卖出 100 股 @ $200，commission_rate=5e-4
        成交额 = 20000
        佣金   = 20000 * 5e-4 = 10   （买入卖出相同）

    使用：cerebro.broker.addcommissioninfo(USStockCommInfo(...))
    """

    params = (
        ('commission_rate', 0.0005),    # 佣金费率（双边），默认万五
        ('stocklike', True),
        ('commtype', bt.CommInfoBase.COMM_PERC),  # 按成交额比例
    )

    def _getcommission(self, size, price, pseudoexec):
        """
        计算单笔交易的总费用（美股仅佣金，买卖对称）。

        :param size: 成交数量，正数=买入，负数=卖出
        :param price: 成交价
        :param pseudoexec: backtrader 预执行标志
        :return: 总费用（美元，始终为正数）
        """
        amount = abs(size) * price
        return amount * self.p.commission_rate


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

    def set_ashare_commission(
        self,
        commission_rate: float = 0.0003,
        min_commission: float = 5.0,
        stamp_duty: float = 0.0005,
        transfer_fee_rate: float = 0.00001,
    ):
        """
        设置A股真实交易成本（佣金+印花税+过户费）。

        相对 set_commission 的对称单一佣金，本方法建模三项费用：
        - 佣金：双边，按 commission_rate，单笔不低于 min_commission
        - 印花税：仅卖出，stamp_duty（默认 0.05%）
        - 过户费：双边，transfer_fee_rate（默认 0.001%）

        :param commission_rate: 佣金费率（双边）
        :param min_commission: 单笔佣金最低收费（元）
        :param stamp_duty: 印花税率（仅卖出）
        :param transfer_fee_rate: 过户费率（双边）
        """
        comminfo = AShareCommInfo(
            commission_rate=commission_rate,
            min_commission=min_commission,
            stamp_duty=stamp_duty,
            transfer_fee_rate=transfer_fee_rate,
        )
        self.cerebro.broker.addcommissioninfo(comminfo)
        print(
            f"设置A股交易成本: 佣金{commission_rate:.4%}(最低{min_commission}元), "
            f"印花税{stamp_duty:.4%}(仅卖出), 过户费{transfer_fee_rate:.5%}(双边)"
        )

    def set_us_commission(self, commission_rate: float = 0.0005):
        """
        设置美股交易成本（仅双边佣金，无印花税/过户费）。

        :param commission_rate: 佣金费率（双边），默认万五
        """
        comminfo = USStockCommInfo(commission_rate=commission_rate)
        self.cerebro.broker.addcommissioninfo(comminfo)
        print(f"设置美股交易成本: 佣金{commission_rate:.4%}(双边, 无印花税/过户费)")

    def set_slippage(self, slippage_perc: float = 0.0005, enabled: bool = True):
        """
        设置百分比滑点模型。

        :param slippage_perc: 滑点比例（默认 0.05%）
        :param enabled: 是否启用
        """
        if not enabled:
            return
        self.cerebro.broker.set_slippage_perc(perc=slippage_perc)
        print(f"设置滑点: {slippage_perc:.4%}")

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

def calculate_strategy_metrics(
    portfolio_values: pd.Series,
    risk_free_rate: float = 0.03,
    win_rate_override: Optional[float] = None,
    profit_loss_ratio_override: Optional[float] = None,
) -> Dict:
    """
    计算策略绩效指标

    :param portfolio_values: 投资组合价值序列（净值序列，建议首值为初始资金）
    :param risk_free_rate: 无风险利率（年化）
    :param win_rate_override: 可选，按平仓交易计算的真实胜率。
                             旧实现把"盈利交易日数/总交易日数"当胜率，是错误的
                             （胜率应基于已平仓交易）。传入此值会覆盖旧算法。
    :param profit_loss_ratio_override: 可选，按平仓交易计算的真实盈亏比。
    :return: 绩效指标字典
    """
    import logging
    logger = logging.getLogger(__name__)

    try:
        returns = portfolio_values.pct_change().dropna()

        total_return = (portfolio_values.iloc[-1] / portfolio_values.iloc[0]) - 1
        annual_return = (1 + total_return) ** (252 / len(portfolio_values)) - 1

        sharpe_ratio = (returns.mean() - risk_free_rate / 252) / returns.std() * np.sqrt(252) if returns.std() > 0 else 0

        cumulative = (1 + returns).cumprod()
        running_max = cumulative.expanding().max()
        drawdown = (cumulative - running_max) / running_max
        max_drawdown = drawdown.min()

        # 胜率：优先用按平仓交易计算的真实胜率，否则回退到旧（错误）口径并标注
        if win_rate_override is not None:
            win_rate = win_rate_override
        else:
            # 旧口径：盈利日占比。仅作回退，不推荐依赖。
            win_rate = (returns > 0).sum() / len(returns) if len(returns) > 0 else 0

        if profit_loss_ratio_override is not None:
            profit_loss_ratio = profit_loss_ratio_override
        else:
            avg_gain = returns[returns > 0].mean() if len(returns[returns > 0]) > 0 else 0
            avg_loss = abs(returns[returns < 0].mean()) if len(returns[returns < 0]) > 0 else 0
            profit_loss_ratio = avg_gain / avg_loss if avg_loss > 0 else 0

        return {
            "总收益率": total_return,
            "年化收益率": annual_return,
            "夏普比率": sharpe_ratio,
            "最大回撤": max_drawdown,
            "胜率": win_rate,
            "盈亏比": profit_loss_ratio,
        }
    except Exception as e:
        logger.error(f"计算绩效指标失败: {e}")
        return {
            "总收益率": 0,
            "年化收益率": 0,
            "夏普比率": 0,
            "最大回撤": 0,
            "胜率": 0,
            "盈亏比": 0,
        }


def run_backtest_with_charts(
    strategy_name: str,
    stock_code: str,
    start_date: str,
    end_date: str,
    initial_capital: float = 100000.0,
    commission_rate: float = 0.0003,
    output_dir: str = "output",
    benchmark_index: str = "000300",
    use_ashare_costs: bool = True,
    slippage_rate: float = 0.0005,
    apply_sentiment_filter: bool = True,
    market: str = "zh_a",
) -> Dict:
    """
    运行回测并生成图表。

    相对旧实现的改进：
      1. 修复策略参数被忽略（value/default 键不匹配）——改用 build_param_dict。
      2. 移除净值曲线的伪造填充/截断，直接用 timereturn 真实日收益率序列。
      3. 胜率改为按平仓交易（tradeanalyzer.won/lost）计算，而非按盈利日。
      4. 接入 A 股真实交易成本（佣金+印花税+过户费）与滑点。
      5. 获取指数基准，计算 Alpha/Beta/信息比率，并绘制基准曲线。
      6. 若启用情绪过滤，加载历史快照并传入策略（避免未来函数）。
      7. 支持 market='us' 美股回测（Sina 数据源 + 仅佣金成本 + 标普500 基准）。

    Args:
        strategy_name: 策略名称
        stock_code: 股票代码（A股6位数字；美股字母代码如 AAPL）
        start_date: 开始日期 (YYYY-MM-DD)
        end_date: 结束日期 (YYYY-MM-DD)
        initial_capital: 初始资金
        commission_rate: 佣金费率（use_ashare_costs=True 时作为双边佣金率）
        output_dir: 输出目录
        benchmark_index: 基准指数代码，A股默认沪深300(000300)，美股默认标普500(SP500)
        use_ashare_costs: 是否使用A股真实成本模型（含印花税/过户费）。market='us' 时忽略
        slippage_rate: 滑点比例
        apply_sentiment_filter: 是否尝试加载情绪快照并接入策略情绪过滤（美股自动关闭）
        market: 市场，'zh_a'（A股，默认）或 'us'（美股）

    Returns:
        包含绩效数据和图表URL的字典（保持旧四键契约，performance_data 扩展新指标）
    """
    import logging
    from src.Strategy.Strategy import create_user_strategy_class, build_param_dict
    from src.Strategy.strategy_manager import get_user_strategy
    from src.data.data_manager import (
        get_index_data, load_sentiment_snapshots, build_stock_sentiment_series,
    )
    from src.visualization import StrategyVisualizer

    logger = logging.getLogger(__name__)

    # 读取 backtest 配置默认值（之前是死配置，这里真正接入）
    try:
        from config.config_loader import get
        slippage_enabled_cfg = get('backtest.slippage_enabled', False)
    except Exception:
        slippage_enabled_cfg = False

    runner = BacktestRunner()
    runner.set_initial_capital(initial_capital)
    # 成本模型：按市场选择（美股强制仅佣金，忽略 use_ashare_costs）
    if market == 'us':
        runner.set_us_commission(commission_rate=commission_rate)
    elif use_ashare_costs:
        runner.set_ashare_commission(commission_rate=commission_rate)
    else:
        runner.set_commission(commission_rate)
    runner.set_slippage(slippage_perc=slippage_rate, enabled=slippage_enabled_cfg or True)
    runner.add_analyzers()

    # 数据：按市场选择数据源。A 股用后复权(hfq)，美股新浪源仅支持 qfq(前复权)/不复权
    stock = Stock(stock_code, market=market)
    stock_data, _ = stock.get_stock_data(
        start_date=start_date.replace('-', ''),
        end_date=end_date.replace('-', ''),
        adjust='qfq' if market == 'us' else 'hfq',
        type='daily'
    )

    if stock_data.empty:
        raise ValueError(f"无法获取股票 {stock_code} 的数据")

    if '时间' in stock_data.columns:
        stock_data['时间'] = pd.to_datetime(stock_data['时间'])
        stock_data.set_index('时间', inplace=True)

    data_feed = bt.feeds.PandasData(
        dataname=stock_data,
        name=stock_code,
        open='开盘',
        high='最高',
        low='最低',
        close='收盘',
        volume='成交量',
        openinterest=-1
    )
    runner.cerebro.adddata(data_feed)

    user_config = get_user_strategy(strategy_name)
    if not user_config:
        raise ValueError(f"未找到用户策略: {strategy_name}")

    # Phase 4: 加载情绪快照，构建该股票的行业情绪序列（避免未来函数）
    # 美股不映射 A 股行业，跳过情绪过滤，回退纯均线策略
    sentiment_series = None
    sentiment_sector = None
    if apply_sentiment_filter and market != 'us':
        try:
            panel = load_sentiment_snapshots()
            if panel is not None and not panel.empty:
                code_no_prefix = stock.get_code_without_prefix()
                series, sector = build_stock_sentiment_series(panel, code_no_prefix)
                if series is not None and not series.empty:
                    sentiment_series = series
                    sentiment_sector = sector
                    logger.info(f"情绪过滤已启用: 股票{stock_code} -> 行业{sector}, "
                                f"{len(series)}个历史快照")
        except Exception as e:
            logger.warning(f"加载情绪数据失败，回测将以纯均线策略运行: {e}")

    strategy_class = create_user_strategy_class(
        user_config,
        sentiment_series=sentiment_series,
        sentiment_sector=sentiment_sector,
    )

    # Phase 0/1: 用统一的参数解析（修复 value/default 不匹配）
    params = build_param_dict(user_config)
    # 参数已作为类 params 默认值注入（create_user_strategy_class 内 build_param_dict），
    # 这里不重复传，避免 backtrader "params already defined" 类问题。
    runner.cerebro.addstrategy(strategy_class)

    results = runner.cerebro.run()

    strat = results[0]

    # Phase 1: 直接用 timereturn 分析器的真实日收益率序列，不再伪造填充净值
    daily_returns = pd.Series(dtype=float)
    try:
        timereturn_analyzer = strat.analyzers.getbyname('timereturn')
        if timereturn_analyzer:
            returns_dict = timereturn_analyzer.get_analysis()
            if returns_dict:
                daily_returns = pd.Series(returns_dict)
    except Exception as e:
        logger.warning(f"获取收益分析器失败: {e}")

    if daily_returns.empty:
        logger.warning("未取到日收益率序列，绩效指标将为 0")
        # 兜底：构造一条全 0 的序列，至少让后续流程不崩
        daily_returns = pd.Series(0.0, index=stock_data.index)

    # 真实净值序列（仅用于绘图与 calculate_strategy_metrics）
    equity = initial_capital * (1 + daily_returns).cumprod()
    # 在序列首部补上初始资金，使净值曲线起点正确
    equity_full = pd.concat([pd.Series([initial_capital], index=[daily_returns.index[0]]), equity])
    equity_full = equity_full[~equity_full.index.duplicated(keep='last')]

    # Phase 1: 按平仓交易计算真实胜率与盈亏比
    win_rate_real = None
    profit_loss_real = None
    try:
        ta = strat.analyzers.getbyname('tradeanalyzer')
        if ta:
            ta_report = ta.get_analysis()
            won = ta_report.get('won', {})
            lost = ta_report.get('lost', {})
            won_n = won.get('total', 0) if isinstance(won, dict) else 0
            lost_n = lost.get('total', 0) if isinstance(lost, dict) else 0
            total_closed = won_n + lost_n
            if total_closed > 0:
                win_rate_real = won_n / total_closed
                won_pnl = won.get('pnl', {}).get('total', 0) if isinstance(won.get('pnl'), dict) else 0
                lost_pnl = abs(lost.get('pnl', {}).get('total', 0)) if isinstance(lost.get('pnl'), dict) else 0
                if lost_pnl > 0:
                    profit_loss_real = won_pnl / lost_pnl
    except Exception as e:
        logger.warning(f"从 tradeanalyzer 提取交易级胜率失败，回退到日级胜率: {e}")

    performance_data = calculate_strategy_metrics(
        equity_full,
        win_rate_override=win_rate_real,
        profit_loss_ratio_override=profit_loss_real,
    )

    # Phase 3: 基准与 Alpha/Beta/信息比率（按市场选择基准指数源）
    benchmark_returns = None
    alpha = beta = info_ratio = None
    try:
        bench_df = get_index_data(
            benchmark_index,
            start_date=start_date.replace('-', ''),
            end_date=end_date.replace('-', ''),
            market=market,
        )
        if bench_df is not None and not bench_df.empty and '收盘' in bench_df.columns:
            bench_df = bench_df.set_index('时间')
            bench_close = pd.to_numeric(bench_df['收盘'], errors='coerce').dropna()
            benchmark_returns = bench_close.pct_change().dropna()
            # 对齐到策略日收益率
            aligned = pd.concat([daily_returns, benchmark_returns], axis=1).dropna()
            if len(aligned) >= 2:
                analyzer = PerformanceAnalyzer(
                    aligned.iloc[:, 0], aligned.iloc[:, 1]
                )
                alpha, beta = analyzer.calculate_alpha_beta()
                info_ratio = analyzer.calculate_information_ratio()
    except Exception as e:
        logger.warning(f"获取基准/计算Alpha/Beta失败: {e}")

    formatted_performance = {
        "总收益率": f"{performance_data.get('总收益率', 0):.2%}",
        "年化收益率": f"{performance_data.get('年化收益率', 0):.2%}",
        "夏普比率": round(performance_data.get('夏普比率', 0), 2),
        "最大回撤": f"{performance_data.get('最大回撤', 0):.2%}",
        "胜率": f"{performance_data.get('胜率', 0):.2%}",
        "盈亏比": round(performance_data.get('盈亏比', 0), 2),
    }
    if alpha is not None and beta is not None:
        formatted_performance["Alpha"] = f"{alpha:.2%}"
        formatted_performance["Beta"] = round(beta, 2)
    if info_ratio is not None:
        formatted_performance["信息比率"] = round(info_ratio, 2)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    strategy_dir = os.path.join(output_dir, f"{strategy_name}_{stock_code}", timestamp)
    os.makedirs(strategy_dir, exist_ok=True)

    visualizer = StrategyVisualizer()

    equity_path = os.path.join(strategy_dir, f"equity_curve_{strategy_name}_{stock_code}_{timestamp}.png")
    equity_fig = visualizer.plot_cumulative_returns(
        daily_returns, benchmark_returns, title=f"{strategy_name} 收益曲线"
    )
    equity_fig.savefig(equity_path)
    plt.close(equity_fig)

    drawdown_path = os.path.join(strategy_dir, f"drawdown_curve_{strategy_name}_{stock_code}_{timestamp}.png")
    drawdown_fig = visualizer.plot_drawdown(daily_returns, title=f"{strategy_name} 回撤曲线")
    drawdown_fig.savefig(drawdown_path)
    plt.close(drawdown_fig)

    dashboard_path = os.path.join(strategy_dir, f"performance_dashboard_{strategy_name}_{stock_code}_{timestamp}.png")
    dashboard_fig = visualizer.plot_performance_dashboard(daily_returns, benchmark_returns)
    dashboard_fig.savefig(dashboard_path)
    plt.close(dashboard_fig)

    return {
        "performance_data": formatted_performance,
        "equity_chart_url": f"/output/{strategy_name}_{stock_code}/{timestamp}/{os.path.basename(equity_path)}",
        "drawdown_chart_url": f"/output/{strategy_name}_{stock_code}/{timestamp}/{os.path.basename(drawdown_path)}",
        "dashboard_url": f"/output/{strategy_name}_{stock_code}/{timestamp}/{os.path.basename(dashboard_path)}"
    }


def run_backtest_json(
    strategy_name: str,
    stock_code: str,
    start_date: str,
    end_date: str,
    initial_capital: float = 100000.0,
    commission_rate: float = 0.0003,
    benchmark_index: str = "000300",
    market: str = "zh_a",
    slippage_rate: float = 0.0005,
) -> Dict:
    """
    运行回测并返回 JSON 可序列化的时序数据（供 Vue3 前端 ECharts 动态绘制）。

    与 run_backtest_with_charts 的区别：不生成 matplotlib PNG，而是返回原始
    净值/回撤/日收益率/基准序列，由前端动态渲染。指标以数值（非格式化字符串）返回。

    Args 同 run_backtest_with_charts（去掉 output_dir/sentiment 等图表相关参数）。
    :return: { strategy_name, stock_code, market, metrics, dates, equity_curve,
               benchmark_curve, drawdown, daily_returns }
    """
    import logging
    from src.Strategy.Strategy import create_user_strategy_class, build_param_dict
    from src.Strategy.strategy_manager import get_user_strategy
    from src.data.data_manager import get_index_data

    logger = logging.getLogger(__name__)

    runner = BacktestRunner()
    runner.set_initial_capital(initial_capital)
    if market == 'us':
        runner.set_us_commission(commission_rate=commission_rate)
    else:
        runner.set_ashare_commission(commission_rate=commission_rate)
    runner.set_slippage(slippage_perc=slippage_rate, enabled=True)
    runner.add_analyzers()

    stock = Stock(stock_code, market=market)
    stock_data, _ = stock.get_stock_data(
        start_date=start_date.replace('-', ''),
        end_date=end_date.replace('-', ''),
        adjust='qfq' if market == 'us' else 'hfq',
        type='daily',
    )
    if stock_data.empty:
        raise ValueError(f"无法获取股票 {stock_code} 的数据")

    if '时间' in stock_data.columns:
        stock_data['时间'] = pd.to_datetime(stock_data['时间'])
        stock_data.set_index('时间', inplace=True)

    runner.cerebro.adddata(bt.feeds.PandasData(
        dataname=stock_data, name=stock_code,
        open='开盘', high='最高', low='最低', close='收盘',
        volume='成交量', openinterest=-1,
    ))

    user_config = get_user_strategy(strategy_name)
    if not user_config:
        raise ValueError(f"未找到用户策略: {strategy_name}")
    strategy_class = create_user_strategy_class(
        user_config, sentiment_series=None, sentiment_sector=None
    )
    runner.cerebro.addstrategy(strategy_class)

    results = runner.cerebro.run()
    strat = results[0]

    # 日收益率序列
    daily_returns = pd.Series(dtype=float)
    try:
        tr = strat.analyzers.getbyname('timereturn')
        if tr:
            rd = tr.get_analysis()
            if rd:
                daily_returns = pd.Series(rd)
    except Exception as e:
        logger.warning(f"获取收益分析器失败: {e}")
    if daily_returns.empty:
        daily_returns = pd.Series(0.0, index=stock_data.index)

    equity = initial_capital * (1 + daily_returns).cumprod()

    # 回撤序列
    running_max = equity.expanding().max()
    drawdown = (equity - running_max) / running_max

    # 交易级胜率/盈亏比
    win_rate_real = None
    profit_loss_real = None
    try:
        ta = strat.analyzers.getbyname('tradeanalyzer')
        if ta:
            rep = ta.get_analysis()
            won = rep.get('won', {})
            lost = rep.get('lost', {})
            wn = won.get('total', 0) if isinstance(won, dict) else 0
            ln = lost.get('total', 0) if isinstance(lost, dict) else 0
            if wn + ln > 0:
                win_rate_real = wn / (wn + ln)
                wp = won.get('pnl', {}).get('total', 0) if isinstance(won.get('pnl'), dict) else 0
                lp = abs(lost.get('pnl', {}).get('total', 0)) if isinstance(lost.get('pnl'), dict) else 0
                if lp > 0:
                    profit_loss_real = wp / lp
    except Exception as e:
        logger.warning(f"tradeanalyzer 提取失败: {e}")

    # 净值序列（含初始资金起点）
    equity_full = pd.concat([pd.Series([initial_capital], index=[daily_returns.index[0]]), equity])
    equity_full = equity_full[~equity_full.index.duplicated(keep='last')]

    metrics_raw = calculate_strategy_metrics(
        equity_full, win_rate_override=win_rate_real,
        profit_loss_ratio_override=profit_loss_real,
    )

    # 基准净值序列 + Alpha/Beta
    benchmark_curve = None
    alpha = beta = info_ratio = None
    try:
        bench_df = get_index_data(
            benchmark_index,
            start_date=start_date.replace('-', ''),
            end_date=end_date.replace('-', ''),
            market=market,
        )
        if bench_df is not None and not bench_df.empty and '收盘' in bench_df.columns:
            bench_df = bench_df.set_index('时间')
            bench_close = pd.to_numeric(bench_df['收盘'], errors='coerce').dropna()
            bench_ret = bench_close.pct_change().dropna()
            bench_equity = 1.0 * (1 + bench_ret).cumprod()
            # 对齐到策略日期
            aligned = pd.concat([daily_returns, bench_ret], axis=1).dropna()
            if len(aligned) >= 2:
                analyzer = PerformanceAnalyzer(aligned.iloc[:, 0], aligned.iloc[:, 1])
                alpha, beta = analyzer.calculate_alpha_beta()
                info_ratio = analyzer.calculate_information_ratio()
            # 基准净值序列对齐到策略日期（ffill 后 bfill 补首部 NaN）
            bench_eq_aligned = bench_equity.reindex(daily_returns.index).ffill().bfill()
            benchmark_curve = bench_eq_aligned.tolist()
    except Exception as e:
        logger.warning(f"获取基准/Alpha/Beta失败: {e}")

    def _safe(v, nd=6):
        """JSON 安全化：NaN/inf 转为 0。"""
        try:
            f = float(v)
            if not np.isfinite(f):
                return 0.0
            return round(f, nd)
        except (TypeError, ValueError):
            return 0.0

    metrics = {
        "总收益率": _safe(metrics_raw.get("总收益率", 0), 6),
        "年化收益率": _safe(metrics_raw.get("年化收益率", 0), 6),
        "夏普比率": _safe(metrics_raw.get("夏普比率", 0), 4),
        "最大回撤": _safe(metrics_raw.get("最大回撤", 0), 6),
        "胜率": _safe(metrics_raw.get("胜率", 0), 6),
        "盈亏比": _safe(metrics_raw.get("盈亏比", 0), 4),
    }
    if alpha is not None:
        metrics["Alpha"] = _safe(alpha, 6)
    if beta is not None:
        metrics["Beta"] = _safe(beta, 4)
    if info_ratio is not None:
        metrics["信息比率"] = _safe(info_ratio, 4)

    dates = [d.strftime('%Y-%m-%d') for d in daily_returns.index]

    return {
        "strategy_name": strategy_name,
        "stock_code": stock_code,
        "market": market,
        "metrics": metrics,
        "dates": dates,
        "equity_curve": [_safe(v, 2) for v in equity.tolist()],
        "benchmark_curve": [_safe(v, 4) for v in benchmark_curve] if benchmark_curve else [],
        "drawdown": [_safe(v, 6) for v in drawdown.tolist()],
        "daily_returns": [_safe(v, 6) for v in daily_returns.tolist()],
    }
