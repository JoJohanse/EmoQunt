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
 * 自选股（watchlist），持久化到 localStorage。
 * 对标 Ghostfolio / 雪球等投资应用：自选是首屏第一公民。
 */
export const useWatchlistStore = defineStore(
  'watchlist',
  () => {
    const items = ref<WatchlistItem[]>([...DEFAULT_ITEMS])
    /** 首页主图上次查看的标的（键为 `code|market`），持久化 */
    const lastKey = ref('')

    function has(code: string, market: Market): boolean {
      return items.value.some((i) => i.code === code && i.market === market)
    }

    /** 添加自选（已存在则返回 false） */
    function add(code: string, market: Market, name: string): boolean {
      const normalized = code.trim()
      if (!normalized || has(normalized, market)) return false
      items.value.push({
        code: normalized,
        market,
        name: name || normalized,
        addedAt: new Date().toISOString(),
      })
      return true
    }

    function remove(code: string, market: Market) {
      items.value = items.value.filter((i) => !(i.code === code && i.market === market))
    }

    function rename(code: string, market: Market, name: string) {
      const item = items.value.find((i) => i.code === code && i.market === market)
      if (item) item.name = name || item.code
    }

    return { items, lastKey, has, add, remove, rename }
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
