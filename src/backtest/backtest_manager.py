import backtrader as bt
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple
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

from src.data.data_manager import Stock
from src.data.columns import DATE, OPEN, HIGH, LOW, CLOSE, VOLUME

# 绩效指标唯一事实来源为 calculate_strategy_metrics，PerformanceAnalyzer.generate_report 为旧报告视图
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


class _TradeRecorder(bt.Analyzer):
    """逐笔成交记录器（回测 K 线买卖点标注的数据源）。

    通过 notify_order 捕获 broker 已成交订单：含滑点时 executed.price 才是
    真实成交价。size>0 为买入、<0 为卖出；日期取成交 bar 的日期。
    """

    def __init__(self):
        self.trades = []

    def notify_order(self, order):
        try:
            if order.status != order.Completed or not order.executed.size:
                return
            dt = order.executed.dt or order.created.dt
            self.trades.append({
                "date": bt.num2date(dt).strftime("%Y-%m-%d"),
                "side": "buy" if order.executed.size > 0 else "sell",
                "price": round(float(order.executed.price), 4),
                "size": round(abs(float(order.executed.size)), 2),
            })
        except Exception:
            # 单条订单记录失败不影响回测主流程
            pass


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


def _build_enrichment_reports(daily_returns, equity, strat, initial_capital, perf_analyzer=None):
    """生成完整绩效报告 + 事后风险报告（激活 PerformanceAnalyzer / RiskManager）。

    从 _run_backtest_core 抽出，便于单独测试 wiring（无需跑完整 cerebro 回测）。

    :param daily_returns: pd.Series，日收益率
    :param equity: pd.Series，净值曲线（iloc[-1] 为期末组合价值）
    :param strat: backtrader Strategy 实例（取 tradeanalyzer 真实交易级胜负），可为 None
    :param initial_capital: 初始资金
    :param perf_analyzer: 已构造的 PerformanceAnalyzer（带基准时复用）；None 则用无基准实例
    :return: (performance_report, risk_report) 两个 dict（或 None 表示该层失败）
    """
    import logging
    logger = logging.getLogger(__name__)
    performance_report = None
    risk_report = None
    try:
        from src.risk import RiskManager
        # 完整绩效报告（含波动率/卡玛/下行差/VaR/CVaR/交易统计）
        pa = perf_analyzer or PerformanceAnalyzer(daily_returns.dropna())
        try:
            # 注入真实交易级胜负，使胜率/盈亏比准确（generate_report 默认用日线正收益日启发式）
            if strat is not None:
                ta = strat.analyzers.getbyname('tradeanalyzer')
            else:
                ta = None
            if ta:
                rep = ta.get_analysis()
                won = rep.get('won', {})
                lost = rep.get('lost', {})
                wn = won.get('total', 0) if isinstance(won, dict) else 0
                ln = lost.get('total', 0) if isinstance(lost, dict) else 0
                pa_report = pa.generate_report()
                if wn + ln > 0:
                    pa_report['胜率'] = pa.calculate_win_rate(wn, ln)
                performance_report = pa_report
            else:
                performance_report = pa.generate_report()
        except Exception as e:
            logger.warning(f"生成完整绩效报告失败（降级）: {e}")
            performance_report = pa.generate_report()

        # 事后风险报告：VaR/CVaR/波动率/夏普/当前回撤/压力测试
        rm = RiskManager(initial_capital=initial_capital)
        rm.update_portfolio_value(float(equity.iloc[-1]))
        rr = rm.generate_risk_report(float(equity.iloc[-1]), daily_returns.dropna())
        # 三个标准压力场景（市场冲击 / 波动放大 / 流动性枯竭）
        stress = rm.stress_test(daily_returns.dropna(), stress_scenarios=[
            {'name': '市场冲击', 'shock': -0.20},
            {'name': '波动放大', 'vol_multiplier': 1.5},
            {'name': '流动性枯竭', 'liquidity_shock': 0.3},
        ])
        rr['stress_test'] = stress
        risk_report = rr
    except Exception as e:
        logger.warning(f"生成风险报告失败（不影响主流程）: {e}")
    return performance_report, risk_report


