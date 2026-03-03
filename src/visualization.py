"""
可视化模块

提供量化策略分析的各种图表绘制功能
包括收益曲线、回撤曲线、风险分析图等
"""

import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
import numpy as np
from typing import Union, List, Optional, Tuple
import warnings

warnings.filterwarnings('ignore')

# 设置中文字体
plt.rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans']  # 用来正常显示中文标签
plt.rcParams['axes.unicode_minus'] = False  # 用来正常显示负号


class StrategyVisualizer:
    """
    策略可视化器
    """
    
    def __init__(self, figsize: Tuple[int, int] = (14, 10)):
        """
        初始化可视化器
        :param figsize: 图表大小
        """
        self.figsize = figsize
    
    def plot_cumulative_returns(
        self, 
        returns: pd.Series, 
        benchmark_returns: Optional[pd.Series] = None, 
        title: str = "累积收益曲线",
        figsize: Optional[Tuple[int, int]] = None
    ) -> plt.Figure:
        """
        绘制累积收益曲线
        :param returns: 策略收益率序列
        :param benchmark_returns: 基准收益率序列
        :param title: 图表标题
        :param figsize: 图表大小
        :return: matplotlib Figure 对象
        """
        figsize = figsize or self.figsize
        fig, ax = plt.subplots(figsize=figsize)
        
        # 计算累积收益
        cum_returns = (1 + returns).cumprod()
        ax.plot(cum_returns.index, cum_returns.values, label='策略收益', linewidth=2)
        
        if benchmark_returns is not None:
            benchmark_cum_returns = (1 + benchmark_returns).cumprod()
            ax.plot(benchmark_cum_returns.index, benchmark_cum_returns.values, label='基准收益', linewidth=2)
        
        ax.set_title(title, fontsize=16)
        ax.set_xlabel('时间', fontsize=12)
        ax.set_ylabel('累积收益', fontsize=12)
        ax.legend()
        ax.grid(True, linestyle='--', alpha=0.6)
        
        plt.tight_layout()
        return fig
    
    def plot_drawdown(
        self, 
        returns: pd.Series, 
        title: str = "回撤曲线",
        figsize: Optional[Tuple[int, int]] = None
    ) -> plt.Figure:
        """
        绘制回撤曲线
        :param returns: 收益率序列
        :param title: 图表标题
        :param figsize: 图表大小
        :return: matplotlib Figure 对象
        """
        figsize = figsize or self.figsize
        fig, ax = plt.subplots(figsize=figsize)
        
        # 计算累积收益和回撤
        cumulative_returns = (1 + returns).cumprod()
        running_max = cumulative_returns.expanding().max()
        drawdown = (cumulative_returns - running_max) / running_max
        
        ax.fill_between(drawdown.index, drawdown.values, 0, color='red', alpha=0.3)
        ax.set_title(title, fontsize=16)
        ax.set_xlabel('时间', fontsize=12)
        ax.set_ylabel('回撤', fontsize=12)
        ax.grid(True, linestyle='--', alpha=0.6)
        
        plt.tight_layout()
        return fig
    
    def plot_returns_distribution(
        self, 
        returns: pd.Series, 
        title: str = "收益分布直方图",
        figsize: Optional[Tuple[int, int]] = None
    ) -> plt.Figure:
        """
        绘制收益分布直方图
        :param returns: 收益率序列
        :param title: 图表标题
        :param figsize: 图表大小
        :return: matplotlib Figure 对象
        """
        figsize = figsize or self.figsize
        fig, ax = plt.subplots(figsize=figsize)
        
        ax.hist(returns.dropna(), bins=50, density=True, alpha=0.7, edgecolor='black')
        ax.set_title(title, fontsize=16)
        ax.set_xlabel('收益率', fontsize=12)
        ax.set_ylabel('密度', fontsize=12)
        ax.grid(True, linestyle='--', alpha=0.6)
        
        # 添加统计信息
        mean_ret = returns.mean()
        std_ret = returns.std()
        ax.axvline(mean_ret, color='red', linestyle='--', label=f'均值: {mean_ret:.4f}')
        ax.axvline(mean_ret + std_ret, color='orange', linestyle='--', label=f'均值+1σ: {(mean_ret + std_ret):.4f}')
        ax.axvline(mean_ret - std_ret, color='orange', linestyle='--', label=f'均值-1σ: {(mean_ret - std_ret):.4f}')
        ax.legend()
        
        plt.tight_layout()
        return fig
    
    def plot_monthly_heatmap(
        self, 
        returns: pd.Series, 
        title: str = "月度收益热力图",
        figsize: Optional[Tuple[int, int]] = None
    ) -> plt.Figure:
        """
        绘制月度收益热力图
        :param returns: 收益率序列
        :param title: 图表标题
        :param figsize: 图表大小
        :return: matplotlib Figure 对象
        """
        figsize = figsize or self.figsize
        fig, ax = plt.subplots(figsize=figsize)
        
        # 计算月度收益
        monthly_returns = returns.resample('M').apply(lambda x: (1 + x).prod() - 1)
        
        if len(monthly_returns) > 0:
            # 创建透视表
            monthly_pivot = monthly_returns.to_frame('monthly_return')
            monthly_pivot['year'] = monthly_pivot.index.year
            monthly_pivot['month'] = monthly_pivot.index.month
            pivot_table = monthly_pivot.pivot(index='year', columns='month', values='monthly_return')
            
            # 绘制热力图
            sns.heatmap(
                pivot_table, 
                annot=True, 
                fmt='.2%', 
                cmap='RdYlGn', 
                center=0, 
                ax=ax,
                cbar_kws={'label': '月度收益率'}
            )
            ax.set_title(title, fontsize=16)
            ax.set_xlabel('月份', fontsize=12)
            ax.set_ylabel('年份', fontsize=12)
        
        plt.tight_layout()
        return fig
    
    def plot_risk_return_scatter(
        self, 
        strategies_returns: dict, 
        title: str = "风险收益散点图",
        figsize: Optional[Tuple[int, int]] = None
    ) -> plt.Figure:
        """
        绘制多个策略的风险收益散点图
        :param strategies_returns: 策略收益率字典 {策略名: 收益率序列}
        :param title: 图表标题
        :param figsize: 图表大小
        :return: matplotlib Figure 对象
        """
        figsize = figsize or self.figsize
        fig, ax = plt.subplots(figsize=figsize)
        
        for name, returns in strategies_returns.items():
            # 计算年化收益率和年化波动率
            annual_return = (1 + returns).pow(252 / len(returns)).mean() - 1 if len(returns) > 0 else 0
            annual_vol = returns.std() * np.sqrt(252) if len(returns) > 0 else 0
            
            ax.scatter(annual_vol, annual_return, label=name, s=100, alpha=0.7)
            ax.annotate(name, (annual_vol, annual_return), xytext=(5, 5), 
                       textcoords='offset points', fontsize=10)
        
        ax.set_title(title, fontsize=16)
        ax.set_xlabel('年化波动率', fontsize=12)
        ax.set_ylabel('年化收益率', fontsize=12)
        ax.grid(True, linestyle='--', alpha=0.6)
        
        plt.tight_layout()
        return fig
    
    def plot_correlation_matrix(
        self, 
        returns_dict: dict, 
        title: str = "收益率相关性矩阵",
        figsize: Optional[Tuple[int, int]] = None
    ) -> plt.Figure:
        """
        绘制收益率相关性矩阵
        :param returns_dict: 收益率字典 {名称: 收益率序列}
        :param title: 图表标题
        :param figsize: 图表大小
        :return: matplotlib Figure 对象
        """
        figsize = figsize or self.figsize
        fig, ax = plt.subplots(figsize=figsize)
        
        # 合并所有收益率序列
        combined_returns = pd.DataFrame(returns_dict)
        
        # 计算相关性矩阵
        corr_matrix = combined_returns.corr()
        
        # 绘制热力图
        sns.heatmap(
            corr_matrix, 
            annot=True, 
            cmap='coolwarm', 
            center=0, 
            square=True,
            ax=ax,
            cbar_kws={'label': '相关系数'}
        )
        ax.set_title(title, fontsize=16)
        
        plt.tight_layout()
        return fig
    
    def plot_performance_dashboard(
        self, 
        returns: pd.Series, 
        benchmark_returns: Optional[pd.Series] = None,
        figsize: Optional[Tuple[int, int]] = (16, 12)
    ) -> plt.Figure:
        """
        绘制综合绩效仪表板
        :param returns: 策略收益率序列
        :param benchmark_returns: 基准收益率序列
        :param figsize: 图表大小
        :return: matplotlib Figure 对象
        """
        fig, axes = plt.subplots(2, 3, figsize=figsize)
        
        # 1. 累积收益曲线
        cum_returns = (1 + returns).cumprod()
        axes[0, 0].plot(cum_returns.index, cum_returns.values, label='策略收益', linewidth=2)
        if benchmark_returns is not None:
            benchmark_cum_returns = (1 + benchmark_returns).cumprod()
            axes[0, 0].plot(benchmark_cum_returns.index, benchmark_cum_returns.values, label='基准收益', linewidth=2)
        axes[0, 0].set_title('累积收益曲线')
        axes[0, 0].legend()
        axes[0, 0].grid(True, linestyle='--', alpha=0.6)
        
        # 2. 回撤曲线
        running_max = cum_returns.expanding().max()
        drawdown = (cum_returns - running_max) / running_max
        axes[0, 1].fill_between(drawdown.index, drawdown.values, 0, color='red', alpha=0.3)
        axes[0, 1].set_title('回撤曲线')
        axes[0, 1].grid(True, linestyle='--', alpha=0.6)
        
        # 3. 收益分布直方图
        axes[0, 2].hist(returns.dropna(), bins=50, density=True, alpha=0.7, edgecolor='black')
        axes[0, 2].set_title('收益分布直方图')
        axes[0, 2].grid(True, linestyle='--', alpha=0.6)
        
        # 4. 滚动波动率
        rolling_vol = returns.rolling(window=20).std() * np.sqrt(252)
        axes[1, 0].plot(returns.index, rolling_vol, label='滚动波动率', color='orange')
        axes[1, 0].set_title('滚动年化波动率 (20日)')
        axes[1, 0].grid(True, linestyle='--', alpha=0.6)
        
        # 5. 滚动夏普比率
        rolling_sharpe = (returns.rolling(window=20).mean() * 252) / (returns.rolling(window=20).std() * np.sqrt(252))
        axes[1, 1].plot(returns.index, rolling_sharpe, label='滚动夏普比率', color='purple')
        axes[1, 1].set_title('滚动夏普比率 (20日)')
        axes[1, 1].grid(True, linestyle='--', alpha=0.6)
        
        # 6. 收益 vs 风险散点图
        # 计算年化指标
        annual_return = (1 + returns).pow(252 / len(returns)).mean() - 1
        annual_vol = returns.std() * np.sqrt(252)
        axes[1, 2].scatter(annual_vol, annual_return, s=200, alpha=0.7, c='blue', marker='^')
        axes[1, 2].annotate(f'策略\n{annual_return:.2%}', (annual_vol, annual_return), 
                           xytext=(5, 5), textcoords='offset points', fontsize=10)
        axes[1, 2].set_title('风险收益图')
        axes[1, 2].set_xlabel('年化波动率')
        axes[1, 2].set_ylabel('年化收益率')
        axes[1, 2].grid(True, linestyle='--', alpha=0.6)
        
        plt.tight_layout()
        return fig


