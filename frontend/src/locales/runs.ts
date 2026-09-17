import type { Messages } from './index'

/**
 * runs —— 运行历史独立页（/runs）与共享的运行详情弹窗（components/RunDetailDialog.vue）。
 *
 * 策略详情页的回测历史 Tab 同样通过 RunDetailDialog 展示单次运行，因此
 * runDetail.* 键只在这里定义一次。指标展示名复用 backtest.metric.<中文键>，
 * 状态文案复用 common.status.*，均不得在本模块重复定义。
 */

export const zh: Messages = {
  title: '运行历史',
  subtitle: '服务端保存的每次回测：状态、指标与净值缩略。',
  loadFailed: '加载失败',
  empty: '还没有运行记录，提交一次回测后这里会显示。',
  // 筛选
  filters: {
    strategy: '策略',
    strategyAll: '全部策略',
    kind: '类型',
    kindTemplate: '模板策略',
    kindCode: '代码策略',
    market: '市场',
    status: '状态',
  },
  metricColumn: '指标',
  // 列
  col: {
    time: '提交时间',
    strategy: '策略',
    stock: '标的',
    range: '区间',
    status: '状态',
    equity: '净值',
    duration: '耗时',
    action: '操作',
    detail: '详情',
  },
  kindTemplate: '模板',
  kindCode: '代码',
  // 运行详情弹窗（RunDetailDialog 共享）
  runDetail: {
    title: '运行详情',
    strategy: '策略',
    stock: '标的',
    range: '区间',
    capital: '初始资金',
    commission: '佣金费率',
    duration: '总耗时',
    equityCurve: '净值曲线',
    tradesCount: '成交笔数',
    errorLabel: '失败原因',
    stages: '阶段耗时',
    stagesFetchData: '取数',
    stagesLoadStrategy: '策略加载',
    stagesBacktest: '回测',
    stagesMetrics: '指标',
    stagesBenchmark: '基准',
    stagesEnrich: '风险报告',
  },
}

export const en: Messages = {
  title: 'Run History',
  subtitle: 'Every backtest stored on the server: status, metrics and equity preview.',
  loadFailed: 'Failed to load',
  empty: 'No runs yet. They will show up here after you submit a backtest.',
  filters: {
    strategy: 'Strategy',
    strategyAll: 'All strategies',
    kind: 'Kind',
    kindTemplate: 'Template',
    kindCode: 'Code',
    market: 'Market',
    status: 'Status',
  },
  metricColumn: 'Metric',
  col: {
    time: 'Submitted',
    strategy: 'Strategy',
    stock: 'Symbol',
    range: 'Range',
    status: 'Status',
    equity: 'Equity',
    duration: 'Duration',
    action: 'Actions',
    detail: 'Detail',
  },
  kindTemplate: 'Template',
  kindCode: 'Code',
  runDetail: {
    title: 'Run Detail',
    strategy: 'Strategy',
    stock: 'Symbol',
    range: 'Range',
    capital: 'Initial Capital',
    commission: 'Commission',
    duration: 'Total Time',
    equityCurve: 'Equity Curve',
    tradesCount: 'Trades',
    errorLabel: 'Error',
    stages: 'Stage Timings',
    stagesFetchData: 'Data',
    stagesLoadStrategy: 'Load',
    stagesBacktest: 'Backtest',
    stagesMetrics: 'Metrics',
    stagesBenchmark: 'Benchmark',
    stagesEnrich: 'Risk',
  },
}
