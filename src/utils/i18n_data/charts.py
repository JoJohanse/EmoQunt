"""图表标签文案目录。

所有者：**matplotlib 可视化 Agent**（src/visualization.py 与
src/backtest/backtest_manager.py 的图表标题/轴标签）——图表内的中文标签以
``charts.*`` 前缀收录，供绘图模块在生成 PNG 时按当前语言取用。

zh 值必须与改造前写在绘图代码里的中文字面量逐字一致（含冒号、空格、
``(20日)`` 之类的后缀），保证中文输出不变。这些是静态标签（无插值参
数），绘图侧直接用 ``t('charts.xxx')``，不走 ``vmsg``。
"""

MESSAGES = {
    # 图表标题
    "charts.cumulativeReturns": {"zh": "累积收益曲线", "en": "Cumulative Returns"},
    "charts.equityCurve": {"zh": "收益曲线", "en": "Equity Curve"},
    "charts.drawdownCurve": {"zh": "回撤曲线", "en": "Drawdown"},
    "charts.returnsDistribution": {"zh": "收益分布直方图", "en": "Returns Distribution"},
    "charts.monthlyHeatmap": {"zh": "月度收益热力图", "en": "Monthly Returns Heatmap"},
    "charts.riskReturnScatter": {"zh": "风险收益散点图", "en": "Risk-Return Scatter"},
    "charts.correlationMatrix": {"zh": "收益率相关性矩阵", "en": "Returns Correlation Matrix"},
    "charts.rollingVolatility": {"zh": "滚动年化波动率 (20日)", "en": "Rolling Annualized Volatility (20d)"},
    "charts.rollingSharpe": {"zh": "滚动夏普比率 (20日)", "en": "Rolling Sharpe Ratio (20d)"},
    "charts.riskReturn": {"zh": "风险收益图", "en": "Risk-Return Chart"},
    "charts.factorExposure": {"zh": "因子暴露分析", "en": "Factor Exposure Analysis"},
    "charts.portfolioAllocation": {"zh": "投资组合配置", "en": "Portfolio Allocation"},
    # 轴标签
    "charts.time": {"zh": "时间", "en": "Time"},
    "charts.cumulativeReturn": {"zh": "累积收益", "en": "Cumulative Return"},
    "charts.drawdown": {"zh": "回撤", "en": "Drawdown"},
    "charts.returnRate": {"zh": "收益率", "en": "Return"},
    "charts.density": {"zh": "密度", "en": "Density"},
    "charts.month": {"zh": "月份", "en": "Month"},
    "charts.year": {"zh": "年份", "en": "Year"},
    "charts.annualizedVolatility": {"zh": "年化波动率", "en": "Annualized Volatility"},
    "charts.annualizedReturn": {"zh": "年化收益率", "en": "Annualized Return"},
    # 热力图色条
    "charts.monthlyReturnRate": {"zh": "月度收益率", "en": "Monthly Return"},
    "charts.correlationCoeff": {"zh": "相关系数", "en": "Correlation Coefficient"},
    # 图例
    "charts.strategyReturn": {"zh": "策略收益", "en": "Strategy"},
    "charts.benchmarkReturn": {"zh": "基准收益", "en": "Benchmark"},
    "charts.rollingVolatilityLabel": {"zh": "滚动波动率", "en": "Rolling Volatility"},
    "charts.rollingSharpeLabel": {"zh": "滚动夏普比率", "en": "Rolling Sharpe Ratio"},
    # 统计注记（数值由调用方拼接）
    "charts.mean": {"zh": "均值", "en": "Mean"},
    "charts.meanPlus1Sigma": {"zh": "均值+1σ", "en": "Mean + 1σ"},
    "charts.meanMinus1Sigma": {"zh": "均值-1σ", "en": "Mean - 1σ"},
    "charts.strategyAnnotation": {"zh": "策略", "en": "Strategy"},
    # 饼图/其他
    "charts.other": {"zh": "其他", "en": "Other"},
    "charts.sentimentPositive": {"zh": "正面", "en": "Positive"},
    "charts.sentimentNegative": {"zh": "负面", "en": "Negative"},
    "charts.sentimentNeutral": {"zh": "中性", "en": "Neutral"},
    "charts.sentimentDistribution": {"zh": "舆情情绪分布", "en": "Sentiment Distribution"},
}
