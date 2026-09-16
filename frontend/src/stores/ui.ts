import { defineStore } from 'pinia'
import { ref, watch } from 'vue'
import { setLocale } from '@/locales'
import type { Locale } from '@/locales'

/**
 * UI 偏好（暗色主题、侧边栏折叠、首访导览标记、界面语言），持久化到 localStorage。
 * 刷新后保持用户的界面习惯（对标管理后台模板的通行做法）。
 *
 * 语言只持久化 lang 这个标识本身，翻译结果一律由 locales 的 t() 现算——
 * 持久化 store 中不得出现 t() 的输出（换语言即失效）。
 */
export const useUiStore = defineStore(
  'ui',
  () => {
    const theme = ref<'light' | 'dark'>('light')
    const sidebarCollapsed = ref(false)
    /** 首页首访导览是否已完成（完成或手动关闭都算），避免反复打扰 */
    const tourDone = ref(false)

    /**
     * 界面语言初值：优先读后端同源的 emoqunt_lang cookie（Jinja2 侧 /set-lang 或
     * setLocale 写入），让两套前端的首次访问体验一致；SPA 自身的 localStorage
     * 偏好（persist 插件恢复）优先生效，二者都缺省时回落中文。
     */
    function initialLang(): Locale {
      const m = document.cookie.match(/(?:^|;\s*)emoqunt_lang=(zh-CN|en-US)(?:;|$)/)
      return m ? (m[1] as Locale) : 'zh-CN'
    }
    const lang = ref<Locale>(initialLang())

    function toggleTheme() {
      theme.value = theme.value === 'dark' ? 'light' : 'dark'
    }
    function toggleSidebar() {
      sidebarCollapsed.value = !sidebarCollapsed.value
    }
    function toggleLang() {
      lang.value = lang.value === 'zh-CN' ? 'en-US' : 'zh-CN'
      setLocale(lang.value)
    }

    // 主题应用到 <html> 的 dark class（Element Plus 暗色变量 + main.css 覆写）
    watch(
      theme,
      (t) => {
        document.documentElement.classList.toggle('dark', t === 'dark')
      },
      { immediate: true },
    )

    // 语言同步到 i18n 引擎（setLocale 负责 <html lang>）；immediate 保证首屏即生效
    watch(lang, (l) => setLocale(l), { immediate: true })

    return { theme, sidebarCollapsed, tourDone, lang, toggleTheme, toggleSidebar, toggleLang }
  },
  { persist: { pick: ['theme', 'sidebarCollapsed', 'tourDone', 'lang'] } },
)
