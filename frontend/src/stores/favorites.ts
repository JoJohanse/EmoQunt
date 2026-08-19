import { defineStore } from 'pinia'
import { ref } from 'vue'

/**
 * 侧边栏收藏（持久化到 localStorage，键 emoqunt:favorites）。
 * 存路由 path 数组，渲染时按 router meta.title 解析标题。
 */
export const useFavoritesStore = defineStore(
  'favorites',
  () => {
    const paths = ref<string[]>([])

    function isFavorite(path: string): boolean {
      return paths.value.includes(path)
    }

    function toggle(path: string) {
      if (isFavorite(path)) {
        paths.value = paths.value.filter((p) => p !== path)
      } else {
        paths.value.push(path)
      }
    }

    return { paths, isFavorite, toggle }
  },
  { persist: true },
)
