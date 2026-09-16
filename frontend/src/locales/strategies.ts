import type { Messages } from './index'

/**
 * strategies —— 策略列表（views/StrategiesView.vue）。
 *
 * 注意：策略名/描述/参数名/参数类型都来自后端（user_strategies/strategies.json 里
 * 持久化的中文），**两种语言下都原样展示**；这里只翻译界面外壳（表头、空态、按钮、
 * 自定义/系统 标签等）。页面 H1 直接复用 layout.nav.strategies，不在此重复定义。
 */

export const zh: Messages = {
  subtitle: '查看与管理所有回测策略',
  badgeCustom: '自定义',
  badgeSystem: '系统',
  noDesc: '暂无描述',
  colParamName: '参数名',
  colValue: '值',
  colType: '类型',
  backtest: '使用此策略回测',
  delete: '删除',
  deleteConfirm: '确定删除策略 "{name}"？此操作不可恢复',
  deleted: '已删除',
  deleteFailed: '删除失败：{msg}',
  loadFailed: '加载失败：{msg}',
  empty: '暂无策略',
}

export const en: Messages = {
  subtitle: 'Browse and manage all backtest strategies',
  badgeCustom: 'Custom',
  badgeSystem: 'Built-in',
  noDesc: 'No description',
  colParamName: 'Parameter',
  colValue: 'Value',
  colType: 'Type',
  backtest: 'Backtest with this strategy',
  delete: 'Delete',
  deleteConfirm: 'Delete strategy "{name}"? This cannot be undone',
  deleted: 'Deleted',
  deleteFailed: 'Failed to delete: {msg}',
  loadFailed: 'Failed to load: {msg}',
  empty: 'No strategies',
}
