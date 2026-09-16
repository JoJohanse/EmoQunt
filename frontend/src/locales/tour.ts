import type { Messages } from './index'

/**
 * tour —— 首页首访导览（composables/useHomeTour.ts，driver.js）。
 *
 * 步骤文案的键名与导览元素一一对应（quick / indexes / kline / watchlist / history /
 * breadth / heatmap）；steps 数组只存 i18n 键，真正的 t() 取值发生在 startHomeTour()
 * 内部——导览是一次性快照，运行中不随语言热切换（可接受）。
 */
export const zh: Messages = {
  next: '下一步',
  prev: '上一步',
  done: '完成',
  steps: {
    quick: {
      title: '快捷入口',
      desc: '回测、因子分析、舆情等核心功能一键直达。',
    },
    indexes: {
      title: '指数速览',
      desc: '大盘三大指数快照，点击任意指数卡片即可在下方主图查看。',
    },
    kline: {
      title: '行情看板',
      desc: 'K 线主图支持周期/复权切换、MA/BOLL 叠加与 MACD/KDJ/RSI 副图；点击右侧自选股可切换标的。',
    },
    watchlist: {
      title: '自选股',
      desc: '输入代码即可添加自选（A股/美股），列表行内展示最新价与涨跌走势。',
    },
    history: {
      title: '最近回测',
      desc: '本地保留最近回测摘要，点击"重跑"一键回填参数。',
    },
    breadth: {
      title: '市场宽度',
      desc: '涨跌家数与涨停/跌停分布，一屏判断当日市场情绪。',
    },
    heatmap: {
      title: '行业热力图',
      desc: '面积=成交额、颜色=涨跌幅，快速定位强势行业。',
    },
  },
}

export const en: Messages = {
  next: 'Next',
  prev: 'Back',
  done: 'Done',
  steps: {
    quick: {
      title: 'Quick Access',
      desc: 'One click to the core features: backtest, factor analysis, sentiment and more.',
    },
    indexes: {
      title: 'Index Overview',
      desc: 'Snapshots of the three major indices — click any card to load it on the chart below.',
    },
    kline: {
      title: 'Market Board',
      desc: 'The K-line chart supports period/adjust switching, MA/BOLL overlays and MACD/KDJ/RSI sub-charts; click a watchlist item on the right to switch symbols.',
    },
    watchlist: {
      title: 'Watchlist',
      desc: 'Enter a code to add a symbol (A-shares / US stocks); each row shows the latest price and intraday trend.',
    },
    history: {
      title: 'Recent Backtests',
      desc: 'Recent backtest summaries are kept locally — click "Re-run" to restore all parameters.',
    },
    breadth: {
      title: 'Market Breadth',
      desc: 'Advancing/declining counts plus limit-up/limit-down distribution — read the mood of the day at a glance.',
    },
    heatmap: {
      title: 'Sector Heatmap',
      desc: 'Area = turnover, color = change — spot the strongest sectors fast.',
    },
  },
}
