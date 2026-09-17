<script setup lang="ts">
import { useRoute } from 'vue-router'
import { computed, ref } from 'vue'
import { useChatStore } from '@/stores/chat'
import { useUiStore } from '@/stores/ui'
import { useFavoritesStore } from '@/stores/favorites'
import ChatPanel from '@/components/ChatPanel.vue'
import AppTabs from '@/components/AppTabs.vue'
import CommandPalette from '@/components/CommandPalette.vue'
import { t } from '@/locales'

const route = useRoute()
const activeIndex = computed(() => route.path)
// 面包屑标题取路由 meta.titleKey 现算（t() 读取 locale，切换语言即重算）
const pageTitle = computed(() => {
  const key = route.meta.titleKey as string | undefined
  return key ? t(key) : ''
})
const chatStore = useChatStore()
const uiStore = useUiStore()
const favoritesStore = useFavoritesStore()

const isDark = computed(() => uiStore.theme === 'dark')
const cmdRef = ref<InstanceType<typeof CommandPalette> | null>(null)
function openCommand() {
  ;(cmdRef.value as unknown as { open: () => void })?.open?.()
}

// 收藏菜单标题：路由 path → 导航文案（与 router meta.titleKey 同一套 nav.* 契约）
const favTitleMap = computed<Record<string, string>>(() => ({
  '/': t('layout.nav.home'),
  '/backtest': t('layout.nav.backtest'),
  '/strategy-compare': t('layout.nav.compare'),
  '/factor-analysis': t('layout.nav.factor'),
  '/sentiment': t('layout.nav.sentiment'),
  '/daily-recommend': t('layout.nav.recommend'),
  '/strategies': t('layout.nav.strategies'),
  '/strategy-library': t('layout.nav.strategyLibrary'),
  '/runs': t('layout.nav.runHistory'),
  '/factor-library': t('layout.nav.factorLibrary'),
}))

/** 语言切换按钮标签显示「目标语言」：中文界面显示 EN，英文界面显示 中文 */
const langLabel = computed(() => (uiStore.lang === 'en-US' ? '中文' : 'EN'))
</script>

