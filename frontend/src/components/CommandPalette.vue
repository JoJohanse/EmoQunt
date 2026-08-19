<script setup lang="ts">
import { ref, computed, watch, nextTick, onMounted, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import { useWatchlistStore } from '@/stores/watchlist'
import { useBacktestHistoryStore } from '@/stores/backtestHistory'

interface CmdItem {
  id: string
  label: string
  group: string
  path?: string
  action?: () => void
  keywords?: string
}

const router = useRouter()
const watchlistStore = useWatchlistStore()
const historyStore = useBacktestHistoryStore()

const open = ref(false)
const query = ref('')
const activeIndex = ref(0)
const inputRef = ref<HTMLInputElement | null>(null)

// --- 命令数据源 ---
const navItems: CmdItem[] = [
  { id: 'nav-home', label: '首页', group: '导航', path: '/', keywords: 'home dashboard' },
  { id: 'nav-backtest', label: '策略回测', group: '导航', path: '/backtest', keywords: 'backtest' },
  { id: 'nav-compare', label: '策略对比', group: '导航', path: '/strategy-compare', keywords: 'compare' },
  { id: 'nav-factor', label: '因子分析', group: '导航', path: '/factor-analysis', keywords: 'factor' },
  { id: 'nav-sentiment', label: '舆情分析', group: '导航', path: '/sentiment', keywords: 'sentiment news' },
  { id: 'nav-recommend', label: '每日推荐', group: '导航', path: '/daily-recommend', keywords: 'recommend' },
  { id: 'nav-strategies', label: '策略列表', group: '导航', path: '/strategies', keywords: 'strategies' },
]

const allItems = computed<CmdItem[]>(() => {
  const wl: CmdItem[] = watchlistStore.items.map((it) => ({
    id: `wl-${it.code}-${it.market}`,
    label: `${it.name} ${it.code}`,
    group: '自选股',
    keywords: `${it.code} ${it.name} ${it.market}`,
    action: () => {
      watchlistStore.lastKey = `${it.code}|${it.market}`
      router.push('/')
    },
  }))
  const hist: CmdItem[] = historyStore.records.slice(0, 10).map((r) => ({
    id: `hist-${r.id}`,
    label: `${r.strategyName} · ${r.stockCode}`,
    group: '最近回测',
    keywords: `${r.strategyName} ${r.stockCode}`,
    action: () => router.push({ path: '/backtest', query: { historyId: r.id } }),
  }))
  return [...navItems, ...wl, ...hist]
})

const filtered = computed(() => {
  const q = query.value.trim().toLowerCase()
  if (!q) return allItems.value
  return allItems.value.filter((it) => {
    const hay = `${it.label} ${it.keywords ?? ''} ${it.path ?? ''}`.toLowerCase()
    return hay.includes(q)
  })
})

const grouped = computed(() => {
  const m = new Map<string, CmdItem[]>()
  for (const it of filtered.value) {
    if (!m.has(it.group)) m.set(it.group, [])
    m.get(it.group)!.push(it)
  }
  return m
})

// 扁平序列用于键盘导航
const flat = computed(() => filtered.value)

function select(it: CmdItem) {
  open.value = false
  if (it.action) it.action()
  else if (it.path) router.push(it.path)
}

function onKeydown(e: KeyboardEvent) {
  if (!open.value) return
  if (e.key === 'ArrowDown') {
    e.preventDefault()
    activeIndex.value = Math.min(activeIndex.value + 1, flat.value.length - 1)
  } else if (e.key === 'ArrowUp') {
    e.preventDefault()
    activeIndex.value = Math.max(activeIndex.value - 1, 0)
  } else if (e.key === 'Enter') {
    e.preventDefault()
    const it = flat.value[activeIndex.value]
    if (it) select(it)
  } else if (e.key === 'Escape') {
    open.value = false
  }
}

watch(query, () => {
  activeIndex.value = 0
})
watch(open, async (v) => {
  if (v) {
    query.value = ''
    activeIndex.value = 0
    await nextTick()
    inputRef.value?.focus()
  }
})

// 全局快捷键：Ctrl+K / Cmd+K 唤起；"/" 在非输入框时唤起
function onGlobalKeydown(e: KeyboardEvent) {
  const isCtrlK = (e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k'
  const isSlash =
    e.key === '/' &&
    !e.ctrlKey && !e.metaKey && !e.altKey &&
    !(e.target instanceof HTMLInputElement) &&
    !(e.target instanceof HTMLTextAreaElement)
  if (isCtrlK || isSlash) {
    e.preventDefault()
    open.value = true
  }
}

onMounted(() => window.addEventListener('keydown', onGlobalKeydown))
onBeforeUnmount(() => window.removeEventListener('keydown', onGlobalKeydown))

defineExpose({ open: () => (open.value = true), close: () => (open.value = false) })
</script>

<template>
  <el-dialog v-model="open" width="560px" :show-close="false" class="cmd-dialog" @keydown="onKeydown">
    <div class="cmd-search">
      <el-icon><Search /></el-icon>
      <input
        ref="inputRef"
        v-model="query"
        class="cmd-input"
        placeholder="搜索命令、页面、自选股、回测…（↑↓ 选择，回车确认）"
      />
      <span class="cmd-hint">ESC 关闭</span>
    </div>
    <el-scrollbar max-height="360px" class="cmd-list">
      <template v-for="[group, items] in grouped" :key="group">
        <div class="cmd-group">{{ group }}</div>
        <div
          v-for="it in items"
          :key="it.id"
          class="cmd-item"
          :class="{ active: flat.indexOf(it) === activeIndex }"
          @click="select(it)"
          @mouseenter="activeIndex = flat.indexOf(it)"
        >
          <span class="cmd-label">{{ it.label }}</span>
          <span v-if="it.path" class="cmd-path">{{ it.path }}</span>
        </div>
      </template>
      <el-empty v-if="!filtered.length" description="无匹配结果" :image-size="56" />
    </el-scrollbar>
  </el-dialog>
</template>

<style scoped>
.cmd-search {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 10px;
  border: 1px solid var(--border);
  border-radius: 8px;
  margin-bottom: 10px;
}
.cmd-input {
  flex: 1;
  border: none;
  outline: none;
  font-size: 14px;
  background: transparent;
  color: var(--text);
}
.cmd-hint {
  font-size: 12px;
  color: var(--text-muted);
  flex-shrink: 0;
}
.cmd-group {
  font-size: 12px;
  color: var(--text-muted);
  padding: 8px 10px 4px;
  font-weight: 600;
}
.cmd-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 10px;
  border-radius: 6px;
  cursor: pointer;
}
.cmd-item:hover,
.cmd-item.active {
  background: rgba(102, 126, 234, 0.12);
}
.cmd-label {
  font-weight: 500;
}
.cmd-path {
  font-size: 12px;
  color: var(--text-muted);
  font-family: monospace;
}
</style>
