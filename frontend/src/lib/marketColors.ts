import type { Market } from '@/api/types'

/**
 * 市场涨跌配色 token module ——「A股红涨绿跌 / 美股绿涨红跌 / 0=中性」这条业务规格
 * 的唯一事实源（此前散布在各视图的字面色统一收口到这里）。
 *
 * 两个出口按消费场景区分，禁止混用：
 *   - chartPalette：ECharts hex（画布内无法解析 CSS 变量），供图表序列/迷你走势线用；
 *   - deltaColor / deltaTone：CSS 侧（var(--danger)/var(--success)/var(--neutral)），供 DOM 徽章/文字用。
 * 评分色 scoreColor 与涨跌方向无关，单独命名，勿与涨跌方向色混用；
 * 板块情绪三档 sectorColor、推荐列表三档 recommendScoreColor 亦为独立语义，各自命名，勿互相混并。
 */

/** ECharts 蜡烛/柱状的涨跌 hex（沿用既有视觉值） */
export interface ChartPalette {
  /** 上涨 / 阳线 / 正收益 */
  up: string
  /** 下跌 / 阴线 / 负收益 */
  down: string
  /** 上涨文字色（tooltip 等浅底场景） */
  upText: string
  /** 下跌文字色 */
  downText: string
}

const CHART_PALETTES: Record<Market, ChartPalette> = {
  // A股：红涨绿跌
  zh_a: { up: '#ef232a', down: '#14b143', upText: '#dc2626', downText: '#059669' },
  // 美股：绿涨红跌
  us: { up: '#26a69a', down: '#ef5350', upText: '#059669', downText: '#dc2626' },
}

/** 市场涨跌图表配色：A股红涨绿跌 / 美股绿涨红跌 */
export function chartPalette(market: Market): ChartPalette {
  return CHART_PALETTES[market] ?? CHART_PALETTES.zh_a
}

/** 中性（平盘）在图表中的 hex；CSS 侧请走 deltaColor → var(--neutral) */
export const NEUTRAL_HEX = '#9ca3af'

// ===== CSS 侧涨跌色（DOM 徽章 / 文字） =====

/** 涨跌方向：0 归一为中性平盘 */
export type DeltaDirection = 'up' | 'down' | 'flat'

/** 语义色调：danger=红 / success=绿 / neutral=中性（对应 --danger/--success/--neutral） */
export type DeltaTone = 'danger' | 'success' | 'neutral'

/** 原始涨跌幅 → 方向（0 归一为平盘） */
export function deltaDirection(chgPct: number): DeltaDirection {
  return chgPct > 0 ? 'up' : chgPct < 0 ? 'down' : 'flat'
}

/** 方向 → 语义色调：A股 up=danger（红涨），美股 up=success（绿涨）；平盘恒为 neutral */
export function deltaTone(market: Market, dir: DeltaDirection): DeltaTone {
  if (dir === 'flat') return 'neutral'
  return (dir === 'up') === (market !== 'us') ? 'danger' : 'success'
}

/**
 * CSS 涨跌色：返回 CSS 变量引用（var(--danger)/var(--success)/var(--neutral)），
 * 供 DOM 涨跌徽章/文字消费。第二参数接受方向或原始涨跌幅。
 */
export function deltaColor(market: Market, dirOrPct: DeltaDirection | number): string {
  const dir = typeof dirOrPct === 'number' ? deltaDirection(dirOrPct) : dirOrPct
  switch (deltaTone(market, dir)) {
    case 'danger':
      return 'var(--danger)'
    case 'success':
      return 'var(--success)'
    default:
      return 'var(--neutral)'
  }
}

// ===== 评分色（与涨跌方向无关，单独命名） =====

/** 多因子/情绪评分 → 颜色：≥70 绿 / ≥60 紫 / ≥45 橙 / 其余红 */
export function scoreColor(v: number): string {
  if (v >= 70) return '#28a745'
  if (v >= 60) return '#667eea'
  if (v >= 45) return '#f59e0b'
  return '#dc3545'
}

/**
 * 板块情绪分三档色：≥70 绿(#28a745) / ≤40 红(#dc3545) / 其余灰(#6c757d)。
 * 与 scoreColor 是不同语义：这是板块情绪的三档口径（40-70 为中性灰，无紫/橙档），
 * 勿混并。消费方：首页「热门板块」、舆情分析、情绪日历。
 */
export function sectorColor(v: number): string {
  if (v >= 70) return '#28a745'
  if (v <= 40) return '#dc3545'
  return '#6c757d'
}

/**
 * 每日推荐列表评分三档色：≥70 绿(#28a745) / ≥60 紫(#667eea) / 其余橙(#f59e0b)。
 * 与四档 scoreColor 的差异：<60 一律橙、不落红档（scoreColor 对 <45 返回红）。
 * 推荐列表两处消费（首页「个股推荐」/「每日推荐」）历史口径即此三档，按零视觉变化收拢。
 */
export function recommendScoreColor(v: number): string {
  if (v >= 70) return '#28a745'
  if (v >= 60) return '#667eea'
  return '#f59e0b'
}
