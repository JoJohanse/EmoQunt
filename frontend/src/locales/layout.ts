import type { Messages } from './index'

/**
 * layout —— 应用外壳（AppLayout / 路由标题 / 命令面板导航）。
 *
 * nav.* 是**跨模块共享契约**：router meta.titleKey、AppLayout 侧边菜单与面包屑、
 * CommandPalette 导航项、收藏菜单标题全部引用它；视图模块不得重复定义这几个键。
 */

export const zh: Messages = {
  nav: {
    home: '首页',
    backtest: '策略回测',
    strategies: '策略列表',
    sentiment: '舆情分析',
    recommend: '每日推荐',
    compare: '策略对比',
    factor: '因子分析',
  },
  group: {
    research: '回测研究',
    insight: '数据洞察',
    manage: '策略管理',
  },
  brand: 'EmoQunt 量化系统',
  favorites: '收藏',
  expandMenu: '展开菜单',
  collapseMenu: '收起菜单',
  commandPalette: '命令面板 Ctrl+K',
  switchLight: '切换到亮色模式',
  switchDark: '切换到暗色模式',
  switchLang: '切换语言',
  aiAssistant: 'AI 助手',
  aiDrawerTitle: 'AI 投资助手',
  asideTip: 'v1.0 · A股 / 美股',
  footer: 'EmoQunt 量化系统 · 让量化投资更简单',
  // 顶部标签页（components/AppTabs.vue）；标签标题本身走 nav.* + 路由 meta.titleKey
  tabs: {
    closeOthers: '关闭其他',
    closeAll: '关闭全部',
  },
}

export const en: Messages = {
  nav: {
    home: 'Home',
    backtest: 'Backtest',
    strategies: 'Strategies',
    sentiment: 'Sentiment',
    recommend: 'Daily Picks',
    compare: 'Compare',
    factor: 'Factor Analysis',
  },
  group: {
    research: 'Backtesting',
    insight: 'Data Insights',
    manage: 'Strategy Management',
  },
  brand: 'EmoQunt Quant Platform',
  favorites: 'Favorites',
  expandMenu: 'Expand menu',
  collapseMenu: 'Collapse menu',
  commandPalette: 'Command palette Ctrl+K',
  switchLight: 'Switch to light mode',
  switchDark: 'Switch to dark mode',
  switchLang: 'Switch to English',
  aiAssistant: 'AI Assistant',
  aiDrawerTitle: 'AI Investment Assistant',
  asideTip: 'v1.0 · A-share / US',
  footer: 'EmoQunt Quant Platform · Make quant investing simple',
  // 顶部标签页（components/AppTabs.vue）；标签标题本身走 nav.* + 路由 meta.titleKey
  tabs: {
    closeOthers: 'Close others',
    closeAll: 'Close all',
  },
}
