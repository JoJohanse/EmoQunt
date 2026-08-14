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
}

/** 首次使用时的默认自选（与首页原有预设标的一致） */
const DEFAULT_ITEMS: WatchlistItem[] = [
  { code: '000001', market: 'zh_a', name: '上证指数', addedAt: '' },
  { code: '000300', market: 'zh_a', name: '沪深300', addedAt: '' },
  { code: '399001', market: 'zh_a', name: '深证成指', addedAt: '' },
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
  { persist: true },
)
