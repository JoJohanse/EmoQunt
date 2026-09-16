import { t } from '@/locales'

/**
 * 首页首访导览（driver.js，动态 import 不进主 chunk；MIT / ~5KB / 零依赖）。
 * 对标 v4 调研结论： Tours 多步导览 + "看过不再弹"（ui store 持久化），
 * 后续新功能可对老用户做单点 Hints。
 */

interface TourStepDef {
  el: string
  /** i18n 键（tour.steps.*）；文案在 startHomeTour() 内即时取值，按启动时的语言渲染 */
  titleKey: string
  descKey: string
}

/** 首页导览步骤：启动时按元素存在性过滤（widget 可拖拽重排、卡片可能空态） */
const HOME_TOUR_STEPS: TourStepDef[] = [
  { el: '.quick-row', titleKey: 'tour.steps.quick.title', descKey: 'tour.steps.quick.desc' },
  { el: '.index-row', titleKey: 'tour.steps.indexes.title', descKey: 'tour.steps.indexes.desc' },
  { el: '.kline-card', titleKey: 'tour.steps.kline.title', descKey: 'tour.steps.kline.desc' },
  { el: '.watch-add', titleKey: 'tour.steps.watchlist.title', descKey: 'tour.steps.watchlist.desc' },
  { el: '.history-list', titleKey: 'tour.steps.history.title', descKey: 'tour.steps.history.desc' },
  { el: '.breadth-card', titleKey: 'tour.steps.breadth.title', descKey: 'tour.steps.breadth.desc' },
  { el: '.heatmap-card', titleKey: 'tour.steps.heatmap.title', descKey: 'tour.steps.heatmap.desc' },
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
    popover: { title: t(s.titleKey), description: t(s.descKey) },
  }))
  ui.tourDone = true // 弹出过一次即标记（完成或关闭都算），避免刷新反复打扰
  if (!steps.length) return

  const [{ driver }, css] = await Promise.all([
    import('driver.js'),
    import('driver.js/dist/driver.css'),
  ])
  void css

  // driver 的按钮文案同样按启动时的语言快照（导览运行中不随语言热切换）
  const driverObj = driver({
    steps,
    showProgress: true,
    nextBtnText: t('tour.next'),
    prevBtnText: t('tour.prev'),
    doneBtnText: t('tour.done'),
  })
  driverObj.drive()
}
