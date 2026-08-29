import { defineStore } from 'pinia'
import { ref } from 'vue'

/** 首页仪表盘 widget 的唯一标识 */
export type HomeWidgetId =
  | 'quick'
  | 'indexes'
  | 'breadth'
  | 'kline'
  | 'heatmap'
  | 'sectors'
  | 'news'
  | 'recommend'
  | 'allocation'
  | 'srchealth'

/** 默认布局顺序（首次使用 / 重置布局时恢复） */
export const DEFAULT_HOME_ORDER: HomeWidgetId[] = [
  'quick',
  'indexes',
  'breadth',
  'kline',
  'heatmap',
  'sectors',
  'news',
  'recommend',
  'allocation',
  'srchealth',
]

/**
 * 首页可拖拽仪表盘的布局状态，持久化到 localStorage（key: emoqunt:homeLayout）。
 * 仅保存 widget 渲染顺序；拖拽重排后自动写回。
 */
export const useHomeLayoutStore = defineStore(
  'homeLayout',
  () => {
    const order = ref<HomeWidgetId[]>([...DEFAULT_HOME_ORDER])

    /** 将 from 位置的 widget 移动到 to 位置（其余相对顺序不变） */
    function move(from: number, to: number) {
      if (from === to) return
      const next = [...order.value]
      const [item] = next.splice(from, 1)
      if (item === undefined) return
      next.splice(to, 0, item)
      order.value = next
    }

    /** 恢复默认布局顺序 */
    function reset() {
      order.value = [...DEFAULT_HOME_ORDER]
    }

    return { order, move, reset }
  },
  {
    persist: {
      pick: ['order'],
      // 兼容历史/脏数据：只保留已知 widget，缺失的按默认顺序补在末尾，
      // 保证 8 个 widget 永远完整渲染。
      revive: (s) => {
        const deduped = [...new Set(Array.isArray(s.order) ? (s.order as unknown[]) : [])]
        const saved = deduped.filter(
          (id): id is HomeWidgetId => typeof id === 'string' && (DEFAULT_HOME_ORDER as readonly string[]).includes(id),
        )
        const rest = DEFAULT_HOME_ORDER.filter((id) => !saved.includes(id))
        return { order: [...saved, ...rest] }
      },
    },
  },
)
