<script setup lang="ts">
import { useRoute } from 'vue-router'
import { computed } from 'vue'
import { useChatStore } from '@/stores/chat'
import ChatPanel from '@/components/ChatPanel.vue'

const route = useRoute()
const activeIndex = computed(() => route.path)
const chatStore = useChatStore()
</script>

<template>
  <el-container class="app-layout">
    <el-header class="app-header">
      <div class="header-inner">
        <router-link to="/" class="brand">
          <el-icon :size="24"><TrendCharts /></el-icon>
          <span class="brand-text">EmoQunt 量化系统</span>
        </router-link>
        <el-menu
          :default-active="activeIndex"
          mode="horizontal"
          :ellipsis="false"
          router
          class="nav-menu"
        >
          <el-menu-item index="/">
            <el-icon><HomeFilled /></el-icon>首页
          </el-menu-item>
          <el-menu-item index="/backtest">
            <el-icon><TrendCharts /></el-icon>策略回测
          </el-menu-item>
          <el-menu-item index="/strategies">
            <el-icon><List /></el-icon>策略列表
          </el-menu-item>
          <el-menu-item index="/sentiment">
            <el-icon><ChatDotRound /></el-icon>舆情分析
          </el-menu-item>
          <el-menu-item index="/daily-recommend">
            <el-icon><Star /></el-icon>每日推荐
          </el-menu-item>
          <el-menu-item index="/strategy-compare">
            <el-icon><DataLine /></el-icon>策略对比
          </el-menu-item>
          <el-menu-item index="/factor-analysis">
            <el-icon><DataAnalysis /></el-icon>因子分析
          </el-menu-item>
        </el-menu>
        <!-- AI 助手触发按钮 -->
        <el-button
          class="ai-btn"
          type="primary"
          round
          size="small"
          @click="chatStore.toggleDrawer()"
        >
          <el-icon><ChatDotRound /></el-icon> AI 助手
        </el-button>
      </div>
    </el-header>
    <el-main class="app-main">
      <slot />
    </el-main>
    <el-footer class="app-footer">
      <span><el-icon><TrendCharts /></el-icon> EmoQunt 量化系统 · 让量化投资更简单</span>
    </el-footer>

    <!-- 全局 AI 助手抽屉（所有页面可用） -->
    <el-drawer
      v-model="chatStore.drawerOpen"
      title="AI 投资助手"
      direction="rtl"
      size="420px"
      :with-header="true"
    >
      <ChatPanel />
    </el-drawer>
  </el-container>
</template>

<style scoped>
.app-layout {
  min-height: 100vh;
}
.app-header {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  padding: 0;
  height: 60px;
}
.header-inner {
  max-width: 1280px;
  margin: 0 auto;
  display: flex;
  align-items: center;
  height: 100%;
  padding: 0 20px;
}
.brand {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #fff;
  text-decoration: none;
  font-weight: 700;
  font-size: 1.15rem;
  margin-right: 32px;
  white-space: nowrap;
}
.brand-text {
  color: #fff;
}
.nav-menu {
  background: transparent !important;
  border-bottom: none !important;
  flex: 1;
}
.nav-menu :deep(.el-menu-item) {
  color: rgba(255, 255, 255, 0.85);
  border-bottom-color: transparent;
}
.nav-menu :deep(.el-menu-item.is-active),
.nav-menu :deep(.el-menu-item:hover) {
  color: #fff;
  background: rgba(255, 255, 255, 0.12) !important;
  border-bottom: 2px solid #fff;
}
.ai-btn {
  margin-left: 12px;
  flex-shrink: 0;
  font-weight: 600;
}
/* 抽屉内 ChatPanel 占满高度 */
:deep(.el-drawer__body) {
  padding: 0;
  display: flex;
  flex-direction: column;
}
.app-main {
  max-width: 1280px;
  margin: 0 auto;
  width: 100%;
  padding: 24px 20px;
  box-sizing: border-box;
}
.app-footer {
  background: #1f2937;
  color: rgba(255, 255, 255, 0.7);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.9rem;
  height: 56px;
}
.app-footer .el-icon {
  vertical-align: middle;
  margin-right: 4px;
}
</style>
