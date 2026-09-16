import type { Messages } from './index'

/**
 * recommend —— 每日推荐（views/DailyRecommendView.vue）。
 *
 * 股票代码/名称、板块名、推荐理由（reason）与热门板块名（top_sector_name）均为后端数据，
 * 两种语言下原样展示；这里只翻译界面外壳（标题、区块名、表头、空态）。H1 复用 layout.nav.recommend。
 */

export const zh: Messages = {
  subtitle: '推荐日期：{date}',
  refreshing: '正在刷新推荐，请稍候…',
  refreshButton: '刷新推荐',
  topSectors: '热门板块 TOP 3',
  heat: '热度：{score}',
  list: '推荐股票列表',
  colRank: '排名',
  colCode: '代码',
  colName: '名称',
  colSector: '板块',
  colScore: '综合评分',
  colReason: '推荐理由',
  empty: '暂无推荐',
  loadFailed: '加载失败：{msg}',
}

export const en: Messages = {
  subtitle: 'Picks for {date}',
  refreshing: 'Refreshing picks, please wait…',
  refreshButton: 'Refresh picks',
  topSectors: 'Top 3 Hot Sectors',
  heat: 'Heat: {score}',
  list: 'Recommended Stocks',
  colRank: 'Rank',
  colCode: 'Code',
  colName: 'Name',
  colSector: 'Sector',
  colScore: 'Overall Score',
  colReason: 'Reason',
  empty: 'No picks yet',
  loadFailed: 'Failed to load: {msg}',
}
