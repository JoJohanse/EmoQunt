import { ref } from 'vue'
import { en as commonEn, zh as commonZh } from './common'
import { en as layoutEn, zh as layoutZh } from './layout'
import { en as homeEn, zh as homeZh } from './home'
import { en as tourEn, zh as tourZh } from './tour'
import { en as backtestEn, zh as backtestZh } from './backtest'
import { en as compareEn, zh as compareZh } from './compare'
import { en as factorEn, zh as factorZh } from './factor'
import { en as sentimentEn, zh as sentimentZh } from './sentiment'
import { en as recommendEn, zh as recommendZh } from './recommend'
import { en as strategiesEn, zh as strategiesZh } from './strategies'
import { en as chatEn, zh as chatZh } from './chat'
import { en as paletteEn, zh as paletteZh } from './palette'

/**
 * 手写 i18n 引擎（零依赖）——只服务本 SPA 的 zh-CN / en-US 两语言。
 *
 * 为什么不用 vue-i18n：本项目前端坚持零新增依赖（见 stores/persist.ts 的手写持久化插件），
 * 且 vue-i18n 的严格类型/模块增强与 `vue-tsc -b` 的构建门禁摩擦较多；这里只需要
 * 「dot-path 查表 + {name} 插值 + 语言切换响应式」三件事，~60 行足够。
 *
 * ── 消息树 ──────────────────────────────────────────────────────────────
 * `messages[locale][namespace][...嵌套][key]`；每个模块文件导出 `zh` / `en` 两个 const，
 * namespace 就是文件名（见下）。嵌套对象随写随用，遍历按 `.` 逐层下钻，只取 string 叶子：
 *
 *   // locales/foo.ts
 *   import type { Messages } from './index'
 *   export const zh: Messages = { title: '标题', form: { submit: '提交' } }
 *   export const en: Messages = { title: 'Title', form: { submit: 'Submit' } }
 *
 * ── 用法 ────────────────────────────────────────────────────────────────
 *   t('layout.nav.home')                  // → '首页' / 'Home'
 *   t('backtest.done', { n: 3 })          // 插值 {n}
 *
 * t() 内部读取 `locale.value`，因此在模板 / computed / watch 中调用会自动建立依赖：
 * 语言切换即重渲染，无需手动刷新。
 *
 * ── 键名契约（视图翻译 agent 必读）────────────────────────────────────────
 * 1) namespace 白名单 = 文件名，恰好是这 12 个：
 *    common / layout / home / tour / backtest / compare / factor / sentiment /
 *    recommend / strategies / chat / palette
 * 2) 跨模块共享的导航键一律住在 layout.ts 的 nav 组下（路由 meta.titleKey 与
 *    CommandPalette 都引用它们），任何视图模块都不得重复定义：
 *      nav.home      首页       / Home
 *      nav.backtest  策略回测   / Backtest
 *      nav.strategies 策略列表  / Strategies
 *      nav.sentiment 舆情分析   / Sentiment
 *      nav.recommend 每日推荐   / Daily Picks
 *      nav.compare   策略对比   / Compare
 *      nav.factor    因子分析   / Factor Analysis
 * 3) 持久化 store 只存语言标识等原始状态，**绝不**存 t() 的结果（换语言即失效）。
 */

/** 模块消息类型：宽松 Record，允许任意嵌套对象（遍历时按 dot-path 下钻） */
export type Messages = Record<string, unknown>

/** 支持的语言；'zh-CN' 为默认与回退语言 */
export type Locale = 'zh-CN' | 'en-US'

/** 当前语言（默认 zh-CN）——读取 `.value` 即参与响应式依赖收集 */
export const locale = ref<Locale>('zh-CN')

/** 全量消息树：`messages[locale][namespace][...][key]` */
const messages: Record<Locale, Messages> = {
  'zh-CN': {
    common: commonZh,
    layout: layoutZh,
    home: homeZh,
    tour: tourZh,
    backtest: backtestZh,
    compare: compareZh,
    factor: factorZh,
    sentiment: sentimentZh,
    recommend: recommendZh,
    strategies: strategiesZh,
    chat: chatZh,
    palette: paletteZh,
  },
  'en-US': {
    common: commonEn,
    layout: layoutEn,
    home: homeEn,
    tour: tourEn,
    backtest: backtestEn,
    compare: compareEn,
    factor: factorEn,
    sentiment: sentimentEn,
    recommend: recommendEn,
    strategies: strategiesEn,
    chat: chatEn,
    palette: paletteEn,
  },
}

/** dot-path 查表：逐层下钻，仅 string 叶子视为命中（对象/数组/缺失都返回 undefined） */
function lookup(tree: Messages | undefined, key: string): string | undefined {
  let cur: unknown = tree
  for (const seg of key.split('.')) {
    if (cur === null || typeof cur !== 'object') return undefined
    cur = (cur as Record<string, unknown>)[seg]
  }
  return typeof cur === 'string' ? cur : undefined
}

/** `{name}` 占位符插值：params 中缺失的占位符原样保留（便于定位漏传参） */
function interpolate(template: string, params: Record<string, string | number>): string {
  return template.replace(/\{(\w+)\}/g, (raw: string, name: string) =>
    name in params ? String(params[name]) : raw,
  )
}

/**
 * 取翻译文案：当前语言 → zh-CN 回退 → 原始键名（保证调用方永远拿到字符串）。
 * dev 下缺键打 warn（生产不打，避免噪声）。
 */
export function t(key: string, params?: Record<string, string | number>): string {
  const raw = lookup(messages[locale.value], key) ?? lookup(messages['zh-CN'], key)
  if (raw === undefined) {
    if (import.meta.env.DEV) console.warn(`[i18n] 缺少翻译键: ${key}`)
    return key
  }
  return params ? interpolate(raw, params) : raw
}

/**
 * 切换语言：更新响应式 locale，并同步 <html lang>（辅助功能/浏览器翻译依赖它）。
 * 同时写入 emoqunt_lang cookie——后端（校验错误、推荐理由、图表标签等发射点）按
 * cookie 解析请求语言，SPA 切换后无需刷新即可让接口也返回对应语言。
 */
export function setLocale(l: Locale): void {
  locale.value = l
  document.documentElement.setAttribute('lang', l)
  document.cookie = `emoqunt_lang=${l}; path=/; max-age=31536000; samesite=lax`
}
