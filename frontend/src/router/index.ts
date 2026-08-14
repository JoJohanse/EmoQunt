import { createRouter, createWebHistory } from 'vue-router'

// SPA 由 FastAPI 托管在 /spa/* 前缀下（dev 时 Vite 的 SPA fallback 同样支持 /spa/ 路径），
// 因此 router base 固定为 /spa/；构建产物的静态资源仍走绝对路径 /assets/...，不受影响。
const router = createRouter({
  history: createWebHistory('/spa/'),
  routes: [
    {
      path: '/',
      name: 'home',
      component: () => import('@/views/HomeView.vue'),
      meta: { title: '首页' },
    },
    {
      path: '/backtest',
      name: 'backtest',
      component: () => import('@/views/BacktestView.vue'),
      meta: { title: '策略回测' },
    },
    {
      path: '/strategies',
      name: 'strategies',
      component: () => import('@/views/StrategiesView.vue'),
      meta: { title: '策略列表' },
    },
    {
      path: '/sentiment',
      name: 'sentiment',
      component: () => import('@/views/SentimentView.vue'),
      meta: { title: '舆情分析' },
    },
    {
      path: '/daily-recommend',
      name: 'daily-recommend',
      component: () => import('@/views/DailyRecommendView.vue'),
      meta: { title: '每日推荐' },
    },
    {
      path: '/strategy-compare',
      name: 'strategy-compare',
      component: () => import('@/views/StrategyCompareView.vue'),
      meta: { title: '策略对比' },
    },
    {
      path: '/factor-analysis',
      name: 'factor-analysis',
      component: () => import('@/views/FactorAnalysisView.vue'),
      meta: { title: '因子分析' },
    },
  ],
})

router.afterEach((to) => {
  document.title = `${to.meta.title ?? ''} · EmoQunt`.trim()
})

export default router
