import { locale } from '@/locales'

/**
 * 数值/货币格式化 token module ——「按当前语言格式化数字」这条规格的唯一事实源
 * （此前各视图字面写 `toLocaleString('zh-CN', ...)`，英文界面下仍出中文千分位/万·亿）。
 *
 * 分层原则（对标 lib/marketColors.ts）：本模块只依赖 i18n 的 locale ref，不引 Vue 组件、
 * 不碰 DOM；图表配置器（chart/kline.ts）与视图/组件共用同一出口。
 * t() 的调用结果不在这里缓存——locale.value 每次读取都参与响应式依赖收集。
 */

/** Intl 区域标识：仅 en-US 走英文，其余（含默认 zh-CN）一律 zh-CN */
function intlLocale(): string {
  return locale.value === 'en-US' ? 'en-US' : 'zh-CN'
}

/** 千分位数字格式化（可选 Intl 选项，如 minimumFractionDigits/percent 等），随当前语言分组 */
export function fmtNum(value: number, opts?: Intl.NumberFormatOptions): string {
  return value.toLocaleString(intlLocale(), opts)
}

/**
 * 大数缩写：zh 用 万 / 亿，en 用 K / M / B（成交额、市值等宽口径展示）。
 * 阈值：en <1e3 原值 → K → M → B；zh <1e4 原值 → 万 → 亿。
 */
export function fmtBigNum(value: number): string {
  if (!Number.isFinite(value)) return String(value)
  const abs = Math.abs(value)
  if (locale.value === 'en-US') {
    if (abs < 1_000) return fmtNum(value, { maximumFractionDigits: 2 })
    if (abs < 1_000_000) return `${fmtNum(value / 1_000, { maximumFractionDigits: 2 })}K`
    if (abs < 1_000_000_000) return `${fmtNum(value / 1_000_000, { maximumFractionDigits: 2 })}M`
    return `${fmtNum(value / 1_000_000_000, { maximumFractionDigits: 2 })}B`
  }
  if (abs < 10_000) return fmtNum(value, { maximumFractionDigits: 2 })
  if (abs < 100_000_000) return `${fmtNum(value / 10_000, { maximumFractionDigits: 2 })}万`
  return `${fmtNum(value / 100_000_000, { maximumFractionDigits: 2 })}亿`
}

/**
 * 货币金额：us → `$` 前缀、zh_a → `¥` 前缀，千分位分组随当前语言。
 * 注意市场决定符号（与 lib/marketColors 的 market 口径一致），语言只决定分组/小数点写法。
 */
export function fmtCurrency(value: number, market: 'zh_a' | 'us'): string {
  const n = fmtNum(value, { minimumFractionDigits: 2, maximumFractionDigits: 2 })
  return market === 'us' ? `$${n}` : `¥${n}`
}
