/**
 * 首页首访导览（driver.js，动态 import 不进主 chunk；MIT / ~5KB / 零依赖）。
 * 对标 v4 调研结论： Tours 多步导览 + "看过不再弹"（ui store 持久化），
 * 后续新功能可对老用户做单点 Hints。
 */

interface TourStepDef {
  el: string
  title: string
  desc: string
}

/** 首页导览步骤：启动时按元素存在性过滤（widget 可拖拽重排、卡片可能空态） */
const HOME_TOUR_STEPS: TourStepDef[] = [
  { el: '.quick-row', title: '快捷入口', desc: '回测、因子分析、舆情等核心功能一键直达。' },
  { el: '.index-row', title: '指数速览', desc: '大盘三大指数快照，点击任意指数卡片即可在下方主图查看。' },
  {
    el: '.kline-card',
    title: '行情看板',
    desc: 'K 线主图支持周期/复权切换、MA/BOLL 叠加与 MACD/KDJ/RSI 副图；点击右侧自选股可切换标的。',
  },
  { el: '.watch-add', title: '自选股', desc: '输入代码即可添加自选（A股/美股），列表行内展示最新价与涨跌走势。' },
  { el: '.history-list', title: '最近回测', desc: '本地保留最近回测摘要，点击"重跑"一键回填参数。' },
  { el: '.breadth-card', title: '市场宽度', desc: '涨跌家数与涨停/跌停分布，一屏判断当日市场情绪。' },
  { el: '.heatmap-card', title: '行业热力图', desc: '面积=成交额、颜色=涨跌幅，快速定位强势行业。' },
]

/**
 * 启动首页导览。完成后（含中途关闭）写入 ui store（persist 到 localStorage），下次不再自动弹出。
 * 仅当页面上至少存在一个可导览元素时才启动。
 */
export async function startHomeTour(): Promise<void> {
  const { useUiStore } = await import('@/stores/ui')
  const ui = useUiStore()

  const steps = HOME_TOUR_STEPS.filter((s) => document.querySelector(s.el)).map((s) => ({
    element: s.el,
    popover: { title: s.title, description: s.desc },
  }))
  ui.tourDone = true // 弹出过一次即标记（完成或关闭都算），避免刷新反复打扰
  if (!steps.length) return

  const [{ driver }, css] = await Promise.all([
    import('driver.js'),
    import('driver.js/dist/driver.css'),
  ])
  void css

  const driverObj = driver({
    steps,
    showProgress: true,
    nextBtnText: '下一步',
    prevBtnText: '上一步',
    doneBtnText: '完成',
  })
  driverObj.drive()
}
