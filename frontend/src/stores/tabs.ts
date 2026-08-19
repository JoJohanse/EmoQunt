import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { RouteLocationNormalized } from 'vue-router'

export interface TabItem {
  path: string
  title: string
}

/**
 * 顶部标签页（持久化到 emoqunt:tabs，仅存 visited）。
 * 首页 "/" 不可关闭。
 */
export const useTabsStore = defineStore(
  'tabs',
  () => {
    const visited = ref<TabItem[]>([{ path: '/', title: '首页' }])

    function addTab(route: RouteLocationNormalized) {
      const title = (route.meta.title as string) || route.path
      if (!visited.value.some((t) => t.path === route.path)) {
        visited.value.push({ path: route.path, title })
      } else {
        // 同路径但标题可能变化，同步更新
        const t = visited.value.find((x) => x.path === route.path)
        if (t) t.title = title
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
      visited.value = [{ path: '/', title: '首页' }]
    }

    return { visited, addTab, removeTab, closeOthers, closeAll }
  },
  { persist: { pick: ['visited'] } },
)
