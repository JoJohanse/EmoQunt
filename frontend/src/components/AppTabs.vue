<script setup lang="ts">
import { watch } from 'vue'
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useTabsStore } from '@/stores/tabs'
import type { TabItem } from '@/stores/tabs'
import { t } from '@/locales'

const route = useRoute()
const router = useRouter()
const tabsStore = useTabsStore()

// 初始化与路由变化时记录
watch(
  () => route.path,
  () => tabsStore.addTab(route as any),
  { immediate: true },
)

/**
 * 标签标题：优先用持久化的 titleKey（旧数据/未知路由为空串时按 path 反查路由 meta），
 * 最终用 t() 现算——这里读的是响应式 locale，切换语言即重渲染。
 * 键缺失（t() 回退为原始键名）或路由不存在时回退显示 path。
 */
function titleOf(tab: TabItem): string {
  const key = tab.titleKey || (router.resolve(tab.path).meta.titleKey as string | undefined)
  if (!key) return tab.path
  const label = t(key)
  return label === key ? tab.path : label
}

function onClick(path: string) {
  if (path !== route.path) router.push(path)
}
function onClose(path: string) {
  const wasActive = path === route.path
  tabsStore.removeTab(path)
  if (wasActive) {
    const fallback = tabsStore.visited[tabsStore.visited.length - 1]
    if (fallback) router.push(fallback.path)
  }
}
function onCloseAll() {
  tabsStore.closeAll()
  if (route.path !== '/') router.push('/')
}
function onCloseOthers(path: string) {
  tabsStore.closeOthers(path)
  if (route.path !== path) router.push(path)
}
</script>

<template>
  <div v-if="tabsStore.visited.length" class="app-tabs">
    <el-scrollbar>
      <div class="tabs-inner">
        <el-tag
          v-for="tab in tabsStore.visited"
          :key="tab.path"
          :type="tab.path === route.path ? '' : 'info'"
          :effect="tab.path === route.path ? 'dark' : 'plain'"
          :closable="tab.path !== '/'"
          class="app-tab"
          @click="onClick(tab.path)"
          @close="onClose(tab.path)"
        >
          {{ titleOf(tab) }}
        </el-tag>
      </div>
    </el-scrollbar>
    <div class="tabs-actions">
      <el-button text size="small" :disabled="tabsStore.visited.length <= 1" @click="onCloseOthers(route.path)">
        {{ t('layout.tabs.closeOthers') }}
      </el-button>
      <el-button text size="small" :disabled="tabsStore.visited.length <= 1" @click="onCloseAll()">
        {{ t('layout.tabs.closeAll') }}
      </el-button>
    </div>
  </div>
</template>

<style scoped>
.app-tabs {
  display: flex;
  align-items: center;
  gap: 8px;
  background: var(--surface);
  border-bottom: 1px solid var(--border);
  padding: 6px 12px;
  min-height: 40px;
}
.tabs-inner {
  display: flex;
  gap: 6px;
  align-items: center;
  flex-wrap: nowrap;
}
.app-tab {
  cursor: pointer;
  user-select: none;
}
.tabs-actions {
  flex-shrink: 0;
  display: flex;
  gap: 4px;
  margin-left: auto;
}
</style>
