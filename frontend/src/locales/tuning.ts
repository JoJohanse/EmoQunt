import type { Messages } from './index'

/**
 * tuning —— 参数调优（/tuning/:taskId 详情页 + 策略详情页的新建调优对话框）。
 *
 * 指标展示名复用 backtest.metric.<中文键>，状态文案复用 common.status.*，
 * 均不得在本模块重复定义。
 */

export const zh: Messages = {
  title: '参数调优',
  loadFailed: '加载失败',
  backToStrategy: '返回策略',
  taskOf: '「{name}」的调优任务',
  // 任务头
  head: {
    targetMetric: '目标指标',
    stock: '标的',
    range: '回测区间',
    capital: '初始资金',
    duration: '总耗时',
    created: '创建时间',
    combos: '组合进度',
  },
  best: '最优',
  baseline: '基准',
  chartTitle: '净值对比（归一化起点 = 1）',
  // 组合表
  table: {
    index: '#',
    params: '参数组合',
    equity: '净值',
    range: '区间',
    status: '状态',
    duration: '耗时',
    action: '操作',
    apply: '应用此参数',
    applyConfirm: '将把参数 {params} 应用到策略（只覆盖网格参数，并自动保存版本快照）。确定？',
    applied: '已应用到策略',
    applyFailed: '应用失败',
    viewParam: '参数',
  },
  // 新建调优对话框（StrategyDetailView 调优 Tab 内）
  create: {
    title: '新建参数调优',
    gridTitle: '参数网格',
    gridHint: '勾选要调优的参数并填写候选值（逗号分隔）；全部候选做笛卡尔积，基准组合（当前参数）自动参与对比。',
    valuesPlaceholder: '候选值，逗号分隔，如 5, 10, 20',
    comboCount: '组合数：{n}（含基准 {total}）',
    comboCountOver: '组合数超过上限 63，请减少候选值',
    targetMetric: '目标指标',
    targetHint: '最优组合按目标指标挑选；最大回撤越小越好。',
    submit: '开始调优',
    submitted: '已提交，正在打开任务…',
    noGrid: '请至少为一个参数填写候选值',
    badValues: '参数「{name}」的候选值格式有误',
  },
  // 任务列表（策略详情调优 Tab）
  list: {
    empty: '还没有调优任务',
    create: '新建调优',
    created: '创建时间',
    progress: '进度',
    target: '目标指标',
    action: '操作',
    open: '查看',
  },
}

export const en: Messages = {
  title: 'Parameter Tuning',
  loadFailed: 'Failed to load',
  backToStrategy: 'Back to Strategy',
  taskOf: 'Tuning task of "{name}"',
  head: {
    targetMetric: 'Target Metric',
    stock: 'Symbol',
    range: 'Range',
    capital: 'Initial Capital',
    duration: 'Total Time',
    created: 'Created',
    combos: 'Combos',
  },
  best: 'Best',
  baseline: 'Baseline',
  chartTitle: 'Equity Comparison (normalized to 1)',
  table: {
    index: '#',
    params: 'Parameters',
    equity: 'Equity',
    range: 'Range',
    status: 'Status',
    duration: 'Duration',
    action: 'Actions',
    apply: 'Apply',
    applyConfirm: 'Apply parameters {params} to the strategy (grid keys only, a version snapshot is saved). Continue?',
    applied: 'Applied to strategy',
    applyFailed: 'Failed to apply',
    viewParam: 'Params',
  },
  create: {
    title: 'New Tuning Task',
    gridTitle: 'Parameter Grid',
    gridHint: 'Tick parameters to tune and list candidate values (comma separated); all candidates form a cartesian product. The baseline combo (current params) joins automatically.',
    valuesPlaceholder: 'Candidates, e.g. 5, 10, 20',
    comboCount: 'Combos: {n} ({total} incl. baseline)',
    comboCountOver: 'Over the limit of 63 combos; reduce candidates',
    targetMetric: 'Target Metric',
    targetHint: 'The best combo is picked by the target metric; lower max drawdown is better.',
    submit: 'Start Tuning',
    submitted: 'Submitted, opening the task…',
    noGrid: 'Fill candidates for at least one parameter',
    badValues: 'Invalid candidate values for "{name}"',
  },
  list: {
    empty: 'No tuning tasks yet',
    create: 'New Tuning',
    created: 'Created',
    progress: 'Progress',
    target: 'Target',
    action: 'Actions',
    open: 'Open',
  },
}
