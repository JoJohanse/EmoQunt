import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { RouteLocationNormalized } from 'vue-router'

export interface TabItem {
  path: string
  /**
   * i18n 标题键（来自路由 meta.titleKey，如 'layout.nav.backtest'）。
   * 只存键、不存译文：语言切换后由 AppTabs 用 t() 现算；
   * 未知路由（无 meta.titleKey）为空串，渲染时按 path 反查或回退 path 本身。
   */
  titleKey: string
}

/** 首页标签（path 与 router/index.ts 的路由表 / 一致，标题键走共享的 nav.* 契约） */
const HOME_TAB: TabItem = { path: '/', titleKey: 'layout.nav.home' }

/** 从路由 meta 取标题键：缺失或非字符串一律归一为空串 */
function titleKeyOf(route: RouteLocationNormalized): string {
  const key = route.meta.titleKey
  return typeof key === 'string' ? key : ''
}

/**
 * 顶部标签页（持久化到 emoqunt:tabs，仅存 visited）。
 * 首页 "/" 不可关闭。
 */
export const useTabsStore = defineStore(
  'tabs',
  () => {
    const visited = ref<TabItem[]>([{ ...HOME_TAB }])

    function addTab(route: RouteLocationNormalized) {
      const titleKey = titleKeyOf(route)
      const found = visited.value.find((t) => t.path === route.path)
      if (found) {
        // 同路径但标题键可能变化，同步更新
        found.titleKey = titleKey
      } else {
        visited.value.push({ path: route.path, titleKey })
      }
    }

    function removeTab(path: string) {
      if (path === '/') return
      visited.value = visited.value.filter((t) => t.path !== path)
    }

    function closeOthers(path: string) {
      visited.value = visited.value.filter((t) => t.path === path || t.path === '/')
    }

    function closeAll() {
      visited.value = [{ ...HOME_TAB }]
    }

    return { visited, addTab, removeTab, closeOthers, closeAll }
  },
  {
    persist: {
      pick: ['visited'],
      /**
       * 迁移：旧数据形如 `{ path, title }`，其中 title 是**已翻译的中文文案**（换语言即失效）。
       * 这里保留 path、丢弃 title 并改存 titleKey；旧记录没有键，留空串由 AppTabs 按 path 反查路由，
       * 查不到就显示 path（未知路由兜底）。同时保证首页标签始终存在且不可关闭。
       */
      revive: (state: Record<string, any>) => {
        const raw = Array.isArray(state.visited) ? state.visited : []
        const visited: TabItem[] = raw
          .filter((it: any) => it && typeof it.path === 'string' && it.path)
          .map((it: any) => ({
            path: it.path,
            titleKey: typeof it.titleKey === 'string' ? it.titleKey : '',
          }))
        if (!visited.some((it) => it.path === '/')) visited.unshift({ ...HOME_TAB })
        return { visited }
      },
    },
  },
)