def _run_backtest_core(
    strategy_name: str,
    stock_code: str,
    start_date: str,
    end_date: str,
    initial_capital: float = 100000.0,
    commission_rate: float = 0.0003,
    benchmark_index: str = "000300",
    slippage_rate: float = 0.0005,
    market: str = "zh_a",
    apply_sentiment_filter: bool = True,
) -> Dict:
    """回测核心流水线（深模块）：装配→数据→策略→回测→指标→基准。

    统一了原 run_backtest_with_charts 与 run_backtest_json 共享的 8 段流水线。
    两个入口函数变为输出适配器：with_charts 生成 PNG，json 返回时序数组。

    :return: 结构化结果字典，含：
        - daily_returns (pd.Series), equity (pd.Series), equity_full (pd.Series)
        - drawdown (pd.Series), benchmark_returns (pd.Series|None)
        - metrics_raw (dict, 中文 key 数值), alpha/beta/info_ratio (float|None)
        - market, strategy_name, stock_code
    """
    import logging
    from src.Strategy.Strategy import create_user_strategy_class
    from src.Strategy.strategy_manager import get_user_strategy
    from src.data.data_manager import (
        get_index_data, load_sentiment_snapshots, build_stock_sentiment_series,
    )

    logger = logging.getLogger(__name__)

    # 读取 backtest 配置默认值
    try:
        from config.config_loader import get
        slippage_enabled_cfg = get('backtest.slippage_enabled', False)
    except Exception:
        slippage_enabled_cfg = False

    cerebro = bt.Cerebro()
    cerebro.broker.setcash(initial_capital)
    if market == 'us':
        cerebro.broker.addcommissioninfo(USStockCommInfo(commission_rate=commission_rate))
    else:
        cerebro.broker.addcommissioninfo(AShareCommInfo(commission_rate=commission_rate))
    # 滑点：保持原有行为（slippage_enabled_cfg or True 恒为 True，始终启用）
    if slippage_enabled_cfg or True:
        cerebro.broker.set_slippage_perc(perc=slippage_rate)
    cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='tradeanalyzer')
    cerebro.addanalyzer(_TradeRecorder, _name='traderecorder')
    cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharperatio')
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
    cerebro.addanalyzer(bt.analyzers.Returns, _name='returns')
    cerebro.addanalyzer(bt.analyzers.TimeReturn, _name='timereturn')

    stock = Stock(stock_code, market=market)
    stock_data, _ = stock.get_stock_data(
        start_date=start_date.replace('-', ''),
        end_date=end_date.replace('-', ''),
        adjust='qfq' if market == 'us' else 'hfq',
        type='daily',
    )
    if stock_data.empty:
        raise ValueError(f"无法获取股票 {stock_code} 的数据")

    if DATE in stock_data.columns:
        stock_data[DATE] = pd.to_datetime(stock_data[DATE])
        stock_data.set_index(DATE, inplace=True)

    cerebro.adddata(bt.feeds.PandasData(
        dataname=stock_data, name=stock_code,
        open=OPEN, high=HIGH, low=LOW, close=CLOSE,
        volume=VOLUME, openinterest=-1,
    ))

    user_config = get_user_strategy(strategy_name)
    if not user_config:
        raise ValueError(f"未找到用户策略: {strategy_name}")

    # 情绪过滤（仅 A 股）
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
        user_config, sentiment_series=sentiment_series, sentiment_sector=sentiment_sector,
    )
    cerebro.addstrategy(strategy_class)

    results = cerebro.run()
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
    equity_full = pd.concat([pd.Series([initial_capital], index=[daily_returns.index[0]]), equity])
    equity_full = equity_full[~equity_full.index.duplicated(keep='last')]

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

    # 逐笔成交（前端回测 K 线买卖点标注数据源），封顶防止极端高频策略撑爆响应
    trades = []
    try:
        rec = strat.analyzers.getbyname('traderecorder')
        if rec is not None:
            trades = list(getattr(rec, "trades", []) or [])[:500]
    except Exception as e:
        logger.warning(f"成交记录提取失败: {e}")

    metrics_raw = calculate_strategy_metrics(
        equity_full, win_rate_override=win_rate_real,
        profit_loss_ratio_override=profit_loss_real,
    )

    # 基准 + Alpha/Beta
    benchmark_returns = None
    benchmark_curve = None
    alpha = beta = info_ratio = None
    perf_analyzer = None  # 用于后续完整报告
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
            benchmark_returns = bench_ret
            aligned = pd.concat([daily_returns, bench_ret], axis=1).dropna()
            if len(aligned) >= 2:
                analyzer = PerformanceAnalyzer(aligned.iloc[:, 0], aligned.iloc[:, 1])
                alpha, beta = analyzer.calculate_alpha_beta()
                info_ratio = analyzer.calculate_information_ratio()
                perf_analyzer = analyzer
            bench_equity = 1.0 * (1 + bench_ret).cumprod()
            bench_eq_aligned = bench_equity.reindex(daily_returns.index).ffill().bfill()
            benchmark_curve = bench_eq_aligned.tolist()
    except Exception as e:
        logger.warning(f"获取基准/计算Alpha/Beta失败: {e}")

    # ---- 完整绩效报告 + 风险报告（激活休眠的 PerformanceAnalyzer / RiskManager）----
    performance_report, risk_report = _build_enrichment_reports(
        daily_returns, equity, strat, initial_capital, perf_analyzer=perf_analyzer,
    )

    return {
        "strategy_name": strategy_name,
        "stock_code": stock_code,
        "market": market,
        "daily_returns": daily_returns,
        "equity": equity,
        "equity_full": equity_full,
        "drawdown": drawdown,
        "benchmark_returns": benchmark_returns,
        "benchmark_curve": benchmark_curve,
        "metrics_raw": metrics_raw,
        "alpha": alpha,
        "beta": beta,
        "info_ratio": info_ratio,
        "trades": trades,
        "performance_report": performance_report,
        "risk_report": risk_report,
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
    """运行回测并生成 matplotlib PNG 图表（Jinja2 前端用）。

    输出适配器：调用 _run_backtest_core，把结果格式化为图表 URL 契约。
    """
    from src.visualization import StrategyVisualizer

    core = _run_backtest_core(
        strategy_name=strategy_name, stock_code=stock_code,
        start_date=start_date, end_date=end_date,
        initial_capital=initial_capital, commission_rate=commission_rate,
        benchmark_index=benchmark_index, slippage_rate=slippage_rate,
        market=market, apply_sentiment_filter=apply_sentiment_filter,
    )

    m = core["metrics_raw"]
    formatted_performance = {
        "总收益率": f"{m.get('总收益率', 0):.2%}",
        "年化收益率": f"{m.get('年化收益率', 0):.2%}",
        "夏普比率": round(m.get('夏普比率', 0), 2),
        "最大回撤": f"{m.get('最大回撤', 0):.2%}",
        "胜率": f"{m.get('胜率', 0):.2%}",
        "盈亏比": round(m.get('盈亏比', 0), 2),
    }
    if core["alpha"] is not None and core["beta"] is not None:
        formatted_performance["Alpha"] = f"{core['alpha']:.2%}"
        formatted_performance["Beta"] = round(core["beta"], 2)
    if core["info_ratio"] is not None:
        formatted_performance["信息比率"] = round(core["info_ratio"], 2)

    daily_returns = core["daily_returns"]
    benchmark_returns = core["benchmark_returns"]

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    strategy_dir = os.path.join(output_dir, f"{strategy_name}_{stock_code}", timestamp)
    os.makedirs(strategy_dir, exist_ok=True)

    visualizer = StrategyVisualizer()
    equity_path = os.path.join(strategy_dir, f"equity_curve_{strategy_name}_{stock_code}_{timestamp}.png")
    equity_fig = visualizer.plot_cumulative_returns(
        daily_returns, benchmark_returns, title=f"{strategy_name} 收益曲线")
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
        "dashboard_url": f"/output/{strategy_name}_{stock_code}/{timestamp}/{os.path.basename(dashboard_path)}",
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
    """运行回测并返回 JSON 可序列化时序数据（Vue3 前端 ECharts 用）。

    输出适配器：调用 _run_backtest_core，把结果序列化为前端可消费的数组。
    """
    core = _run_backtest_core(
        strategy_name=strategy_name, stock_code=stock_code,
        start_date=start_date, end_date=end_date,
        initial_capital=initial_capital, commission_rate=commission_rate,
        benchmark_index=benchmark_index, slippage_rate=slippage_rate,
        market=market, apply_sentiment_filter=False,  # JSON 路径不用情绪过滤（与原行为一致）
    )

    def _safe(v, nd=6):
        try:
            f = float(v)
            if not np.isfinite(f):
                return 0.0
            return round(f, nd)
        except (TypeError, ValueError):
            return 0.0

    def _safe_any(v, nd=6):
        """序列化任意指标值：数值→_safe，datetime/Timestamp→ISO str，其它→原值。

        注意 pd.Timestamp 不是 datetime 的子类，需单独判断；
        PerformanceAnalyzer 的最大回撤起止时间可能是 Timestamp。
        """
        if isinstance(v, (datetime, pd.Timestamp)):
            return pd.Timestamp(v).strftime('%Y-%m-%d')
        if isinstance(v, (int, float, np.floating, np.integer)):
            return _safe(v, nd)
        return v

    m = core["metrics_raw"]
    metrics = {
        "总收益率": _safe(m.get("总收益率", 0), 6),
        "年化收益率": _safe(m.get("年化收益率", 0), 6),
        "夏普比率": _safe(m.get("夏普比率", 0), 4),
        "最大回撤": _safe(m.get("最大回撤", 0), 6),
        "胜率": _safe(m.get("胜率", 0), 6),
        "盈亏比": _safe(m.get("盈亏比", 0), 4),
    }
    if core["alpha"] is not None:
        metrics["Alpha"] = _safe(core["alpha"], 6)
    if core["beta"] is not None:
        metrics["Beta"] = _safe(core["beta"], 4)
    if core["info_ratio"] is not None:
        metrics["信息比率"] = _safe(core["info_ratio"], 4)

    # ---- 追加完整绩效报告的新增指标（波动率/卡玛/下行差/VaR/CVaR/交易统计）----
    pr = core.get("performance_report") or {}
    for k in ("年化波动率", "卡玛比率", "下行标准差", "VaR (95%)", "CVaR (95%)",
              "交易次数", "盈利交易数", "亏损交易数", "平均盈利", "平均亏损",
              "最大回撤开始时间", "最大回撤结束时间"):
        if k in pr and pr[k] is not None:
            metrics[k] = _safe_any(pr[k], 6)

    # ---- 风险报告（顶层字段，前端单独渲染风险面板）----
    rr = core.get("risk_report")
    risk_report = None
    if rr:
        risk_report = {
            "portfolio_value": _safe(rr.get("portfolio_value", 0), 2),
            "current_drawdown": _safe(rr.get("current_drawdown", 0), 6),
            "max_drawdown_limit": _safe(rr.get("max_drawdown_limit", 0), 4),
            "volatility": _safe(rr.get("volatility", 0), 6),
            "sharpe_ratio": _safe(rr.get("sharpe_ratio", 0), 4),
            "blacklist_count": int(rr.get("blacklist_count", 0) or 0),
            "var_analysis": {
                "historical_var": _safe((rr.get("var_analysis") or {}).get("historical_var", 0), 2),
                "parametric_var": _safe((rr.get("var_analysis") or {}).get("parametric_var", 0), 2),
                "cvar": _safe((rr.get("var_analysis") or {}).get("cvar", 0), 2),
                "confidence_level": _safe((rr.get("var_analysis") or {}).get("confidence_level", 0.95), 2),
            },
            "stress_test": {
                k: _safe(v, 2) for k, v in (rr.get("stress_test") or {}).items()
            },
            "risk_limits": {
                k: _safe(v, 4) for k, v in (rr.get("risk_limits") or {}).items()
            },
        }

    daily_returns = core["daily_returns"]
    equity = core["equity"]
    drawdown = core["drawdown"]
    dates = [d.strftime('%Y-%m-%d') for d in daily_returns.index]
    benchmark_curve = core["benchmark_curve"]

    return {
        "strategy_name": strategy_name,
        "stock_code": stock_code,
        "market": market,
        "metrics": metrics,
        "risk_report": risk_report,
        "dates": dates,
        "equity_curve": [_safe(v, 2) for v in equity.tolist()],
        "benchmark_curve": [_safe(v, 4) for v in benchmark_curve] if benchmark_curve else [],
        "drawdown": [_safe(v, 6) for v in drawdown.tolist()],
        "daily_returns": [_safe(v, 6) for v in daily_returns.tolist()],
        "trades": core.get("trades", []),
    }
