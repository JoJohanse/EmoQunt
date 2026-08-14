<script setup lang="ts">
import { useRoute } from 'vue-router'
import { computed } from 'vue'
import { useChatStore } from '@/stores/chat'
import { useUiStore } from '@/stores/ui'
import ChatPanel from '@/components/ChatPanel.vue'

const route = useRoute()
const activeIndex = computed(() => route.path)
const pageTitle = computed(() => (route.meta.title as string) ?? '')
const chatStore = useChatStore()
const uiStore = useUiStore()

const isDark = computed(() => uiStore.theme === 'dark')
</script>

<template>
  <el-container class="app-layout">
    <!-- 左侧导航：品牌 + 分组菜单（可折叠，状态持久化） -->
    <el-aside :width="uiStore.sidebarCollapsed ? '64px' : '220px'" class="app-aside">
      <router-link to="/" class="brand" :title="uiStore.sidebarCollapsed ? 'EmoQunt 量化系统' : ''">
        <el-icon :size="26"><TrendCharts /></el-icon>
        <span v-show="!uiStore.sidebarCollapsed" class="brand-text">EmoQunt</span>
      </router-link>
      <el-scrollbar class="menu-scrollbar">
        <el-menu
          :default-active="activeIndex"
          :collapse="uiStore.sidebarCollapsed"
          :collapse-transition="false"
          router
          class="side-menu"
          :style="{
            '--el-menu-bg-color': 'transparent',
            '--el-menu-text-color': 'rgba(255, 255, 255, 0.82)',
            '--el-menu-hover-bg-color': 'rgba(255, 255, 255, 0.14)',
            '--el-menu-active-color': '#ffffff',
          }"
        >
          <el-menu-item index="/">
            <el-icon><HomeFilled /></el-icon>
            <template #title>首页</template>
          </el-menu-item>

          <el-sub-menu index="research">
            <template #title>
              <el-icon><TrendCharts /></el-icon>
              <span>回测研究</span>
            </template>
            <el-menu-item index="/backtest">
              <el-icon><Histogram /></el-icon>
              <template #title>策略回测</template>
            </el-menu-item>
            <el-menu-item index="/strategy-compare">
              <el-icon><DataLine /></el-icon>
              <template #title>策略对比</template>
            </el-menu-item>
            <el-menu-item index="/factor-analysis">
              <el-icon><DataAnalysis /></el-icon>
              <template #title>因子分析</template>
            </el-menu-item>
          </el-sub-menu>

          <el-sub-menu index="insight">
            <template #title>
              <el-icon><View /></el-icon>
              <span>数据洞察</span>
            </template>
            <el-menu-item index="/sentiment">
              <el-icon><ChatDotRound /></el-icon>
              <template #title>舆情分析</template>
            </el-menu-item>
            <el-menu-item index="/daily-recommend">
              <el-icon><Star /></el-icon>
              <template #title>每日推荐</template>
            </el-menu-item>
          </el-sub-menu>

          <el-sub-menu index="manage">
            <template #title>
              <el-icon><Files /></el-icon>
              <span>策略管理</span>
            </template>
            <el-menu-item index="/strategies">
              <el-icon><List /></el-icon>
              <template #title>策略列表</template>
            </el-menu-item>
          </el-sub-menu>
        </el-menu>
      </el-scrollbar>
      <div v-show="!uiStore.sidebarCollapsed" class="aside-tip">v1.0 · A股 / 美股</div>
    </el-aside>

    <!-- 右侧主区 -->
    <el-container class="main-container">
      <el-header class="app-header">
        <div class="header-left">
          <el-button text circle :title="uiStore.sidebarCollapsed ? '展开菜单' : '收起菜单'" @click="uiStore.toggleSidebar()">
            <el-icon :size="18"><Expand v-if="uiStore.sidebarCollapsed" /><Fold v-else /></el-icon>
          </el-button>
          <el-breadcrumb separator="/" class="crumbs">
            <el-breadcrumb-item :to="{ path: '/' }">首页</el-breadcrumb-item>
            <el-breadcrumb-item v-if="route.path !== '/' && pageTitle">{{ pageTitle }}</el-breadcrumb-item>
          </el-breadcrumb>
        </div>
        <div class="header-right">
          <el-button
            text
            circle
            :title="isDark ? '切换到亮色模式' : '切换到暗色模式'"
            @click="uiStore.toggleTheme()"
          >
            <el-icon :size="18"><Sunny v-if="isDark" /><Moon v-else /></el-icon>
          </el-button>
          <!-- AI 助手触发按钮 -->
          <el-button class="ai-btn" type="primary" round size="small" @click="chatStore.toggleDrawer()">
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
    </el-container>

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
.app-aside {
  background: linear-gradient(180deg, #5b6ee0 0%, #764ba2 100%);
  display: flex;
  flex-direction: column;
  transition: width 0.2s ease;
  overflow: hidden;
}
.brand {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  color: #fff;
  text-decoration: none;
  font-weight: 700;
  font-size: 1.15rem;
  height: 60px;
  flex-shrink: 0;
  border-bottom: 1px solid rgba(255, 255, 255, 0.15);
  white-space: nowrap;
}
.menu-scrollbar {
  flex: 1;
}
.side-menu {
  border-right: none !important;
  padding: 8px;
}
.side-menu :deep(.el-menu-item.is-active) {
  background: rgba(255, 255, 255, 0.18) !important;
  border-radius: 8px;
  font-weight: 600;
}
.side-menu :deep(.el-menu-item),
.side-menu :deep(.el-sub-menu__title) {
  border-radius: 8px;
  height: 46px;
  line-height: 46px;
}
.aside-tip {
  color: rgba(255, 255, 255, 0.45);
  font-size: 0.75rem;
  text-align: center;
  padding: 10px 0 14px;
  flex-shrink: 0;
  white-space: nowrap;
}
.main-container {
  min-width: 0;
}
.app-header {
  background: var(--surface);
  border-bottom: 1px solid var(--border);
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 60px;
  padding: 0 20px;
  position: sticky;
  top: 0;
  z-index: 10;
}
.header-left,
.header-right {
  display: flex;
  align-items: center;
  gap: 8px;
}
.crumbs {
  margin-left: 4px;
  font-size: 0.95rem;
}
.ai-btn {
  margin-left: 8px;
  font-weight: 600;
}
/* 抽屉内 ChatPanel 占满高度 */
:deep(.el-drawer__body) {
  padding: 0;
  display: flex;
  flex-direction: column;
}
.app-main {
  max-width: 1440px;
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