def quick_plot_performance(
    strategy_returns: pd.Series, 
    benchmark_returns: Optional[pd.Series] = None,
    figsize: Tuple[int, int] = (14, 10)
) -> plt.Figure:
    """
    快速绘制策略绩效图表
    :param strategy_returns: 策略收益率序列
    :param benchmark_returns: 基准收益率序列
    :param figsize: 图表大小
    :return: matplotlib Figure 对象
    """
    visualizer = StrategyVisualizer(figsize=figsize)
    return visualizer.plot_performance_dashboard(strategy_returns, benchmark_returns)


def plot_factor_exposure(factor_data: pd.DataFrame, title: str = "因子暴露分析") -> plt.Figure:
    """
    绘制因子暴露分析图
    :param factor_data: 因子数据 DataFrame
    :param title: 图表标题
    :return: matplotlib Figure 对象
    """
    fig, ax = plt.subplots(figsize=(12, 8))
    
    # 绘制因子暴露热力图
    sns.boxplot(data=factor_data, ax=ax)
    ax.set_title(title)
    ax.tick_params(axis='x', rotation=45)
    
    plt.tight_layout()
    return fig


def plot_portfolio_allocation(weights: dict, title: str = "投资组合配置") -> plt.Figure:
    """
    绘制投资组合配置饼图
    :param weights: 权重字典 {资产名: 权重}
    :param title: 图表标题
    :return: matplotlib Figure 对象
    """
    fig, ax = plt.subplots(figsize=(10, 8))
    
    # 过滤掉权重小于1%的资产
    filtered_weights = {k: v for k, v in weights.items() if abs(v) >= 0.01}
    other_weight = sum(v for v in weights.values() if abs(v) < 0.01)
    
    if other_weight != 0:
        filtered_weights['其他'] = other_weight
    
    ax.pie(filtered_weights.values(), labels=filtered_weights.keys(), autopct='%1.1f%%', startangle=90)
    ax.set_title(title)
    
    plt.tight_layout()
    return fig


if __name__ == "__main__":
    # 示例使用
    np.random.seed(42)
    dates = pd.date_range(start='2023-01-01', end='2023-12-31', freq='D')
    strategy_returns = pd.Series(np.random.normal(0.001, 0.02, len(dates)), index=dates)
    benchmark_returns = pd.Series(np.random.normal(0.0005, 0.015, len(dates)), index=dates)
    
    # 创建可视化器
    visualizer = StrategyVisualizer()
    
    # 绘制累积收益曲线
    fig1 = visualizer.plot_cumulative_returns(strategy_returns, benchmark_returns)
    plt.show()
    
    # 绘制回撤曲线
    fig2 = visualizer.plot_drawdown(strategy_returns)
    plt.show()
    
    # 绘制收益分布
    fig3 = visualizer.plot_returns_distribution(strategy_returns)
    plt.show()
    
    # 绘制月度热力图
    fig4 = visualizer.plot_monthly_heatmap(strategy_returns)
    plt.show()
    
    # 绘制综合仪表板
    fig5 = visualizer.plot_performance_dashboard(strategy_returns, benchmark_returns)
    plt.show()