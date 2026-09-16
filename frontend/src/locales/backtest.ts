import type { Messages } from './index'

/**
 * backtest —— 策略回测（views/BacktestView.vue + 首页「最近回测」摘要）。
 *
 * metric.* 是**后端 JSON 指标字段名的显示译文**：键名沿用后端中文字段名
 * （总收益率 / 夏普比率 / VaR (95%)…），因为它们是 API 契约的一部分，
 * 视图里 `m.总收益率` 这类访问必须与后端一致；只有右侧译文随语言切换。
 */

export const zh: Messages = {
  subtitle: '选择市场、策略与标的，运行回测查看动态绩效图表（Alpha/Beta、回撤、日收益）',
  running: '正在运行回测，请稍候...',
  /** toast：从首页「重跑」带入历史参数时的提示 */
  formRestored: '已回填历史回测参数：{name} · {code}',
  strategiesLoadFailed: '策略列表加载失败：',
  runFailed: '回测失败：',
  done: '回测完成',
  selectStrategyRequired: '请选择策略',
  noTrades: '回测期间无成交记录（策略未触发买卖信号）',
  /** K 线买入加权平均成本线标注 */
  avgCost: '成本均价',
  market: {
    zh_a: 'A 股',
    us: '美股',
  },
  /** 货币单位词（y 轴名 / 风险面板 VaR 列头）；具体金额一律走 lib/format 的 fmtCurrency */
  currency: {
    cny: '元',
    usd: '美元',
  },
  benchmark: {
    csi300: '沪深300',
    sp500: '标普500',
  },
  stockHint: {
    zh_a: '不带前缀的 6 位 A 股代码',
    us: '美股字母代码，如 AAPL、MSFT、BRK.B',
  },
  commissionHint: {
    zh_a: 'A 股已自动叠加印花税（卖出 0.05%）与过户费（双边 0.001%）',
    us: '美股仅佣金（双边），无印花税/过户费',
  },
  form: {
    market: '市场',
    strategy: '选择策略',
    strategyPlaceholder: '请选择策略',
    stockCode: '股票代码',
    initialCapital: '初始资金',
    commissionRate: '佣金费率',
    startDate: '开始日期',
    endDate: '结束日期',
    run: '运行回测',
  },
  section: {
    metrics: '绩效指标',
    tradesKline: '回测 K 线 · 买卖点标注',
    equity: '累计收益曲线',
    drawdown: '最大回撤曲线',
    dailyReturns: '日收益率分布',
  },
  empty: {
    kline: 'K线数据加载失败或回测区间无效',
    result: '运行回测后在此查看动态绩效图表',
  },
  metric: {
    总收益率: '总收益率',
    年化收益率: '年化收益率',
    夏普比率: '夏普比率',
    最大回撤: '最大回撤',
    胜率: '胜率',
    盈亏比: '盈亏比',
    信息比率: '信息比率',
    年化波动率: '年化波动率',
    卡玛比率: '卡玛比率',
    下行标准差: '下行标准差',
    var95: 'VaR(95%)',
    cvar95: 'CVaR(95%)',
    交易次数: '交易次数',
    盈利交易数: '盈利交易',
    亏损交易数: '亏损交易',
  },
  series: {
    strategyNav: '策略净值',
    drawdown: '回撤',
    dailyReturns: '日收益率',
    dailyK: '日K',
  },
  tooltip: {
    open: '开',
    close: '收',
    low: '低',
    high: '高',
    change: '涨跌',
  },
  risk: {
    title: '风险分析',
    historicalVar: '历史 VaR (95%)',
    parametricVar: '参数 VaR (95%)',
    cvar: 'CVaR (95%)',
    currentDrawdown: '当前回撤',
    maxDrawdownLimit: '回撤上限',
    scenario: '场景',
    /** {unit} = currency.cny / currency.usd */
    varColumn: 'VaR（{unit}）',
    /** {value} = 基准 VaR 金额（fmtCurrency 输出） */
    stressTitle: '压力测试场景（基准 VaR：{value}）',
  },
}

export const en: Messages = {
  subtitle:
    'Pick a market, strategy and symbol, then run a backtest to see dynamic performance charts (Alpha/Beta, drawdown, daily returns)',
  running: 'Running backtest, please wait...',
  formRestored: 'Restored historical backtest parameters: {name} · {code}',
  strategiesLoadFailed: 'Failed to load strategies: ',
  runFailed: 'Backtest failed: ',
  done: 'Backtest completed',
  selectStrategyRequired: 'Please select a strategy',
  noTrades: 'No trades during the backtest period (the strategy produced no buy/sell signals)',
  avgCost: 'Avg Cost',
  market: {
    zh_a: 'A-shares',
    us: 'US Stocks',
  },
  currency: {
    cny: 'CNY',
    usd: 'USD',
  },
  benchmark: {
    csi300: 'CSI 300',
    sp500: 'S&P 500',
  },
  stockHint: {
    zh_a: '6-digit A-share code without an exchange prefix',
    us: 'US ticker symbols, e.g. AAPL, MSFT, BRK.B',
  },
  commissionHint: {
    zh_a: 'A-shares automatically include stamp duty (0.05% on sells) and transfer fee (0.001% both sides)',
    us: 'US stocks: commission only (both sides), no stamp duty or transfer fee',
  },
  form: {
    market: 'Market',
    strategy: 'Strategy',
    strategyPlaceholder: 'Select a strategy',
    stockCode: 'Stock Code',
    initialCapital: 'Initial Capital',
    commissionRate: 'Commission Rate',
    startDate: 'Start Date',
    endDate: 'End Date',
    run: 'Run Backtest',
  },
  section: {
    metrics: 'Performance Metrics',
    tradesKline: 'Backtest K-line · Trade Markers',
    equity: 'Cumulative Return',
    drawdown: 'Max Drawdown Curve',
    dailyReturns: 'Daily Return Distribution',
  },
  empty: {
    kline: 'K-line data failed to load, or the backtest range is invalid',
    result: 'Run a backtest to see dynamic performance charts here',
  },
  metric: {
    总收益率: 'Total Return',
    年化收益率: 'Annualized Return',
    夏普比率: 'Sharpe Ratio',
    最大回撤: 'Max Drawdown',
    胜率: 'Win Rate',
    盈亏比: 'Profit/Loss Ratio',
    信息比率: 'Information Ratio',
    年化波动率: 'Annualized Volatility',
    卡玛比率: 'Calmar Ratio',
    下行标准差: 'Downside Deviation',
    var95: 'VaR (95%)',
    cvar95: 'CVaR (95%)',
    交易次数: 'Trades',
    盈利交易数: 'Winning Trades',
    亏损交易数: 'Losing Trades',
  },
  series: {
    strategyNav: 'Strategy NAV',
    drawdown: 'Drawdown',
    dailyReturns: 'Daily Returns',
    dailyK: 'Daily K',
  },
  tooltip: {
    open: 'Open',
    close: 'Close',
    low: 'Low',
    high: 'High',
    change: 'Change',
  },
  risk: {
    title: 'Risk Analysis',
    historicalVar: 'Historical VaR (95%)',
    parametricVar: 'Parametric VaR (95%)',
    cvar: 'CVaR (95%)',
    currentDrawdown: 'Current Drawdown',
    maxDrawdownLimit: 'Max Drawdown Limit',
    scenario: 'Scenario',
    varColumn: 'VaR ({unit})',
    stressTitle: 'Stress Test Scenarios (Baseline VaR: {value})',
  },
}
