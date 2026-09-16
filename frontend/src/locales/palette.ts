import type { Messages } from './index'

/**
 * palette —— 全局命令面板（components/CommandPalette.vue）。
 *
 * 导航项文案**复用** layout.nav.*（与 router meta.titleKey 同一套契约），此处不得重复定义；
 * 自选股名称、回测策略名是数据，保持原样。
 */

export const zh: Messages = {
  groupNav: '导航',
  groupWatchlist: '自选股',
  groupRecentBacktest: '最近回测',
  placeholder: '搜索命令、页面、自选股、回测…（↑↓ 选择，回车确认）',
  escHint: 'ESC 关闭',
  noResults: '无匹配结果',
}

export const en: Messages = {
  groupNav: 'Navigation',
  groupWatchlist: 'Watchlist',
  groupRecentBacktest: 'Recent backtests',
  placeholder: 'Search commands, pages, watchlist, backtests… (↑↓ to move, Enter to confirm)',
  escHint: 'ESC to close',
  noResults: 'No matching results',
}
