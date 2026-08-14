<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import dayjs from 'dayjs'
import { klineApi, sentimentApi, recommendApi } from '@/api'
import type { KlineData, SentimentData, DailyRecommendData, Market } from '@/api/types'
import { useWatchlistStore } from '@/stores/watchlist'
import { useBacktestHistoryStore } from '@/stores/backtestHistory'
import { VChart } from '@/composables/useECharts'

const router = useRouter()
const watchlistStore = useWatchlistStore()
const historyStore = useBacktestHistoryStore()

// ===== 大盘指数速览（固定 3 个 A 股指数） =====
const INDEX_PRESETS = [
  { code: '000001', market: 'zh_a' as Market, name: '上证指数' },
  { code: '000300', market: 'zh_a' as Market, name: '沪深300' },
  { code: '399001', market: 'zh_a' as Market, name: '深证成指' },
]

// ===== 快捷入口 =====
const quickActions = [
  { path: '/backtest', icon: 'Histogram', title: '策略回测', desc: 'A股/美股 · 动态绩效图表' },
  { path: '/strategy-compare', icon: 'DataLine', title: '策略对比', desc: '多策略同台竞技' },
  { path: '/factor-analysis', icon: 'DataAnalysis', title: '因子分析', desc: 'IC 分析 · 分层回测' },
  { path: '/sentiment', icon: 'ChatDotRound', title: '舆情分析', desc: '板块情绪 · 热点新闻' },
  { path: '/daily-recommend', icon: 'Star', title: '每日推荐', desc: '多因子打分选股' },
  { path: '/strategies', icon: 'List', title: '策略列表', desc: '查看/管理自有策略' },
]

// ===== K 线主图 =====
const kline = ref<KlineData | null>(null)
const sentiment = ref<SentimentData | null>(null)
const recommend = ref<DailyRecommendData | null>(null)
const loadingKline = ref(false)

// 当前标的（键为 `code|market`），上次选择持久化在 watchlist store
const activeKey = ref(watchlistStore.lastKey || '000001|zh_a')
const activeTarget = computed(() => {
  const found = watchlistStore.items.find((t) => `${t.code}|${t.market}` === activeKey.value)
  return found || watchlistStore.items[0] || INDEX_PRESETS[0]
})

async function loadKline() {
  if (!activeTarget.value) return
  loadingKline.value = true
  try {
    kline.value = await klineApi.get(activeTarget.value.code, activeTarget.value.market, 180)
  } catch (e: any) {
    ElMessage.warning('K线数据加载失败：' + e.message)
    kline.value = null
  } finally {
    loadingKline.value = false
  }
}

// 切换标的时重新加载K线并记忆选择（用 code+market 作为唯一键，避免对象引用比较问题）
watch(activeKey, () => {
  watchlistStore.lastKey = activeKey.value
  loadKline()
})
watch(
  () => watchlistStore.items,
  () => {
    // 自选列表变化后，若当前标的已不存在则回退到第一个
    if (!watchlistStore.items.some((t) => `${t.code}|${t.market}` === activeKey.value)) {
      activeKey.value = watchlistStore.items.length
        ? `${watchlistStore.items[0].code}|${watchlistStore.items[0].market}`
        : '000001|zh_a'
    }
  },
)

// ===== 自选股行情（最新价 + 涨跌幅） =====
interface Quote {
  code: string
  market: Market
  name: string
  close: number
  chgPct: number
}
const quotes = ref<Record<string, Quote>>({})

async function loadQuote(code: string, market: Market, name?: string) {
  try {
    const d = await klineApi.get(code, market, 2)
    if (!d.ohlcv.length) return
    const close = d.ohlcv[d.ohlcv.length - 1][1]
    const prev = d.ohlcv.length > 1 ? d.ohlcv[d.ohlcv.length - 2][1] : close
    quotes.value[`${code}|${market}`] = {
      code,
      market,
      name: d.name || name || code,
      close,
      chgPct: prev ? (close / prev - 1) * 100 : 0,
    }
  } catch {
    // 单只行情失败静默降级（不阻塞首页）
  }
}

