import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { Market } from '@/api/types'

/** 自选股条目 */
export interface WatchlistItem {
  code: string
  market: Market
  /** 展示名（添加时从行情接口解析，可被用户修改） */
  name: string
  /** 添加时间（ISO 字符串） */
  addedAt: string
  /** 指数标记：kind=index 时行情走服务端指数数据链（000001 等二义代码需要） */
  kind?: 'index'
}

/** 首次使用时的默认自选（与首页原有预设标的一致） */
const DEFAULT_ITEMS: WatchlistItem[] = [
  { code: '000001', market: 'zh_a', name: '上证指数', addedAt: '', kind: 'index' },
  { code: '000300', market: 'zh_a', name: '沪深300', addedAt: '', kind: 'index' },
  { code: '399001', market: 'zh_a', name: '深证成指', addedAt: '', kind: 'index' },
  { code: 'AAPL', market: 'us', name: 'Apple', addedAt: '' },
  { code: 'MSFT', market: 'us', name: 'Microsoft', addedAt: '' },
  { code: 'TSLA', market: 'us', name: 'Tesla', addedAt: '' },
]

/**
 * 标的唯一键：`code|market|kind`。
 * 第三段区分二义代码（如 A股 000001 既可能是上证指数也可能是平安银行），
 * 首页主图选中态、行情缓存、跳转预选全部以此为键。
 */
export function targetKey(code: string, market: Market, kind?: '' | 'index'): string {
  return `${code}|${market}|${kind ?? ''}`
}

/** A 股代码归一：每日推荐/工具结果常带 .SZ/.SH 交易所后缀，自选与主图统一用裸 6 位代码 */
function normalizeCode(code: string, market: Market): string {
  const trimmed = code.trim()
  if (market === 'us') return trimmed.toUpperCase()
  return trimmed.replace(/\.(SZ|SH|BJ)$/i, '')
}

/**
 * 自选股（watchlist），持久化到 localStorage。
 * 对标 Ghostfolio / 雪球等投资应用：自选是首屏第一公民。
 */
export const useWatchlistStore = defineStore(
  'watchlist',
  () => {
    const items = ref<WatchlistItem[]>([...DEFAULT_ITEMS])
    /** 首页主图上次查看的标的（键为 `code|market|kind`），持久化 */
    const lastKey = ref('')

    function has(code: string, market: Market, kind?: 'index'): boolean {
      return items.value.some(
        (i) => i.code === code && i.market === market && (i.kind ?? '') === (kind ?? ''),
      )
    }

    /** 添加自选（已存在则返回 false；A 股代码自动剥交易所后缀） */
    function add(code: string, market: Market, name: string, kind?: 'index'): boolean {
      const normalized = normalizeCode(code, market)
      if (!normalized || has(normalized, market, kind)) return false
      items.value.push({
        code: normalized,
        market,
        name: name || normalized,
        addedAt: new Date().toISOString(),
        kind,
      })
      return true
    }

    function remove(code: string, market: Market, kind?: 'index') {
      items.value = items.value.filter(
        (i) => !(i.code === code && i.market === market && (i.kind ?? '') === (kind ?? '')),
      )
    }

    function rename(code: string, market: Market, name: string) {
      const item = items.value.find((i) => i.code === code && i.market === market)
      if (item) item.name = name || item.code
    }

    /** 按唯一键查找条目 */
    function findByKey(key: string): WatchlistItem | undefined {
      return items.value.find((i) => targetKey(i.code, i.market, i.kind) === key)
    }

    /**
     * 确保标的存在于自选并返回其唯一键（供聊天卡片/推荐卡片"在首页打开主图"：
     * 主图标的来源于自选列表，未跟踪时先加入）。
     */
    function ensureTracked(code: string, market: Market, name: string, kind?: 'index'): string {
      const normalized = normalizeCode(code, market)
      const found = items.value.find(
        (i) => i.code === normalized && i.market === market && (i.kind ?? '') === (kind ?? ''),
      )
      if (found) return targetKey(found.code, found.market, found.kind)
      add(normalized, market, name, kind)
      return targetKey(normalized, market, kind)
    }

    /**
     * 「跳首页主图预选标的」协议收口：确保标的已跟踪（未跟踪时先加入自选）并写入
     * lastKey（统一为 targetKey 的 `code|market|kind` 格式），返回最终键。
     * 不负责导航——调用方自行 router.push('/')；首页监听 lastKey 切换主图。
     */
    function openChartOnHome(target: { code: string; market: Market; name?: string; kind?: 'index' }): string {
      const key = ensureTracked(target.code, target.market, target.name ?? target.code, target.kind)
      lastKey.value = key
      return key
    }

    return { items, lastKey, has, add, remove, rename, findByKey, ensureTracked, openChartOnHome }
  },
  {
    persist: {
      // 迁移：旧持久化数据无 kind 字段，按默认自选的三个指数代码回填，
      // 使「上证指数/沪深300/深证成指」继续走服务端指数链而非个股链
      revive: (s) => {
        const INDEX_KEYS = new Set(['000001|zh_a', '000300|zh_a', '399001|zh_a'])
        if (Array.isArray(s.items)) {
          for (const it of s.items) {
            if (it && !it.kind && INDEX_KEYS.has(`${it.code}|${it.market}`)) it.kind = 'index'
          }
        }
        return s
      },
    },
  },
)
