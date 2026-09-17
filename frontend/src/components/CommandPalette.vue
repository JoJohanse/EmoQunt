<script setup lang="ts">
import { ref, computed, watch, nextTick, onMounted, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import { useWatchlistStore } from '@/stores/watchlist'
import { useBacktestHistoryStore } from '@/stores/backtestHistory'
import { t } from '@/locales'

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
// 导航项文案复用 layout.nav.*（与 router meta.titleKey 同一契约）；分组名走 palette.*。
// 用 computed 而非模块级常量：t() 读取响应式 locale，语言切换即时重建列表。
const navItems = computed<CmdItem[]>(() => [
  { id: 'nav-home', label: t('layout.nav.home'), group: t('palette.groupNav'), path: '/', keywords: 'home dashboard' },
  { id: 'nav-backtest', label: t('layout.nav.backtest'), group: t('palette.groupNav'), path: '/backtest', keywords: 'backtest' },
  { id: 'nav-compare', label: t('layout.nav.compare'), group: t('palette.groupNav'), path: '/strategy-compare', keywords: 'compare' },
  { id: 'nav-factor', label: t('layout.nav.factor'), group: t('palette.groupNav'), path: '/factor-analysis', keywords: 'factor' },
  { id: 'nav-sentiment', label: t('layout.nav.sentiment'), group: t('palette.groupNav'), path: '/sentiment', keywords: 'sentiment news' },
  { id: 'nav-recommend', label: t('layout.nav.recommend'), group: t('palette.groupNav'), path: '/daily-recommend', keywords: 'recommend' },
  { id: 'nav-strategies', label: t('layout.nav.strategies'), group: t('palette.groupNav'), path: '/strategies', keywords: 'strategies' },
  { id: 'nav-strategy-library', label: t('layout.nav.strategyLibrary'), group: t('palette.groupNav'), path: '/strategy-library', keywords: 'strategy library code python' },
])

const allItems = computed<CmdItem[]>(() => {
  const wl: CmdItem[] = watchlistStore.items.map((it) => ({
    id: `wl-${it.code}-${it.market}`,
    // 自选名与代码是数据，保持原样
    label: `${it.name} ${it.code}`,
    group: t('palette.groupWatchlist'),
    keywords: `${it.code} ${it.name} ${it.market}`,
    action: () => {
      // 跳首页预选协议收口走 openChartOnHome（修复旧 `code|market` 两段键格式漂移）
      watchlistStore.openChartOnHome({ code: it.code, market: it.market, name: it.name, kind: it.kind })
      router.push('/')
    },
  }))
  const hist: CmdItem[] = historyStore.records.slice(0, 10).map((r) => ({
    id: `hist-${r.id}`,
    // 策略名是用户数据，保持原样
    label: `${r.strategyName} · ${r.stockCode}`,
    group: t('palette.groupRecentBacktest'),
    keywords: `${r.strategyName} ${r.stockCode}`,
    action: () => router.push({ path: '/backtest', query: { historyId: r.id } }),
  }))
  return [...navItems.value, ...wl, ...hist]
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
        :placeholder="t('palette.placeholder')"
      />
      <span class="cmd-hint">{{ t('palette.escHint') }}</span>
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
      <el-empty v-if="!filtered.length" :description="t('palette.noResults')" :image-size="56" />
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
