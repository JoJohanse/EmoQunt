import type { Messages } from './index'

/**
 * compare —— 策略对比（views/StrategyCompareView.vue）。
 *
 * metric.* 的子键刻意保留后端 JSON 的中文字段名（总收益率 / 夏普比率…）：只有「列头显示文案」
 * 走 t()，表格列的 prop 与行对象的键仍是中文，避免 API 契约与展示层耦合。
 */

export const zh: Messages = {
  title: '策略对比',
  subtitle: '选择 2-5 个策略，在同一标的上对比净值曲线与绩效指标',
  market: {
    zhA: 'A 股',
    us: '美股',
  },
  form: {
    market: '市场',
    strategies: '选择策略',
    strategiesPlaceholder: '选择 2-5 个策略',
    stockCode: '股票代码',
    initialCapital: '初始资金',
    startDate: '开始日期',
    endDate: '结束日期',
    hintZhA: '不带前缀的 6 位 A 股代码',
    hintUs: '美股字母代码，如 AAPL',
  },
  run: '开始对比',
  section: {
    equity: '净值曲线对比',
    metrics: '绩效指标对比',
  },
  chart: {
    equityAxis: '净值',
  },
  table: {
    strategy: '策略',
  },
  metric: {
    总收益率: '总收益率',
    年化收益率: '年化收益率',
    夏普比率: '夏普比率',
    最大回撤: '最大回撤',
    胜率: '胜率',
    盈亏比: '盈亏比',
  },
  loadStrategiesFailed: '策略列表加载失败：',
  needAtLeastTwo: '请至少选择 2 个策略进行对比',
  atMostFive: '最多对比 5 个策略',
  done: '对比完成',
  failed: '对比失败：',
  strategyFailed: '策略 {name} 失败：',
  empty: '选择多个策略后在此查看对比结果',
}

export const en: Messages = {
  title: 'Strategy Compare',
  subtitle:
    'Pick 2-5 strategies and compare their equity curves and performance metrics on the same symbol',
  market: {
    zhA: 'A-share',
    us: 'US',
  },
  form: {
    market: 'Market',
    strategies: 'Strategies',
    strategiesPlaceholder: 'Select 2-5 strategies',
    stockCode: 'Symbol',
    initialCapital: 'Initial Capital',
    startDate: 'Start Date',
    endDate: 'End Date',
    hintZhA: '6-digit A-share code without prefix',
    hintUs: 'US ticker symbol, e.g. AAPL',
  },
  run: 'Compare',
  section: {
    equity: 'Equity Curve Comparison',
    metrics: 'Performance Metrics',
  },
  chart: {
    equityAxis: 'NAV',
  },
  table: {
    strategy: 'Strategy',
  },
  metric: {
    总收益率: 'Total Return',
    年化收益率: 'Annualized Return',
    夏普比率: 'Sharpe Ratio',
    最大回撤: 'Max Drawdown',
    胜率: 'Win Rate',
    盈亏比: 'Profit/Loss Ratio',
  },
  loadStrategiesFailed: 'Failed to load strategy list: ',
  needAtLeastTwo: 'Select at least 2 strategies to compare',
  atMostFive: 'At most 5 strategies can be compared',
  done: 'Comparison complete',
  failed: 'Comparison failed: ',
  strategyFailed: 'Strategy {name} failed: ',
  empty: 'Select multiple strategies to see the comparison here',
}
