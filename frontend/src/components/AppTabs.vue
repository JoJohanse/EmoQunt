<script setup lang="ts">
import { watch } from 'vue'
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useTabsStore } from '@/stores/tabs'

const route = useRoute()
const router = useRouter()
const tabsStore = useTabsStore()

// 初始化与路由变化时记录
watch(
  () => route.path,
  () => tabsStore.addTab(route as any),
  { immediate: true },
)

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
          v-for="t in tabsStore.visited"
          :key="t.path"
          :type="t.path === route.path ? '' : 'info'"
          :effect="t.path === route.path ? 'dark' : 'plain'"
          :closable="t.path !== '/'"
          class="app-tab"
          @click="onClick(t.path)"
          @close="onClose(t.path)"
        >
          {{ t.title }}
        </el-tag>
      </div>
    </el-scrollbar>
    <div class="tabs-actions">
      <el-button text size="small" :disabled="tabsStore.visited.length <= 1" @click="onCloseOthers(route.path)">
        关闭其他
      </el-button>
      <el-button text size="small" :disabled="tabsStore.visited.length <= 1" @click="onCloseAll()">
        关闭全部
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
