import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
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
