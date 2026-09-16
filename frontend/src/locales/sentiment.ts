import type { Messages } from './index'

/**
 * sentiment —— 舆情分析（views/SentimentView.vue + components/SentimentCalendar.vue）。
 *
 * 新闻标题/来源、板块名、股票名全部来自后端快照，两种语言下都保持中文原样；
 * 这里只翻译界面外壳（标题、区块名、空态、提示语）。页面 H1 复用 layout.nav.sentiment。
 */

export const zh: Messages = {
  subtitle: '更新时间：{time} · 热门新闻 {count} 条',
  refreshing: '正在刷新舆情数据，请稍候…',
  hotNews: '热门新闻',
  sectorRank: '板块得分排行',
  unknownSource: '未知来源',
  emptyNews: '暂无热门新闻',
  emptySectors: '暂无板块数据',
  calendarHint: '有快照的日期显示当日最强板块情绪分',
  loadFailed: '加载失败：{msg}',
}

export const en: Messages = {
  subtitle: 'Updated: {time} · {count} trending news',
  refreshing: 'Refreshing sentiment data, please wait…',
  hotNews: 'Trending News',
  sectorRank: 'Sector Sentiment Ranking',
  unknownSource: 'Unknown source',
  emptyNews: 'No trending news',
  emptySectors: 'No sector data',
  calendarHint: "Dates with a snapshot show that day's top sector sentiment score",
  loadFailed: 'Failed to load: {msg}',
}