// 添加自选：先拉 2 根 K 线校验代码并解析名称
const newCode = ref('')
const newMarket = ref<Market>('zh_a')
const adding = ref(false)

async function addWatch() {
  const code = newCode.value.trim()
  if (!code) {
    ElMessage.warning('请输入股票/指数代码')
    return
  }
  if (watchlistStore.has(code, newMarket.value)) {
    ElMessage.info('该标的已在自选中')
    return
  }
  adding.value = true
  try {
    const d = await klineApi.get(code, newMarket.value, 2)
    watchlistStore.add(code, newMarket.value, d.name || code)
    await loadQuote(code, newMarket.value, d.name)
    newCode.value = ''
    ElMessage.success(`已添加自选：${d.name || code}`)
  } catch (e: any) {
    ElMessage.error('添加失败，请检查代码是否正确：' + e.message)
  } finally {
    adding.value = false
  }
}

function removeWatch(code: string, market: Market) {
  watchlistStore.remove(code, market)
}

// 涨跌配色：A股红涨绿跌，美股绿涨红跌（与主流行情软件一致）
function chgColor(market: Market, chgPct: number): string {
  if (chgPct === 0) return 'var(--neutral)'
  const up = chgPct > 0
  if (market === 'zh_a') return up ? 'var(--danger)' : 'var(--success)'
  return up ? 'var(--success)' : 'var(--danger)'
}

// ===== 最近回测（本地持久化） =====
const recentBacktests = computed(() => historyStore.records.slice(0, 5))
function fmtTime(ts: string): string {
  return dayjs(ts).format('MM-DD HH:mm')
}
function rerunBacktest(id: string) {
  router.push({ path: '/backtest', query: { historyId: id } })
}

// ===== 首屏加载 =====
async function loadAll() {
  // 自选 + 指数速览的行情（并行，失败静默）
  const quoteTargets = new Map<string, { code: string; market: Market; name?: string }>()
  for (const i of INDEX_PRESETS) quoteTargets.set(`${i.code}|${i.market}`, i)
  for (const it of watchlistStore.items) quoteTargets.set(`${it.code}|${it.market}`, it)
  quoteTargets.forEach((t) => loadQuote(t.code, t.market, t.name))
  // K线
  await loadKline()
  // 舆情
  sentimentApi.get().then((d) => (sentiment.value = d)).catch((e: any) => {
    // 舆情数据获取较慢或需联网，失败时静默降级
    console.warn('舆情数据加载失败', e.message)
  })
  // 推荐
  recommendApi.get().then((d) => (recommend.value = d)).catch((e: any) => {
    console.warn('推荐数据加载失败', e.message)
  })
}
onMounted(loadAll)

// K线 ECharts 配置：蜡烛图 + 成交量
const klineOption = computed(() => {
  if (!kline.value || !kline.value.dates.length) return {}
  const k = kline.value
  // A股红涨绿跌；美股绿涨红跌
  const isUS = k.market === 'us'
  const upColor = isUS ? '#26a69a' : '#ef232a'
  const downColor = isUS ? '#ef5350' : '#14b143'
  return {
    title: {
      text: `${k.name || k.code} ${isUS ? '(美股)' : '(A股)'}`,
      left: 'center',
      textStyle: { fontSize: 16, fontWeight: 600 },
    },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross' },
    },
    legend: { data: ['日K', '成交量'], top: 28, left: 'center' },
    grid: [
      { left: '6%', right: '3%', top: 60, height: '58%' },
      { left: '6%', right: '3%', top: '76%', height: '16%' },
    ],
    xAxis: [
      {
        type: 'category',
        data: k.dates,
        boundaryGap: true,
        axisLine: { onZero: false },
        splitLine: { show: false },
        min: 'dataMin',
        max: 'dataMax',
      },
      {
        type: 'category',
        gridIndex: 1,
        data: k.dates,
        boundaryGap: true,
        axisLabel: { show: false },
      },
    ],
    yAxis: [
      { scale: true, splitArea: { show: true } },
      { gridIndex: 1, splitNumber: 2, axisLabel: { show: false } },
    ],
    dataZoom: [
      { type: 'inside', xAxisIndex: [0, 1], start: 60, end: 100 },
      { type: 'slider', xAxisIndex: [0, 1], top: '94%', start: 60, end: 100 },
    ],
    series: [
      {
        name: '日K',
        type: 'candlestick',
        data: k.ohlcv,
        itemStyle: {
          color: upColor,
          color0: downColor,
          borderColor: upColor,
          borderColor0: downColor,
        },
      },
      {
        name: '成交量',
        type: 'bar',
        xAxisIndex: 1,
        yAxisIndex: 1,
        data: k.volumes.map((v, i) => ({
          value: v,
          itemStyle: { color: k.ohlcv[i] && k.ohlcv[i][1] >= k.ohlcv[i][0] ? upColor : downColor },
        })),
      },
    ],
  }
})

