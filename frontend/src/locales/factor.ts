import type { Messages } from './index'

/**
 * factor —— 因子分析（views/FactorAnalysisView.vue）。
 *
 * IC / Rank IC / ICIR 在两种语言下保持原样（行业通用缩写）；后端返回的 quantile_labels
 * 属数据，不走 i18n。
 */

export const zh: Messages = {
  title: '因子分析',
  subtitle: '在沪深300成分股上做多因子 IC/分层分析（对标 Qlib 多因子框架）',
  type: {
    momentum: '动量 (20日收益)',
    momentumDesc: '过去 20 个交易日收益率',
    rsi: 'RSI (14)',
    rsiDesc: '14 日相对强弱指标',
    volatility: '波动率 (20日)',
    volatilityDesc: '20 日日收益标准差',
    volumeRatio: '成交量比',
    volumeRatioDesc: '当日量 / 20 日均量',
  },
  form: {
    factorType: '因子类型',
    startDate: '开始日期',
    endDate: '结束日期',
    quantiles: '分层数',
    forwardPeriod: '前瞻周期',
    hint: '首次运行会拉取 HS300 全量数据，依赖数据库缓存；请耐心等待',
  },
  run: '开始分析',
  section: {
    icOverview: 'IC 概览',
    icSeries: 'IC 时序',
    quantileCumReturns: '分层累计收益',
    quantileStats: '分层统计',
  },
  chart: {
    cumNavAxis: '累计净值',
  },
  cards: {
    icMean: 'IC 均值',
    rankIcMean: 'Rank IC 均值',
    icir: 'ICIR',
    rankIcir: 'Rank ICIR',
    icWinRate: 'IC 胜率',
    icPositiveRate: 'IC 正率',
  },
  meta: {
    universe: '股票池规模：{n} 只',
    monotonicity: '单调性：',
    monotonic: '单调 ✓',
    notMonotonic: '非单调',
    ratio: '（比率 {ratio}）',
  },
  table: {
    quantile: '分层',
    meanReturn: '平均收益',
    sharpe: '夏普',
    winRate: '胜率',
  },
  done: '因子分析完成',
  failed: '分析失败：',
  empty: '选择因子类型后开始分析',
}

export const en: Messages = {
  title: 'Factor Analysis',
  subtitle:
    'Multi-factor IC and quantile analysis on CSI 300 constituents (modeled after the Qlib multi-factor framework)',
  type: {
    momentum: 'Momentum (20-day return)',
    momentumDesc: 'Return over the past 20 trading days',
    rsi: 'RSI (14)',
    rsiDesc: '14-day relative strength index',
    volatility: 'Volatility (20-day)',
    volatilityDesc: 'Standard deviation of 20-day daily returns',
    volumeRatio: 'Volume Ratio',
    volumeRatioDesc: "Today's volume / 20-day average volume",
  },
  form: {
    factorType: 'Factor Type',
    startDate: 'Start Date',
    endDate: 'End Date',
    quantiles: 'Quantiles',
    forwardPeriod: 'Forward Period',
    hint: 'The first run downloads the full HS300 dataset and relies on the database cache; please be patient',
  },
  run: 'Analyze',
  section: {
    icOverview: 'IC Overview',
    icSeries: 'IC Time Series',
    quantileCumReturns: 'Quantile Cumulative Returns',
    quantileStats: 'Quantile Statistics',
  },
  chart: {
    cumNavAxis: 'Cumulative NAV',
  },
  cards: {
    icMean: 'IC Mean',
    rankIcMean: 'Rank IC Mean',
    icir: 'ICIR',
    rankIcir: 'Rank ICIR',
    icWinRate: 'IC Win Rate',
    icPositiveRate: 'IC Positive Rate',
  },
  meta: {
    universe: 'Universe: {n} stocks',
    monotonicity: 'Monotonicity: ',
    monotonic: 'Monotonic ✓',
    notMonotonic: 'Non-monotonic',
    ratio: '(ratio {ratio})',
  },
  table: {
    quantile: 'Quantile',
    meanReturn: 'Mean Return',
    sharpe: 'Sharpe',
    winRate: 'Win Rate',
  },
  done: 'Factor analysis complete',
  failed: 'Analysis failed: ',
  empty: 'Select a factor type to start the analysis',
}
