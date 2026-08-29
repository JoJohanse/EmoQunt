import { defineStore } from 'pinia'
import { ref } from 'vue'

/** K线周期 */
export type KlinePeriod = 'day' | 'week' | 'month'
/** 复权方式 */
export type KlineAdjust = 'qfq' | 'hfq' | 'nfq'
/** 主图叠加指标 */
export type OverlayMode = 'none' | 'ma' | 'boll'
/** 副图指标 */
export type SubIndicator = 'none' | 'macd' | 'kdj' | 'rsi'

const PERIODS = ['day', 'week', 'month'] as const
const ADJUSTS = ['qfq', 'hfq', 'nfq'] as const
const OVERLAYS = ['none', 'ma', 'boll'] as const
const SUBS = ['none', 'macd', 'kdj', 'rsi'] as const

/**
 * K线工具栏偏好（周期/复权/主图叠加/副图指标）。
 * 持久化回归 persist 插件（键 `emoqunt:klinePrefs`）；revive 兼职旧裸键清理与值校验。
 */

/** persist 插件接入前的旧裸键（HomeView 直读写 localStorage 的遗留） */
const LEGACY_KEYS = [
  'emoqunt:kline_period',
  'emoqunt:kline_adjust',
  'emoqunt:kline_overlay',
  'emoqunt:kline_sub',
  // 更旧的「主图 MA 开关」布尔键：false → 主图叠加=无
  'emoqunt:kline_ma',
] as const

/** 枚举校验：仅接受合法字符串值，其余视为不存在 */
function pickValid<T extends string>(v: unknown, allowed: readonly T[]): T | undefined {
  return typeof v === 'string' && (allowed as readonly string[]).includes(v) ? (v as T) : undefined
}

/** 读取旧裸键（JSON 解析 + 枚举校验，损坏/越界视为不存在） */
function readLegacy<T extends string>(key: string, allowed: readonly T[]): T | undefined {
  try {
    const raw = localStorage.getItem(key)
    return raw === null ? undefined : pickValid(JSON.parse(raw), allowed)
  } catch {
    return undefined
  }
}

/** 旧「MA 开关」→ 主图叠加：false → 'none'；缺省/true → 'ma'（与旧默认一致） */
function readLegacyMaSwitch(): OverlayMode {
  try {
    const raw = localStorage.getItem('emoqunt:kline_ma')
    if (raw === null) return 'ma'
    return JSON.parse(raw) === false ? 'none' : 'ma'
  } catch {
    return 'ma'
  }
}

/** 删除旧裸键（迁移收尾，try/catch 静默降级） */
function removeLegacyKeys() {
  for (const k of LEGACY_KEYS) {
    try { localStorage.removeItem(k) } catch { /* 隐私模式等，忽略 */ }
  }
}

export const useKlinePrefsStore = defineStore(
  'klinePrefs',
  () => {
    // 旧键迁移的「读取初值」必须在 setup 做：persist 插件仅在新键已存在时才调用 revive，
    // 首次升级运行（尚无 `emoqunt:klinePrefs`）时只有这里能接住旧偏好。
    const period = ref<KlinePeriod>(readLegacy<KlinePeriod>('emoqunt:kline_period', PERIODS) ?? 'day')
    const adjust = ref<KlineAdjust>(readLegacy<KlineAdjust>('emoqunt:kline_adjust', ADJUSTS) ?? 'qfq')
    // 叠加口径与旧逻辑一致：overlay 键有效值优先，否则回退旧「MA 开关」（缺省 → 'ma'）
    const overlay = ref<OverlayMode>(
      readLegacy<OverlayMode>('emoqunt:kline_overlay', OVERLAYS) ?? readLegacyMaSwitch(),
    )
    const sub = ref<SubIndicator>(readLegacy<SubIndicator>('emoqunt:kline_sub', SUBS) ?? 'macd')
    return { period, adjust, overlay, sub }
  },
  {
    persist: {
      pick: ['period', 'adjust', 'overlay', 'sub'],
      revive: (s) => {
        // 走到 revive ⇒ 新键已存在（此前成功持久化过），旧裸键此时删除才不丢数据
        removeLegacyKeys()
        // 越界字段剔除：$patch 跳过缺失键，该字段回落 setup 初值/默认
        if (pickValid(s.period, PERIODS) === undefined) delete s.period
        if (pickValid(s.adjust, ADJUSTS) === undefined) delete s.adjust
        if (pickValid(s.overlay, OVERLAYS) === undefined) delete s.overlay
        if (pickValid(s.sub, SUBS) === undefined) delete s.sub
        return s
      },
    },
  },
)