function sectorColor(sentiment: number): string {
  if (sentiment >= 70) return '#28a745'
  if (sentiment <= 40) return '#dc3545'
  return '#6c757d'
}
function scoreColor(score: number): string {
  if (score >= 70) return '#28a745'
  if (score >= 60) return '#667eea'
  return '#f59e0b'
}
</script>

<template>
  <div class="dashboard">
    <!-- 快捷入口 -->
    <el-row :gutter="12" class="quick-row">
      <el-col v-for="qa in quickActions" :key="qa.path" :xs="12" :sm="8" :md="4">
        <router-link :to="qa.path" class="quick-card">
          <el-icon :size="22"><component :is="qa.icon" /></el-icon>
          <div class="quick-text">
            <div class="quick-title">{{ qa.title }}</div>
            <div class="quick-desc">{{ qa.desc }}</div>
          </div>
        </router-link>
      </el-col>
    </el-row>

    <!-- 大盘指数速览 -->
    <el-row :gutter="12" class="index-row">
      <el-col v-for="idx in INDEX_PRESETS" :key="idx.code" :xs="24" :sm="8">
        <div class="index-card">
          <span class="index-name">{{ idx.name }}</span>
          <template v-if="quotes[`${idx.code}|${idx.market}`]">
            <span class="index-close">{{ quotes[`${idx.code}|${idx.market}`].close.toFixed(2) }}</span>
            <span
              class="index-chg"
              :style="{ color: chgColor(idx.market, quotes[`${idx.code}|${idx.market}`].chgPct) }"
            >
              {{ quotes[`${idx.code}|${idx.market}`].chgPct >= 0 ? '+' : '' }}{{ quotes[`${idx.code}|${idx.market}`].chgPct.toFixed(2) }}%
            </span>
          </template>
          <span v-else class="index-close index-loading">加载中…</span>
        </div>
      </el-col>
    </el-row>

    <!-- 主区：K线图 + 右侧自选/最近回测 -->
    <el-row :gutter="16">
      <el-col :xs="24" :md="16">
        <el-card shadow="never" class="kline-card">
          <template #header>
            <div class="kline-header">
              <span class="section-title" style="margin: 0; border: none; padding: 0">
                <el-icon><CandlestickChart /></el-icon> 行情看板
              </span>
              <el-select
                v-model="activeKey"
                placeholder="选择标的"
                style="width: 200px"
                filterable
              >
                <el-option
                  v-for="t in watchlistStore.items"
                  :key="t.code + t.market"
                  :label="`${t.name} (${t.code})`"
                  :value="`${t.code}|${t.market}`"
                />
              </el-select>
            </div>
          </template>
          <div v-loading="loadingKline" class="kline-body">
            <v-chart v-if="kline && kline.dates.length" class="kline-chart" :option="klineOption" autoresize />
            <el-empty v-else-if="!loadingKline" description="暂无K线数据" />
          </div>
        </el-card>
      </el-col>

      <el-col :xs="24" :md="8" class="side-col">
        <!-- 自选股（本地持久化） -->
        <el-card shadow="never" class="side-card">
          <template #header>
            <span class="section-title" style="margin: 0; border: none; padding: 0">
              <el-icon><Collection /></el-icon> 自选股
            </span>
          </template>
          <div class="watch-add">
            <el-input
              v-model="newCode"
              :placeholder="newMarket === 'us' ? '美股代码，如 AAPL' : '6位代码，如 600938'"
              size="small"
              @keyup.enter="addWatch"
            />
            <el-select v-model="newMarket" size="small" style="width: 84px">
              <el-option label="A股" value="zh_a" />
              <el-option label="美股" value="us" />
            </el-select>
            <el-button type="primary" size="small" :loading="adding" @click="addWatch">
              <el-icon><Plus /></el-icon>
            </el-button>
          </div>
          <div class="watch-list">
            <div
              v-for="item in watchlistStore.items"
              :key="`${item.code}|${item.market}`"
              class="watch-item"
              :class="{ active: activeKey === `${item.code}|${item.market}` }"
              @click="activeKey = `${item.code}|${item.market}`"
            >
              <div class="watch-name">
                <span class="watch-title">{{ item.name }}</span>
                <code class="watch-code">{{ item.code }}</code>
              </div>
              <template v-if="quotes[`${item.code}|${item.market}`]">
                <span class="watch-close">{{ quotes[`${item.code}|${item.market}`].close.toFixed(2) }}</span>
                <span
                  class="watch-chg"
                  :style="{ color: chgColor(item.market, quotes[`${item.code}|${item.market}`].chgPct) }"
                >
                  {{ quotes[`${item.code}|${item.market}`].chgPct >= 0 ? '+' : '' }}{{ quotes[`${item.code}|${item.market}`].chgPct.toFixed(2) }}%
                </span>
              </template>
              <span v-else class="watch-close watch-pending">…</span>
              <el-button
                class="watch-del"
                text
                circle
                size="small"
                title="移除自选"
                @click.stop="removeWatch(item.code, item.market)"
              >
                <el-icon :size="14"><Close /></el-icon>
              </el-button>
            </div>
            <el-empty
              v-if="!watchlistStore.items.length"
              :image-size="60"
              description="暂无自选，输入代码添加"
            />
          </div>
        </el-card>

        <!-- 最近回测（本地持久化） -->
        <el-card shadow="never" class="side-card">
          <template #header>
            <div class="kline-header">
              <span class="section-title" style="margin: 0; border: none; padding: 0">
                <el-icon><Clock /></el-icon> 最近回测
              </span>
              <el-button
                v-if="historyStore.records.length"
                text
                size="small"
                type="danger"
                @click="historyStore.clear()"
              >
                清空
              </el-button>
            </div>
          </template>
          <div class="history-list">
            <div v-for="r in recentBacktests" :key="r.id" class="history-item">
              <div class="history-main">
                <div class="history-head">
                  <span class="history-strategy">{{ r.strategyName }}</span>
                  <code class="watch-code">{{ r.stockCode }}</code>
                  <span class="history-return" :style="{ color: r.totalReturn >= 0 ? 'var(--danger)' : 'var(--success)' }">
                    {{ (r.totalReturn * 100).toFixed(2) }}%
                  </span>
                </div>
                <small class="history-meta">
                  {{ fmtTime(r.ts) }} · 回撤 {{ (r.maxDrawdown * 100).toFixed(1) }}% · 夏普 {{ r.sharpe.toFixed(2) }}
                </small>
              </div>
              <el-button text size="small" type="primary" @click="rerunBacktest(r.id)">
                <el-icon><VideoPlay /></el-icon> 重跑
              </el-button>
            </div>
            <el-empty
              v-if="!recentBacktests.length"
              :image-size="60"
              description="还没有回测记录"
            />
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 下部三栏：热门板块 / 热门舆情 / 个股推荐 -->
    <el-row :gutter="16" class="info-row">
      <!-- 热门板块 -->
      <el-col :xs="24" :md="8">
        <el-card shadow="never" class="info-card">
          <template #header>
            <span class="section-title" style="margin: 0; border: none; padding: 0">
              <el-icon><Sunrise /></el-icon> 热门板块 TOP
            </span>
          </template>
          <div class="info-body">
            <div
              v-for="s in (recommend?.top_sectors || sentiment?.sectors || []).slice(0, 6)"
              :key="s.name"
              class="sector-row"
            >
              <div class="sector-row-head">
                <span class="sector-name">{{ s.name }}</span>
                <span class="sector-score" :style="{ color: sectorColor(s.sentiment) }">{{ s.sentiment }}</span>
              </div>
              <el-progress
                :percentage="s.sentiment"
                :color="sectorColor(s.sentiment)"
                :stroke-width="6"
                :show-text="false"
              />
            </div>
            <el-empty v-if="!(recommend?.top_sectors?.length || sentiment?.sectors?.length)" :image-size="60" description="暂无板块数据" />
          </div>
        </el-card>
      </el-col>

      <!-- 热门舆情 -->
      <el-col :xs="24" :md="8">
        <el-card shadow="never" class="info-card">
          <template #header>
            <span class="section-title" style="margin: 0; border: none; padding: 0">
              <el-icon><ChatDotRound /></el-icon> 当日舆情
            </span>
          </template>
          <div class="info-body news-body">
            <div v-for="(n, i) in (sentiment?.news_list || []).slice(0, 6)" :key="i" class="news-item">
              <div class="news-source">
                <el-icon><Link /></el-icon> {{ n.source || '未知来源' }}
                <span v-if="n.date" class="news-date">{{ n.date }}</span>
              </div>
              <a v-if="n.url" :href="n.url" target="_blank" class="news-title">{{ n.title }}</a>
              <div v-else class="news-title">{{ n.title }}</div>
            </div>
            <el-empty v-if="!sentiment?.news_list?.length" :image-size="60" description="暂无舆情数据" />
          </div>
        </el-card>
      </el-col>

      <!-- 个股推荐 -->
      <el-col :xs="24" :md="8">
        <el-card shadow="never" class="info-card">
          <template #header>
            <span class="section-title" style="margin: 0; border: none; padding: 0">
              <el-icon><Star /></el-icon> 个股推荐
            </span>
          </template>
          <div class="info-body">
            <div v-for="r in (recommend?.recommendations || []).slice(0, 6)" :key="r.code" class="rec-item">
              <el-tag :type="r.rank <= 3 ? (r.rank === 1 ? 'warning' : r.rank === 2 ? 'info' : 'danger') : 'info'" effect="dark" round size="small">{{ r.rank }}</el-tag>
              <div class="rec-main">
                <div class="rec-head">
                  <span class="rec-name">{{ r.name }}</span>
                  <code class="rec-code">{{ r.code }}</code>
                  <span class="rec-score" :style="{ color: scoreColor(r.score) }">{{ r.score }}</span>
                </div>
                <small class="rec-reason">{{ r.reason }}</small>
              </div>
            </div>
            <el-empty v-if="!recommend?.recommendations?.length" :image-size="60" description="暂无推荐数据" />
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<style scoped>
.dashboard {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.dashboard > .el-row {
  width: 100%;
}

/* 快捷入口 */
.quick-card {
  display: flex;
  align-items: center;
  gap: 10px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 12px 14px;
  margin-bottom: 12px;
  color: var(--text);
  transition: border-color 0.15s, box-shadow 0.15s, transform 0.15s;
}
.quick-card:hover {
  border-color: var(--brand-start);
  box-shadow: var(--shadow);
  transform: translateY(-2px);
}
.quick-card .el-icon {
  color: var(--brand-start);
  flex-shrink: 0;
}
.quick-title {
  font-weight: 600;
  font-size: 0.92rem;
  line-height: 1.3;
}
.quick-desc {
  font-size: 0.74rem;
  color: var(--text-muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* 指数速览 */
.index-card {
  display: flex;
  align-items: baseline;
  gap: 10px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 10px 16px;
  margin-bottom: 12px;
}
.index-name {
  font-weight: 600;
  color: var(--text-muted);
  font-size: 0.9rem;
}
.index-close {
  font-size: 1.2rem;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}
.index-chg {
  font-size: 0.9rem;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}
.index-loading {
  color: var(--text-muted);
  font-size: 0.85rem;
  font-weight: 400;
}

/* K线主图 */
.kline-card {
  border-radius: var(--radius);
}
.kline-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.kline-body {
  min-height: 460px;
}
.kline-chart {
  height: 460px;
  width: 100%;
}

/* 右栏：自选 + 最近回测 */
.side-col {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.side-card {
  border-radius: var(--radius);
}
.watch-add {
  display: flex;
  gap: 8px;
  margin-bottom: 10px;
}
.watch-list {
  max-height: 300px;
  overflow-y: auto;
}
.watch-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 7px 8px;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.12s;
}
.watch-item:hover {
  background: var(--bg);
}
.watch-item.active {
  background: rgba(102, 126, 234, 0.12);
}
.watch-name {
  flex: 1;
  min-width: 0;
  display: flex;
  align-items: baseline;
  gap: 6px;
  overflow: hidden;
}
.watch-title {
  font-weight: 600;
  font-size: 0.9rem;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.watch-code {
  font-size: 0.72rem;
  color: var(--text-muted);
}
.watch-close {
  font-variant-numeric: tabular-nums;
  font-weight: 600;
  font-size: 0.88rem;
}
.watch-chg {
  width: 62px;
  text-align: right;
  font-variant-numeric: tabular-nums;
  font-weight: 700;
  font-size: 0.85rem;
}
.watch-pending {
  color: var(--text-muted);
  font-weight: 400;
}
.watch-del {
  flex-shrink: 0;
  opacity: 0;
  transition: opacity 0.12s;
}
.watch-item:hover .watch-del {
  opacity: 1;
}

/* 最近回测 */
.history-list {
  max-height: 260px;
  overflow-y: auto;
}
.history-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 7px 8px;
  border-radius: 8px;
}
.history-item:hover {
  background: var(--bg);
}
.history-main {
  flex: 1;
  min-width: 0;
}
.history-head {
  display: flex;
  align-items: baseline;
  gap: 6px;
}
.history-strategy {
  font-weight: 600;
  font-size: 0.9rem;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.history-return {
  margin-left: auto;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}
.history-meta {
  color: var(--text-muted);
  font-size: 0.74rem;
  display: block;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* 下部三栏 */
.info-row {
  margin-top: 0 !important;
}
.info-card {
  border-radius: var(--radius);
  height: 100%;
}
.info-body {
  min-height: 280px;
  max-height: 380px;
  overflow-y: auto;
}

/* 板块行 */
.sector-row {
  margin-bottom: 14px;
}
.sector-row-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}
.sector-name {
  font-weight: 600;
}
.sector-score {
  font-weight: 700;
  font-size: 1.1rem;
}

/* 舆情 */
.news-body {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.news-item {
  border-left: 3px solid var(--brand-start);
  padding-left: 10px;
}
.news-source {
  font-size: 0.78rem;
  color: var(--text-muted);
  margin-bottom: 3px;
  display: flex;
  align-items: center;
  gap: 4px;
}
.news-date {
  margin-left: auto;
}
.news-title {
  font-size: 0.92rem;
  color: var(--text);
  line-height: 1.4;
  font-weight: 500;
}

/* 推荐 */
.rec-item {
  display: flex;
  gap: 10px;
  margin-bottom: 12px;
  align-items: flex-start;
}
.rec-main {
  flex: 1;
  min-width: 0;
}
.rec-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 2px;
}
.rec-name {
  font-weight: 600;
}
.rec-code {
  font-size: 0.78rem;
  color: var(--text-muted);
}
.rec-score {
  margin-left: auto;
  font-weight: 700;
  font-size: 1.05rem;
}
.rec-reason {
  color: var(--text-muted);
  display: block;
  line-height: 1.4;
}
</style>
