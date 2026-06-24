<script setup lang="ts">
import { useRouter } from 'vue-router'
const router = useRouter()

const features = [
  {
    icon: 'TrendCharts',
    title: '策略回测',
    desc: '选择策略运行回测，查看含 Alpha/Beta、最大回撤的详细绩效报告',
    route: '/backtest',
    color: 'linear-gradient(135deg, #667eea, #764ba2)',
  },
  {
    icon: 'List',
    title: '策略管理',
    desc: '创建、编辑、查看所有策略及其参数配置',
    route: '/strategies',
    color: 'linear-gradient(135deg, #28a745, #48c764)',
  },
  {
    icon: 'ChatDotRound',
    title: '舆情分析',
    desc: '基于实时热点舆论数据生成板块情绪与个股交易信号',
    route: '/sentiment',
    color: 'linear-gradient(135deg, #f59e0b, #fbbf24)',
  },
  {
    icon: 'Star',
    title: '每日推荐',
    desc: '融合情绪与多因子模型，智能推荐潜力股票',
    route: '/daily-recommend',
    color: 'linear-gradient(135deg, #0ea5e9, #38bdf8)',
  },
]

const highlights = [
  { icon: 'MagicStick', title: '情绪因子策略', desc: '将行业情绪快照接入回测信号过滤' },
  { icon: 'DataAnalysis', title: '多因子模型', desc: '均线、情绪、基本面多维度打分' },
  { icon: 'Wallet', title: '真实交易成本', desc: 'A股佣金/印花税/过户费与美股成本建模' },
  { icon: 'Histogram', title: '动态可视化', desc: 'ECharts 交互式图表，支持缩放与数据钻取' },
]
</script>

<template>
  <div>
    <div class="hero-gradient">
      <h1><el-icon :size="32"><TrendCharts /></el-icon> 欢迎使用 EmoQunt 量化系统</h1>
      <p>结合情绪因子的智能量化策略回测平台 · Vue3 SPA · 让数据驱动你的投资决策</p>
    </div>

    <el-row :gutter="20">
      <el-col v-for="f in features" :key="f.route" :xs="24" :sm="12" :lg="6">
        <el-card class="feature-card" shadow="hover" @click="router.push(f.route)">
          <div class="feature-icon" :style="{ background: f.color }">
            <el-icon :size="26"><component :is="f.icon" /></el-icon>
          </div>
          <h3>{{ f.title }}</h3>
          <p class="feature-desc">{{ f.desc }}</p>
          <el-button type="primary" round>进入</el-button>
        </el-card>
      </el-col>
    </el-row>

    <el-card class="highlight-card" shadow="never">
      <template #header>
        <span class="section-title" style="margin: 0; border: none; padding: 0">
          <el-icon><Setting /></el-icon> 系统特性
        </span>
      </template>
      <el-row :gutter="16">
        <el-col v-for="h in highlights" :key="h.title" :xs="12" :md="6">
          <div class="highlight-item">
            <div class="hl-icon"><el-icon><component :is="h.icon" /></el-icon></div>
            <div>
              <div class="hl-title">{{ h.title }}</div>
              <small class="hl-desc">{{ h.desc }}</small>
            </div>
          </div>
        </el-col>
      </el-row>
    </el-card>
  </div>
</template>

<style scoped>
.hero-gradient {
  background: var(--brand-grad);
  color: #fff;
  border-radius: var(--radius);
  padding: 2.5rem 2rem;
  margin-bottom: 1.5rem;
  text-align: center;
}
.hero-gradient h1 {
  margin: 0 0 0.5rem;
  font-size: 1.9rem;
  font-weight: 800;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
}
.hero-gradient p {
  margin: 0;
  opacity: 0.92;
}
.feature-card {
  text-align: center;
  cursor: pointer;
  border-radius: var(--radius);
  margin-bottom: 16px;
  transition: transform 0.2s;
}
.feature-card:hover {
  transform: translateY(-4px);
}
.feature-icon {
  width: 64px;
  height: 64px;
  border-radius: 50%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  margin-bottom: 12px;
}
.feature-card h3 {
  margin: 0 0 8px;
}
.feature-desc {
  color: var(--text-muted);
  font-size: 0.9rem;
  min-height: 40px;
  margin: 0 0 12px;
}
.highlight-card {
  margin-top: 8px;
  border-radius: var(--radius);
}
.highlight-item {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 12px;
}
.hl-icon {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: var(--brand-grad);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  font-size: 1.1rem;
}
.hl-title {
  font-weight: 600;
}
.hl-desc {
  color: var(--text-muted);
}
</style>
