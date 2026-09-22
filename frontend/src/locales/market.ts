import type { Messages } from './index'

/**
 * market —— 行情终端独立页（/market）。
 *
 * 只放**本页自有**文案；以下共享词表一律复用，不得在本模块重复定义：
 * - 市场标签（A股/US）→ common.market.*；空态兜底 → common.noData；
 * - K 线图内标签（周期/复权/指数、系列名、tooltip 字段名）→ home.kline.*
 *   （chart/kline.ts 是蜡烛图骨架的唯一实现，两页画的是同一张图、同一批标签）；
 * - 指数预设名（上证指数/沪深300/深证成指/标普500/纳斯达克）→ home.index.*
 *   （与首页指数速览、stores/watchlist 默认股的 nameKey 同源，避免同一指数名三处翻译漂移）。
 */

export const zh: Messages = {
  title: '行情终端',
  subtitle: '搜索标的、查看大字报价与多周期 K 线（指数与个股同页）。',
  searchPlaceholder: '搜索代码 / 名称',
  groupIndexes: '指数',
  groupWatchlist: '自选股',
  indexTag: '指数',
  empty: '没有匹配的标的',
  selectHint: '从左侧列表选择标的',
  addAndView: '添加并查看 {code}',
  addDone: '已添加并查看：{name}',
  addFailed: '添加失败，请检查代码是否正确：',
  kline: {
    title: '行情走势',
  },
}

export const en: Messages = {
  title: 'Market Terminal',
  subtitle: 'Search symbols, read the big quote header and multi-period K-lines (indices and stocks).',
  searchPlaceholder: 'Search code / name',
  groupIndexes: 'Indices',
  groupWatchlist: 'Watchlist',
  indexTag: 'Index',
  empty: 'No matching symbols',
  selectHint: 'Pick a symbol from the list',
  addAndView: 'Add and view {code}',
  addDone: 'Added and viewing: {name}',
  addFailed: 'Failed to add. Please check the symbol code: ',
  kline: {
    title: 'Price Chart',
  },
}