<template>
  <el-container class="app-layout">
    <!-- 左侧导航：品牌 + 分组菜单（可折叠，状态持久化） -->
    <el-aside :width="uiStore.sidebarCollapsed ? '64px' : '220px'" class="app-aside">
      <router-link to="/" class="brand" :title="uiStore.sidebarCollapsed ? t('layout.brand') : ''">
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
            <template #title>
              <span class="menu-label">{{ t('layout.nav.home') }}</span>
              <el-button text size="small" class="fav-btn" @click.stop="favoritesStore.toggle('/')">
                <el-icon><StarFilled v-if="favoritesStore.isFavorite('/')" /><Star v-else /></el-icon>
              </el-button>
            </template>
          </el-menu-item>

          <!-- 收藏分组：仅当有收藏时显示 -->
          <el-sub-menu v-if="favoritesStore.paths.length" index="favorites">
            <template #title>
              <el-icon><StarFilled /></el-icon>
              <span>{{ t('layout.favorites') }}</span>
            </template>
            <el-menu-item v-for="p in favoritesStore.paths" :key="p" :index="p">
              <el-icon><Star /></el-icon>
              <template #title>{{ favTitleMap[p] ?? p }}</template>
            </el-menu-item>
          </el-sub-menu>

          <el-sub-menu index="research">
            <template #title>
              <el-icon><TrendCharts /></el-icon>
              <span>{{ t('layout.group.research') }}</span>
            </template>
            <el-menu-item index="/backtest">
              <el-icon><Histogram /></el-icon>
              <template #title>
                <span class="menu-label">{{ t('layout.nav.backtest') }}</span>
                <el-button text size="small" class="fav-btn" @click.stop="favoritesStore.toggle('/backtest')">
                  <el-icon><StarFilled v-if="favoritesStore.isFavorite('/backtest')" /><Star v-else /></el-icon>
                </el-button>
              </template>
            </el-menu-item>
            <el-menu-item index="/strategy-compare">
              <el-icon><DataLine /></el-icon>
              <template #title>
                <span class="menu-label">{{ t('layout.nav.compare') }}</span>
                <el-button text size="small" class="fav-btn" @click.stop="favoritesStore.toggle('/strategy-compare')">
                  <el-icon><StarFilled v-if="favoritesStore.isFavorite('/strategy-compare')" /><Star v-else /></el-icon>
                </el-button>
              </template>
            </el-menu-item>
            <el-menu-item index="/factor-analysis">
              <el-icon><DataAnalysis /></el-icon>
              <template #title>
                <span class="menu-label">{{ t('layout.nav.factor') }}</span>
                <el-button text size="small" class="fav-btn" @click.stop="favoritesStore.toggle('/factor-analysis')">
                  <el-icon><StarFilled v-if="favoritesStore.isFavorite('/factor-analysis')" /><Star v-else /></el-icon>
                </el-button>
              </template>
            </el-menu-item>
          </el-sub-menu>

          <el-sub-menu index="insight">
            <template #title>
              <el-icon><View /></el-icon>
              <span>{{ t('layout.group.insight') }}</span>
            </template>
            <el-menu-item index="/sentiment">
              <el-icon><ChatDotRound /></el-icon>
              <template #title>
                <span class="menu-label">{{ t('layout.nav.sentiment') }}</span>
                <el-button text size="small" class="fav-btn" @click.stop="favoritesStore.toggle('/sentiment')">
                  <el-icon><StarFilled v-if="favoritesStore.isFavorite('/sentiment')" /><Star v-else /></el-icon>
                </el-button>
              </template>
            </el-menu-item>
            <el-menu-item index="/daily-recommend">
              <el-icon><Star /></el-icon>
              <template #title>
                <span class="menu-label">{{ t('layout.nav.recommend') }}</span>
                <el-button text size="small" class="fav-btn" @click.stop="favoritesStore.toggle('/daily-recommend')">
                  <el-icon><StarFilled v-if="favoritesStore.isFavorite('/daily-recommend')" /><Star v-else /></el-icon>
                </el-button>
              </template>
            </el-menu-item>
          </el-sub-menu>

          <el-sub-menu index="manage">
            <template #title>
              <el-icon><Files /></el-icon>
              <span>{{ t('layout.group.manage') }}</span>
            </template>
            <el-menu-item index="/strategies">
              <el-icon><List /></el-icon>
              <template #title>
                <span class="menu-label">{{ t('layout.nav.strategies') }}</span>
                <el-button text size="small" class="fav-btn" @click.stop="favoritesStore.toggle('/strategies')">
                  <el-icon><StarFilled v-if="favoritesStore.isFavorite('/strategies')" /><Star v-else /></el-icon>
                </el-button>
              </template>
            </el-menu-item>
            <el-menu-item index="/strategy-library">
              <el-icon><Coin /></el-icon>
              <template #title>
                <span class="menu-label">{{ t('layout.nav.strategyLibrary') }}</span>
                <el-button text size="small" class="fav-btn" @click.stop="favoritesStore.toggle('/strategy-library')">
                  <el-icon><StarFilled v-if="favoritesStore.isFavorite('/strategy-library')" /><Star v-else /></el-icon>
                </el-button>
              </template>
            </el-menu-item>
            <el-menu-item index="/runs">
              <el-icon><Clock /></el-icon>
              <template #title>
                <span class="menu-label">{{ t('layout.nav.runHistory') }}</span>
                <el-button text size="small" class="fav-btn" @click.stop="favoritesStore.toggle('/runs')">
                  <el-icon><StarFilled v-if="favoritesStore.isFavorite('/runs')" /><Star v-else /></el-icon>
                </el-button>
              </template>
            </el-menu-item>
            <el-menu-item index="/factor-library">
              <el-icon><DataAnalysis /></el-icon>
              <template #title>
                <span class="menu-label">{{ t('layout.nav.factorLibrary') }}</span>
                <el-button text size="small" class="fav-btn" @click.stop="favoritesStore.toggle('/factor-library')">
                  <el-icon><StarFilled v-if="favoritesStore.isFavorite('/factor-library')" /><Star v-else /></el-icon>
                </el-button>
              </template>
            </el-menu-item>
          </el-sub-menu>
        </el-menu>
      </el-scrollbar>
      <div v-show="!uiStore.sidebarCollapsed" class="aside-tip">{{ t('layout.asideTip') }}</div>
    </el-aside>

    <!-- 右侧主区 -->
    <el-container class="main-container">
      <el-header class="app-header">
        <div class="header-left">
          <el-button
            text
            circle
            :title="uiStore.sidebarCollapsed ? t('layout.expandMenu') : t('layout.collapseMenu')"
            @click="uiStore.toggleSidebar()"
          >
            <el-icon :size="18"><Expand v-if="uiStore.sidebarCollapsed" /><Fold v-else /></el-icon>
          </el-button>
          <el-breadcrumb separator="/" class="crumbs">
            <el-breadcrumb-item :to="{ path: '/' }">{{ t('layout.nav.home') }}</el-breadcrumb-item>
            <el-breadcrumb-item v-if="route.path !== '/' && pageTitle">{{ pageTitle }}</el-breadcrumb-item>
          </el-breadcrumb>
        </div>
        <div class="header-right">
          <el-button text circle :title="t('layout.commandPalette')" @click="openCommand">
            <el-icon :size="18"><Search /></el-icon>
          </el-button>
          <!-- 语言切换（标签显示目标语言，与右侧主题切换同款样式） -->
          <el-tooltip :content="t('layout.upDown.label')" placement="bottom">
            <el-select
              v-model="uiStore.upDownColor"
              size="small"
              class="updown-select"
              :aria-label="t('layout.upDown.label')"
            >
              <el-option value="market" :label="t('layout.upDown.market')" />
              <el-option value="red_up" :label="t('layout.upDown.redUp')" />
              <el-option value="green_up" :label="t('layout.upDown.greenUp')" />
            </el-select>
          </el-tooltip>
          <el-button text circle class="lang-btn" :title="t('layout.switchLang')" @click="uiStore.toggleLang()">
            <span class="lang-label">{{ langLabel }}</span>
          </el-button>
          <el-button
            text
            circle
            :title="isDark ? t('layout.switchLight') : t('layout.switchDark')"
            @click="uiStore.toggleTheme()"
          >
            <el-icon :size="18"><Sunny v-if="isDark" /><Moon v-else /></el-icon>
          </el-button>
          <!-- AI 助手触发按钮 -->
          <el-button class="ai-btn" type="primary" round size="small" @click="chatStore.toggleDrawer()">
            <el-icon><ChatDotRound /></el-icon> {{ t('layout.aiAssistant') }}
          </el-button>
        </div>
      </el-header>
      <AppTabs />
      <el-main class="app-main">
        <slot />
      </el-main>
      <el-footer class="app-footer">
        <span><el-icon><TrendCharts /></el-icon> {{ t('layout.footer') }}</span>
      </el-footer>
    </el-container>

    <!-- 全局命令面板 -->
    <CommandPalette ref="cmdRef" />

    <!-- 全局 AI 助手抽屉（所有页面可用） -->
    <el-drawer
      v-model="chatStore.drawerOpen"
      :title="t('layout.aiDrawerTitle')"
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
.menu-label {
  flex: 1;
  /* 英文菜单项（Factor Analysis）比中文宽，超宽时省略号截断，避免被 aside overflow 硬裁 */
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
/* 分组标题（Strategy Management 等）同理：el-sub-menu__title 是 flex 但自身不截断 */
.side-menu :deep(.el-sub-menu__title > span) {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.fav-btn {
  margin-left: 6px;
  color: rgba(255, 255, 255, 0.7) !important;
  padding: 2px !important;
}
.fav-btn:hover {
  color: #fff !important;
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
/* 语言切换按钮内的文字标签（无图标，故字号略小以对齐相邻图标按钮） */
.lang-label {
  font-size: 12px;
  font-weight: 600;
  line-height: 1;
}
/* is-circle 固定 32px 宽 + 8px 内边距，「中文」二字（约 24px）会溢出圆形热区；
   归零内边距让文字在圆内居中，与相邻图标按钮严格同尺寸 */
.updown-select {
  width: 104px;
  margin-right: 4px;
}
.updown-select :deep(.el-select__wrapper) {
  min-height: 28px;
}
.lang-btn {
  padding: 0;
  justify-content: center;
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
