import { defineStore } from 'pinia'
import { ref, watch } from 'vue'

/**
 * UI 偏好（暗色主题、侧边栏折叠），持久化到 localStorage。
 * 刷新后保持用户的界面习惯（对标管理后台模板的通行做法）。
 */
export const useUiStore = defineStore(
  'ui',
  () => {
    const theme = ref<'light' | 'dark'>('light')
    const sidebarCollapsed = ref(false)

    function toggleTheme() {
      theme.value = theme.value === 'dark' ? 'light' : 'dark'
    }
    function toggleSidebar() {
      sidebarCollapsed.value = !sidebarCollapsed.value
    }

    // 主题应用到 <html> 的 dark class（Element Plus 暗色变量 + main.css 覆写）
    watch(
      theme,
      (t) => {
        document.documentElement.classList.toggle('dark', t === 'dark')
      },
      { immediate: true },
    )

    return { theme, sidebarCollapsed, toggleTheme, toggleSidebar }
  },
  { persist: { pick: ['theme', 'sidebarCollapsed'] } },
)
