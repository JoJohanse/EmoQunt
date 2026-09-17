import { watch } from 'vue'
import { createRouter, createWebHistory } from 'vue-router'
import { locale, t } from '@/locales'

// SPA 由 FastAPI 托管在 /spa/* 前缀下（dev 时 Vite 的 SPA fallback 同样支持 /spa/ 路径），
// 因此 router base 固定为 /spa/；构建产物的静态资源仍走绝对路径 /assets/...，不受影响。
const router = createRouter({
  history: createWebHistory('/spa/'),
  routes: [
    {
      path: '/',
      name: 'home',
      component: () => import('@/views/HomeView.vue'),
      meta: { titleKey: 'layout.nav.home' },
    },
    {
      path: '/backtest',
      name: 'backtest',
      component: () => import('@/views/BacktestView.vue'),
      meta: { titleKey: 'layout.nav.backtest' },
    },
    {
      path: '/strategies',
      name: 'strategies',
      component: () => import('@/views/StrategiesView.vue'),
      meta: { titleKey: 'layout.nav.strategies' },
    },
    {
      path: '/strategy-library',
      name: 'strategy-library',
      component: () => import('@/views/StrategyLibraryView.vue'),
      meta: { titleKey: 'layout.nav.strategyLibrary' },
    },
    {
      path: '/strategy-library/:id',
      name: 'strategy-library-detail',
      component: () => import('@/views/StrategyDetailView.vue'),
      meta: { titleKey: 'layout.nav.strategyLibrary' },
    },
    {
      path: '/sentiment',
      name: 'sentiment',
      component: () => import('@/views/SentimentView.vue'),
      meta: { titleKey: 'layout.nav.sentiment' },
    },
    {
      path: '/daily-recommend',
      name: 'daily-recommend',
      component: () => import('@/views/DailyRecommendView.vue'),
      meta: { titleKey: 'layout.nav.recommend' },
    },
    {
      path: '/strategy-compare',
      name: 'strategy-compare',
      component: () => import('@/views/StrategyCompareView.vue'),
      meta: { titleKey: 'layout.nav.compare' },
    },
    {
      path: '/factor-analysis',
      name: 'factor-analysis',
      component: () => import('@/views/FactorAnalysisView.vue'),
      meta: { titleKey: 'layout.nav.factor' },
    },
  ],
})

/**
 * 文档标题：`<导航文案> · EmoQunt`。
 * 无 titleKey（或键缺失，t 会回退为原始键名）时只剩品牌名，避免标题里出现裸键。
 */
function composeTitle(titleKey: unknown): string {
  const key = typeof titleKey === 'string' ? titleKey : ''
  const label = key ? t(key) : ''
  // t() 对缺失键回退为原始键名，此时视为无标题
  const title = label === key ? '' : label
  return `${title} · EmoQunt`.trim()
}

router.afterEach((to) => {
  document.title = composeTitle(to.meta.titleKey)
})

// 页内切换语言不会触发导航，需就地重算当前页标题
watch(locale, () => {
  document.title = composeTitle(router.currentRoute.value.meta.titleKey)
})

export default router
