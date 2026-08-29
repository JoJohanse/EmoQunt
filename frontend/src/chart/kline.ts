import type { Market } from '@/api/types'
import { chartPalette } from '@/lib/marketColors'

/**
 * 蜡烛图 option 组装器（纯函数 module，无框架依赖）。
 *
 * 收拢首页看板与回测页两处 K 线图的七组重复视觉事实，供两视图共享 scaffold：
 *   1. 市场涨跌配色（消费 lib/marketColors 的 chartPalette）；
 *   2. 蜡烛 itemStyle（阳线/阴线四元组）；
 *   3. 十字光标（tooltip cross + 多窗格联动，统一轴标签底色）；
 *   4. inside + slider 缩放（最小窗口 15%、滚轮缩放、18px 滑块）；
 *   5. 价格轴/tooltip 数值格式（fmtPriceNum，唯一实现）；
 *   6. 类目 x 轴（boundaryGap / dataMin-dataMax / onZero=false / 隐刻度）；
 *   7. tooltip 前收涨跌计算（首根回退开盘价口径）。
 *
 * 分层原则：本模块只负责「骨架」，不做 20 参数浅函数——
 *   - 指标叠加（MA/BOLL/MACD/KDJ/RSI 序列、三窗格 grid 组装）留在 HomeView；
 *   - 买卖点注记（markPoint/markLine）留在 BacktestView。
 */

/** 单根 K 线：[open, close, low, high]（与 /api/kline ohlcv 契约一致，注意不是 OHLC 习惯序） */
export type KlineBar = [number, number, number, number]

// ===== 5) 价格数值格式 =====

/**
 * 价格轴/tooltip 数值格式：千分位；≥1000 的指数点位省去小数，
 * 避免宽标签溢出网格边距被裁剪。两视图唯一实现。
 */
export function fmtPriceNum(v: number): string {
  const dec = Math.abs(v) >= 1000 ? 0 : 2
  return v.toLocaleString('zh-CN', { minimumFractionDigits: dec, maximumFractionDigits: dec })
}

// ===== 2) 蜡烛 itemStyle =====

/** 蜡烛涨跌 itemStyle：color=阳线、color0=阴线（市场配色 token，A股红涨绿跌/美股绿涨红跌） */
export function candleItemStyle(market: Market) {
  const { up, down } = chartPalette(market)
  return { color: up, color0: down, borderColor: up, borderColor0: down }
}

// ===== 3) 十字光标 =====

/** 十字光标轴标签底色（两视图统一的深灰蓝） */
export const CROSSHAIR_LABEL_BG = '#6a7985'

/** tooltip 十字光标（type: cross + 统一标签底色） */
export function crosshairPointer() {
  return { type: 'cross', label: { backgroundColor: CROSSHAIR_LABEL_BG } }
}

/** 多窗格十字光标联动（option 根级 axisPointer，HomeView 三窗格用） */
export function linkedCrosshair() {
  return { link: [{ xAxisIndex: 'all' as const }], label: { backgroundColor: CROSSHAIR_LABEL_BG } }
}

// ===== 4) 缩放（inside + slider） =====

export interface KlineDataZoomOptions {
  /** 绑定的 x 轴索引（多窗格传 [0,1,2]）；缺省不绑定，作用于全部 x 轴 */
  xAxisIndex?: number[]
  /** 初始窗口起点（百分比），默认 0（回测页展示全区间） */
  start?: number
  /** slider 顶部定位（多窗格布局，百分比字符串，含 left/right 边距） */
  sliderTop?: string
  /** slider 底部定位（单窗格布局，像素） */
  sliderBottom?: number
  /** inside 滚轮缩放时阻止页面随之滚动（首页长页面嵌图需要） */
  preventDefaultMouseMove?: boolean
}

/**
 * K线图统一缩放组件：inside 滚轮缩放（最小窗口 15%）+ 18px slider。
 * 滑块定位二选一：多窗格传 sliderTop（含 7%/4% 左右边距），单窗格传 sliderBottom。
 */
export function klineDataZoom(o: KlineDataZoomOptions = {}) {
  const bind = o.xAxisIndex ? { xAxisIndex: o.xAxisIndex } : {}
  const sliderPos = o.sliderTop
    ? { left: '7%', right: '4%', top: o.sliderTop }
    : { bottom: o.sliderBottom ?? 12 }
  return [
    {
      type: 'inside',
      ...bind,
      start: o.start ?? 0,
      end: 100,
      minValueSpan: 15,
      zoomOnMouseWheel: true,
      moveOnMouseMove: true,
      ...(o.preventDefaultMouseMove ? { preventDefaultMouseMove: true } : {}),
    },
    { type: 'slider', ...bind, ...sliderPos, height: 18, start: o.start ?? 0, end: 100 },
  ]
}

// ===== 6) 类目 x 轴 =====

/** 月度刻度策略（对标 Lightweight Charts tickMarkFormatter）：按月边界取刻度，1月显示年份 */
export function monthTickConfig(dates: string[]): {
  interval: (index: number) => boolean
  formatter: (v: string) => string
} {
  let last = ''
  const flags = dates.map((d) => {
    const ym = d.slice(0, 7)
    const show = ym !== last
    last = ym
    return show
  })
  return {
    interval: (index: number) => Boolean(flags[index]),
    formatter: (v: string) => {
      const [y, m] = v.split('-')
      return m === '01' ? `${y}年` : `${Number(m)}月`
    },
  }
}

export interface KlineXAxisOptions {
  /** 类目数据（日期字符串数组） */
  data: string[]
  /** 所属窗格（多窗格 grid 索引），默认 0 */
  gridIndex?: number
  /** 是否显示轴标签（多窗格中间轴隐藏）；缺省走 ECharts 默认刻度 */
  labelShow?: boolean
  /** 月度刻度策略（传 monthTickConfig 结果）；labelShow=true 且未传时用 ECharts 默认 */
  ticks?: { interval: (index: number) => boolean; formatter: (v: string) => string }
}

/** K线图类目 x 轴 scaffold：boundaryGap / dataMin-dataMax / onZero=false / 隐刻度 */
export function klineXAxis(o: KlineXAxisOptions) {
  return {
    type: 'category',
    gridIndex: o.gridIndex ?? 0,
    data: o.data,
    boundaryGap: true,
    axisLine: { onZero: false },
    axisTick: { show: false },
    axisLabel:
      o.labelShow === false
        ? { show: false }
        : o.ticks
          ? { show: true, interval: o.ticks.interval, formatter: o.ticks.formatter }
          : {},
    splitLine: { show: false },
    min: 'dataMin',
    max: 'dataMax',
  }
}

// ===== 7) tooltip 前收涨跌 =====

/** tooltip 涨跌上下文：prev=前收（首根回退为当根开盘价），chgPct=相对前收涨跌幅（%） */
export function chgVsPrevClose(
  ohlcv: readonly KlineBar[],
  idx: number,
): { prev: number; chgPct: number } {
  const o = ohlcv[idx]
  const prev = o && idx > 0 ? ohlcv[idx - 1]![1] : (o?.[0] ?? 0)
  return { prev, chgPct: prev ? ((o![1]! / prev - 1) * 100) : 0 }
}
