<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import dayjs from 'dayjs'
import { klineApi, sentimentApi, recommendApi, marketApi } from '@/api'
import type {
  KlineData,
  SentimentData,
  DailyRecommendData,
  Market,
  SentimentCalendarItem,
  MarketBreadth,
  SectorBoardData,
  SourceBeat,
  SourceHealthData,
} from '@/api/types'
import { useWatchlistStore, targetKey } from '@/stores/watchlist'
import type { WatchlistItem } from '@/stores/watchlist'
import { chartPalette, deltaTone, deltaDirection, NEUTRAL_HEX } from '@/lib/marketColors'
import {
  candleItemStyle,
  chgVsPrevClose,
  crosshairPointer,
  fmtPriceNum,
  klineDataZoom,
  klineXAxis,
  linkedCrosshair,
  monthTickConfig,
} from '@/chart/kline'
import { useBacktestHistoryStore } from '@/stores/backtestHistory'
import { calcMA, calcBOLL, calcMACD, calcKDJ, calcRSI } from '@/lib/indicators'
import { useHomeLayoutStore } from '@/stores/homeLayout'
import { useUiStore } from '@/stores/ui'
import { usePolling } from '@/composables/usePolling'
import { VChart } from '@/composables/useECharts'
import SentimentCalendar from '@/components/SentimentCalendar.vue'
import MiniSparkline from '@/components/MiniSparkline.vue'
import AnimNumber from '@/components/AnimNumber.vue'

const router = useRouter()
const watchlistStore = useWatchlistStore()
const historyStore = useBacktestHistoryStore()
const homeLayoutStore = useHomeLayoutStore()
const uiStore = useUiStore()

// ===== 仪表盘可拖拽布局（与 stores/homeLayout 保持一致） =====
const DEFAULT_WIDGETS = [
  { id: 'quick', title: '快捷入口', icon: 'Histogram' },
  { id: 'indexes', title: '指数速览', icon: 'TrendCharts' },
  { id: 'breadth', title: '市场宽度', icon: 'Odometer' },
  { id: 'kline', title: '行情看板', icon: 'CandlestickChart' },
  { id: 'heatmap', title: '行业热力图', icon: 'Grid' },
  { id: 'sectors', title: '热门板块', icon: 'Sunrise' },
  { id: 'news', title: '当日舆情', icon: 'ChatDotRound' },
  { id: 'recommend', title: '个股推荐', icon: 'Star' },
  { id: 'allocation', title: '自选分布', icon: 'PieChart' },
  { id: 'srchealth', title: '数据源心跳', icon: 'Monitor' },
] as const

type WidgetId = (typeof DEFAULT_WIDGETS)[number]['id']

// 与 HomeWidgetId 同源，避免 stores/homeLayout 里的 DEFAULT_HOME_ORDER 漂移时漏同步
const widgetMeta = computed(() => {
  const meta = new Map<string, { title: string; icon: string }>()
  for (const w of DEFAULT_WIDGETS) meta.set(w.id, w)
  return meta
})

/** 按持久化顺序渲染的 widget 列表 */
const orderedWidgets = computed(() =>
  homeLayoutStore.order
    .map((id) => ({ id, meta: widgetMeta.value.get(id) }))
    .filter((w): w is { id: WidgetId; meta: { title: string; icon: string } } => Boolean(w.meta)),
)

// 拖拽重排：dragstart 记录来源索引，dragover 放行，drop 时移动
const dragFrom = ref<number | null>(null)
const draggingIndex = ref<number | null>(null)

function onDragStart(event: DragEvent, index: number) {
  // 仅允许从手柄发起拖拽，避免干扰卡片内输入框/图表的正常交互
  const handle = (event.target as HTMLElement).closest('.widget-handle')
  if (!handle) {
    event.preventDefault()
    return
  }
  dragFrom.value = index
  draggingIndex.value = index
}
function onDragOver() {
  // HTML5 拖拽必须 preventDefault 才能触发 drop
}
function onDrop(targetIndex: number) {
  const from = dragFrom.value
  dragFrom.value = null
  draggingIndex.value = null
  if (from === null || from === targetIndex) return
  homeLayoutStore.move(from, targetIndex)
}
function onDragEnd() {
  dragFrom.value = null
  draggingIndex.value = null
}
function resetLayout() {
  homeLayoutStore.reset()
  ElMessage.success('已恢复默认布局')
}

// ===== 大盘指数速览（固定 3 个 A 股指数；kind=index 走服务端指数数据链） =====
const INDEX_PRESETS = [
  { code: '000001', market: 'zh_a' as Market, name: '上证指数', kind: 'index' as const },
  { code: '000300', market: 'zh_a' as Market, name: '沪深300', kind: 'index' as const },
  { code: '399001', market: 'zh_a' as Market, name: '深证成指', kind: 'index' as const },
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
const klineChartRef = ref<InstanceType<typeof VChart> | null>(null)

// ===== K线工具栏偏好（周期/复权/主图叠加/副图指标），持久化到 localStorage =====
function loadPref<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key)
    if (raw !== null) return JSON.parse(raw) as T
  } catch { /* ignore */ }
  return fallback
}
function savePref(key: string, value: unknown) {
  try { localStorage.setItem(key, JSON.stringify(value)) } catch { /* quota */ }
}

type KlinePeriod = 'day' | 'week' | 'month'
type KlineAdjust = 'qfq' | 'hfq' | 'nfq'
type OverlayMode = 'none' | 'ma' | 'boll'
type SubIndicator = 'none' | 'macd' | 'kdj' | 'rsi'

const PERIOD_KEY = 'emoqunt:kline_period'
const ADJUST_KEY = 'emoqunt:kline_adjust'
const OVERLAY_KEY = 'emoqunt:kline_overlay'
const SUB_KEY = 'emoqunt:kline_sub'

const PERIOD_LABELS: Record<KlinePeriod, string> = { day: '日线', week: '周线', month: '月线' }
const ADJUST_LABELS: Record<KlineAdjust, string> = { qfq: '前复权', hfq: '后复权', nfq: '不复权' }

const klinePeriod = ref(loadPref<KlinePeriod>(PERIOD_KEY, 'day'))
// 兼容旧「MA 开关」：kline_ma=false 迁移为主图叠加=无
const klineOverlayInit = loadPref<OverlayMode | ''>(OVERLAY_KEY, '')
const klineOverlay = ref<OverlayMode>(
  klineOverlayInit === 'ma' || klineOverlayInit === 'boll' || klineOverlayInit === 'none'
    ? klineOverlayInit
    : (loadPref('emoqunt:kline_ma', true) ? 'ma' : 'none'),
)
const klineAdjust = ref(loadPref(ADJUST_KEY, 'qfq') as KlineAdjust)
const klineSub = ref(loadPref(SUB_KEY, 'macd') as SubIndicator)

watch(klinePeriod, (v) => savePref(PERIOD_KEY, v))
watch(klineOverlay, (v) => savePref(OVERLAY_KEY, v))
watch(klineAdjust, (v) => savePref(ADJUST_KEY, v))
watch(klineSub, (v) => savePref(SUB_KEY, v))

function resetKlineZoom() {
  try {
    const inst: any = (klineChartRef.value as any)?.chart
    if (inst?.dispatchAction) {
      for (let i = 0; i < 3; i++) {
        inst.dispatchAction({ type: 'dataZoom', dataZoomIndex: i, start: 60, end: 100 })
      }
    }
  } catch { /* ignore */ }
}

// 当前标的（键为 `code|market|kind`，第三段区分上证指数/平安银行这类二义代码），持久化在 watchlist store
function normKey(key: string): string {
  if (!key) return ''
  const parts = key.split('|')
  if (parts.length >= 3) return key
  // 旧持久化格式 code|market：按自选条目回填 kind
  const item = watchlistStore.items.find((i) => i.code === parts[0] && i.market === parts[1])
  return targetKey(parts[0] ?? '', (parts[1] as Market) ?? 'zh_a', item?.kind)
}
function firstItemKey(): string {
  const first = watchlistStore.items[0]
  return first ? targetKey(first.code, first.market, first.kind) : '000001|zh_a|index'
}
const activeKey = ref(normKey(watchlistStore.lastKey) || firstItemKey())
const activeTarget = computed<{ code: string; market: Market; name: string; kind?: 'index' } | null>(() => {
  const found = watchlistStore.findByKey(activeKey.value)
  if (found) return found
  // 指数速览卡片可点击切换到未在自选中的预设指数
  const preset = INDEX_PRESETS.find((i) => targetKey(i.code, i.market, i.kind) === activeKey.value)
  if (preset) return { code: preset.code, market: preset.market, name: preset.name, kind: preset.kind }
  return watchlistStore.items[0] ?? null
})
/** 是否指数标的：指数无复权概念，禁用复权选择 */
const isIndexTarget = computed(() => activeTarget.value?.kind === 'index')

function selectIndex(idx: (typeof INDEX_PRESETS)[number]) {
  activeKey.value = targetKey(idx.code, idx.market, idx.kind)
}

async function loadKline() {
  if (!activeTarget.value) return
  loadingKline.value = true
  try {
    kline.value = await klineApi.get(
      activeTarget.value.code, activeTarget.value.market, 180,
      klinePeriod.value, klineAdjust.value,
      isIndexTarget.value ? 'index' : '',
    )
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
// 周期/复权切换重新拉数据
watch([klinePeriod, klineAdjust], () => loadKline())
watch(
  () => watchlistStore.lastKey,
  (v) => {
    if (v && v !== activeKey.value) activeKey.value = v
  },
)
watch(
  () => watchlistStore.items,
  () => {
    // 自选列表变化后，若当前标的已不存在（既不在自选也不是指数预设）则回退
    const stillValid =
      watchlistStore.findByKey(activeKey.value) ||
      INDEX_PRESETS.some((i) => targetKey(i.code, i.market, i.kind) === activeKey.value)
    if (!stillValid) activeKey.value = firstItemKey()
  },
)

// ===== 自选股行情（最新价 + 涨跌幅 + 行内走势） =====
interface Quote {
  code: string
  market: Market
  name: string
  close: number
  chgPct: number
  /** 最近 30 根收盘价（行内 sparkline 用） */
  closes: number[]
}
const quotes = ref<Record<string, Quote>>({})
/** 行情刷新闪烁方向（key → 'up'/'down'），短暂高亮后自动清除 */
const flashMap = ref<Record<string, 'up' | 'down'>>({})

function quoteOf(code: string, market: Market, kind?: 'index'): Quote | undefined {
  return quotes.value[targetKey(code, market, kind)]
}
function flashOf(code: string, market: Market, kind?: 'index'): string {
  return flashMap.value[targetKey(code, market, kind)] ?? ''
}

interface QuoteTarget {
  code: string
  market: Market
  name?: string
  kind?: '' | 'index'
}

async function loadQuote(code: string, market: Market, name?: string, kind?: '' | 'index') {
  try {
    // 拉 30 根日线：最新价/涨跌 + 行内 sparkline 一次取齐
    const d = await klineApi.get(code, market, 30, 'day', '', kind ?? '')
    if (!d.ohlcv.length) return
    const closes = d.ohlcv.map((o) => o[1])
    const close = closes[closes.length - 1] ?? 0
    const prev = closes.length > 1 ? closes[closes.length - 2]! : close
    const chgPct = prev ? (close / prev - 1) * 100 : 0
    const key = targetKey(code, market, kind)
    const old = quotes.value[key]
    quotes.value[key] = {
      code,
      market,
      name: d.name || name || code,
      close,
      chgPct,
      closes,
    }
    // 价格变化时按方向闪烁一次（SWR 轮询的可见反馈）
    if (old && old.close !== close) {
      flashMap.value[key] = close > old.close ? 'up' : 'down'
      setTimeout(() => delete flashMap.value[key], 900)
    }
  } catch {
    // 单只行情失败静默降级（不阻塞首页）
  }
}

/** 拉取全部自选 + 指数速览行情（轮询复用） */
function loadQuotes() {
  const quoteTargets = new Map<string, QuoteTarget>()
  for (const i of INDEX_PRESETS) quoteTargets.set(targetKey(i.code, i.market, i.kind), i)
  for (const it of watchlistStore.items) quoteTargets.set(targetKey(it.code, it.market, it.kind), it)
  quoteTargets.forEach((t) => loadQuote(t.code, t.market, t.name, t.kind))
}

// SWR 式轮询：页面不可见暂停、失败指数退避（日线数据 60s 足够）
usePolling(loadQuotes, { intervalMs: 60_000 })
// 数据源心跳变化缓慢，5 分钟刷一次
usePolling(loadSourceHealth, { intervalMs: 300_000 })

/** 行内 sparkline 颜色：按区间涨跌取市场涨跌色（A股红涨绿跌 / 美股绿涨红跌） */
function sparkColor(item: WatchlistItem): string {
  const closes = quoteOf(item.code, item.market, item.kind)?.closes ?? []
  if (closes.length < 2) return '#667eea'
  const up = (closes[closes.length - 1] ?? 0) >= (closes[0] ?? 0)
  const { up: upColor, down: downColor } = chartPalette(item.market)
  return up ? upColor : downColor
}

/** 指数速览 sparkline 颜色：按当日涨跌取市场涨跌色（收拢模板内联三元） */
function chgSparkColor(market: Market, chgPct: number | undefined): string {
  const { up, down } = chartPalette(market)
  return (chgPct ?? 0) < 0 ? down : up
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
    const d = await klineApi.get(code, newMarket.value, 30)
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

function removeWatch(code: string, market: Market, kind?: 'index') {
  watchlistStore.remove(code, market, kind)
}

// 涨跌徽章（A股红涨绿跌，美股绿涨红跌；方向→色调语义映射收拢在 lib/marketColors）
function deltaBadgeStyle(market: Market, chgPct: number): Record<string, string> {
  const tone = deltaTone(market, deltaDirection(chgPct))
  if (tone === 'neutral') return { background: 'var(--neutral)', color: '#fff' }
  return tone === 'danger'
    ? { background: '#fef2f2', color: 'var(--danger)', border: '1px solid #fecaca' }
    : { background: '#f0fdf4', color: 'var(--success)', border: '1px solid #bbf7d0' }
}

// ===== 情绪日历 =====
const calendar = ref<SentimentCalendarItem[]>([])

// ===== 市场宽度 + 板块热力图 =====
const breadth = ref<MarketBreadth | null>(null)
const sectorBoard = ref<SectorBoardData | null>(null)
const loadingBreadth = ref(false)
const loadingSectors = ref(false)

// ===== 数据源健康心跳（Uptime Kuma beat bar 模式） =====
const sourceHealth = ref<SourceHealthData | null>(null)

/** 展示的数据源与顺序（与后端取数链一致；未启用的源显示灰格） */
const HEALTH_SOURCES: { key: string; label: string }[] = [
  { key: 'tushare', label: 'Tushare' },
  { key: 'yfinance', label: 'Yahoo' },
  { key: 'sina', label: '新浪' },
  { key: 'eastmoney', label: '东财' },
  { key: 'baostock', label: 'BaoStock' },
]

/** 补齐为固定 7 格（旧→新，左侧补灰格） */
function beatsOf(key: string): (SourceBeat | null)[] {
  const beats = sourceHealth.value?.sources[key] ?? []
  const pad = Math.max(0, 7 - beats.length)
  return [...Array<null>(pad).fill(null), ...beats]
}
function beatTitle(b: SourceBeat | null): string {
  if (!b) return '暂无记录'
  return `${b.ok ? '成功' : '失败'} · ${dayjs(b.ts * 1000).format('MM-DD HH:mm')}`
}
function lastBeatText(key: string): string {
  const beats = sourceHealth.value?.sources[key] ?? []
  if (!beats.length) return '—'
  const last = beats[beats.length - 1]!
  return `${last.ok ? '✓' : '✗'} ${dayjs(last.ts * 1000).format('HH:mm')}`
}
const hasHealthData = computed(() => Object.keys(sourceHealth.value?.sources ?? {}).length > 0)

async function loadSourceHealth() {
  try {
    sourceHealth.value = await marketApi.sourceHealth()
  } catch (e: any) {
    console.warn('数据源健康加载失败', e.message)
  }
}

// ===== 快讯流（来源分组过滤；数据仍来自情绪快照的 news_list） =====
const newsSourceFilter = ref('全部')
const newsSources = computed(() => {
  const sources: string[] = []
  for (const n of sentiment.value?.news_list || []) {
    const s = cleanNewsSource(n.source)
    if (!sources.includes(s)) sources.push(s)
  }
  return ['全部', ...sources]
})
const filteredNews = computed(() => {
  const list = sentiment.value?.news_list || []
  const picked =
    newsSourceFilter.value === '全部'
      ? list
      : list.filter((n) => cleanNewsSource(n.source) === newsSourceFilter.value)
  return picked.slice(0, 10)
})

/** 来源徽标配色：按来源名哈希取固定色板 */
const NEWS_SOURCE_COLORS = ['#667eea', '#10b981', '#f59e0b', '#8b5cf6', '#0ea5e9', '#ec4899']

/** 清洗来源名：trendradar 解析出的来源可能带 [URL:...] 附件或超长，展示与分组统一截净 */
function cleanNewsSource(source?: string): string {
  const s = (source || '未知来源').split(' [URL:')[0].split(' [MOBILE:')[0].trim()
  return (s || '未知来源').slice(0, 16)
}
function newsSourceColor(source?: string): string {
  const s = cleanNewsSource(source)
  let h = 0
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) >>> 0
  return NEWS_SOURCE_COLORS[h % NEWS_SOURCE_COLORS.length]
}

const breadthUpPct = computed(() => {
  if (!breadth.value) return 50
  const total = breadth.value.up + breadth.value.down
  if (!total) return 50
  return Math.round((breadth.value.up / total) * 100)
})

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
  loadQuotes()
  // K线
  await loadKline()
  // 舆情
  sentimentApi.get().then((d) => (sentiment.value = d)).catch((e: any) => {
    // 舆情数据获取较慢或需联网，失败时静默降级
    console.warn('舆情数据加载失败', e.message)
  })
  // 情绪日历（仅读本地快照，失败静默）
  sentimentApi.calendar().then((d) => (calendar.value = d)).catch((e: any) => {
    console.warn('情绪日历加载失败', e.message)
  })
  // 推荐
  recommendApi.get().then((d) => (recommend.value = d)).catch((e: any) => {
    console.warn('推荐数据加载失败', e.message)
  })
  // 市场宽度
  loadingBreadth.value = true
  marketApi.breadth().then((d) => (breadth.value = d)).catch((e: any) => {
    console.warn('市场宽度加载失败', e.message)
  }).finally(() => (loadingBreadth.value = false))
  // 板块行情（热力图数据源）
  loadingSectors.value = true
  marketApi.sectors().then((d) => (sectorBoard.value = d)).catch((e: any) => {
    console.warn('板块行情加载失败', e.message)
  }).finally(() => (loadingSectors.value = false))
  // 数据源健康心跳
  loadSourceHealth()
}
onMounted(() => {
  loadAll()
  // 首访导览：仅首次进入弹出（ui store 持久化，重放入口在布局工具栏）
  if (!uiStore.tourDone) {
    setTimeout(() => {
      import('@/composables/useHomeTour')
        .then((m) => m.startHomeTour())
        .catch(() => {})
    }, 900)
  }
})

// ===== 首访导览重放 + 空态引导 =====
const newCodeInput = ref<{ focus: () => void } | null>(null)
function focusWatchInput() {
  newCodeInput.value?.focus()
}
function replayTour() {
  import('@/composables/useHomeTour')
    .then((m) => m.startHomeTour())
    .catch(() => {})
}
// 个股推荐点击：加入自选（若未跟踪）并切换主图（卡片下钻：概览 → 个股主图）
function openRecInChart(rec: { code: string; name: string }) {
  activeKey.value = watchlistStore.openChartOnHome({ code: rec.code, market: 'zh_a', name: rec.name })
}

// 成交量格式化：亿/万自适应
function fmtVol(v: number): string {
  if (!isFinite(v)) return '-'
  const a = Math.abs(v)
  if (a >= 1e8) return (v / 1e8).toFixed(2) + '亿'
  if (a >= 1e4) return (v / 1e4).toFixed(1) + '万'
  return String(Math.round(v))
}

function heatColor(chg: number): string {
  const v = Math.max(-5, Math.min(5, chg))
  if (v > 0) {
    const t = v / 5
    // 白 -> 浅红 -> 深红
    if (t < 0.5) return t < 0.25 ? '#fecaca' : '#f87171'
    return t < 0.75 ? '#ef4444' : '#991b1b'
  }
  if (v < 0) {
    const t = -v / 5
    if (t < 0.5) return t < 0.25 ? '#bbf7d0' : '#4ade80'
    return t < 0.75 ? '#22c55e' : '#14532d'
  }
  return '#f3f4f6'
}

// 价格/时间轴格式化与 K线图骨架件统一收在 chart/kline（fmtPriceNum/monthTickConfig）

// K线 ECharts 配置：蜡烛图 + 成交量 + 主图叠加(MA/BOLL) + 副图指标(MACD/KDJ/RSI)
const klineOption = computed(() => {
  if (!kline.value || !kline.value.dates.length) return {}
  const k = kline.value
  // A股红涨绿跌；美股绿涨红跌（市场配色 token 见 lib/marketColors）
  const isUS = k.market === 'us'
  const { up: upColor, down: downColor, upText, downText } = chartPalette(k.market)

  const dates = k.dates
  const ohlcv = k.ohlcv
  const closes = ohlcv.map((o) => o[1])
  const lastClose = closes[closes.length - 1]!
  const lastUp = ohlcv.length > 1 ? lastClose >= ohlcv[ohlcv.length - 2]![1] : true

  const periodLabel = PERIOD_LABELS[k.period ?? klinePeriod.value] ?? '日线'
  const adjustLabel = k.kind === 'index' ? '指数' : (ADJUST_LABELS[k.adjust ?? klineAdjust.value] ?? '')

  // ---- 主图叠加与副图指标（由工具栏偏好驱动） ----
  const overlay = klineOverlay.value
  const sub = klineSub.value
  const ma5 = calcMA(closes, 5)
  const ma20 = calcMA(closes, 20)
  const ma60 = calcMA(closes, 60)
  const boll = overlay === 'boll' ? calcBOLL(closes) : null
  const macd = sub === 'macd' ? calcMACD(closes) : null
  const kdj = sub === 'kdj' ? calcKDJ(ohlcv) : null
  const rsi6 = sub === 'rsi' ? calcRSI(closes, 6) : null
  const rsi12 = sub === 'rsi' ? calcRSI(closes, 12) : null
  const rsi24 = sub === 'rsi' ? calcRSI(closes, 24) : null
  const hasSub = sub !== 'none'

  // 蜡烛宽度按数据密度分档（180根约6-10px，长周期压到2-4px）
  const nBars = dates.length
  const candleWidth = nBars <= 70 ? 9 : nBars <= 140 ? 7 : nBars <= 260 ? 4 : nBars <= 420 ? 3 : 2

  const legendData: string[] = ['日K']
  if (overlay === 'ma') legendData.push('MA5', 'MA20', 'MA60')
  if (overlay === 'boll') legendData.push('BOLL中轨', 'BOLL上轨', 'BOLL下轨')
  legendData.push('成交量')
  if (sub === 'macd') legendData.push('DIF', 'DEA', 'MACD')
  if (sub === 'kdj') legendData.push('K', 'D', 'J')
  if (sub === 'rsi') legendData.push('RSI6', 'RSI12', 'RSI24')

  const trendLine = { type: 'line', smooth: true, showSymbol: false, connectNulls: true }

  const series: any[] = [
    {
      name: '日K',
      type: 'candlestick',
      data: ohlcv,
      barWidth: candleWidth,
      barMinWidth: 1,
      itemStyle: candleItemStyle(k.market),
      // 最新价虚线 + 右侧价格标签（TradingView 式）
      markLine: {
        symbol: ['none', 'none'],
        silent: true,
        animation: false,
        lineStyle: { type: 'dashed', width: 1, color: lastUp ? upColor : downColor },
        label: {
          position: 'insideEndTop',
          formatter: () => fmtPriceNum(lastClose),
          color: lastUp ? upColor : downText,
          fontSize: 11,
        },
        data: [{ yAxis: lastClose }],
      },
    },
  ]
  if (overlay === 'ma') {
    series.push(
      { name: 'MA5', ...trendLine, data: ma5, lineStyle: { width: 1.2, color: '#f59e0b' } },
      { name: 'MA20', ...trendLine, data: ma20, lineStyle: { width: 1.2, color: '#667eea' } },
      { name: 'MA60', ...trendLine, data: ma60, lineStyle: { width: 1.2, color: '#10b981' } },
    )
  } else if (boll) {
    series.push(
      { name: 'BOLL中轨', ...trendLine, data: boll.mid, lineStyle: { width: 1.2, color: '#8b5cf6' } },
      { name: 'BOLL上轨', ...trendLine, data: boll.up, lineStyle: { width: 1, type: 'dashed', opacity: 0.7, color: '#8b5cf6' } },
      { name: 'BOLL下轨', ...trendLine, data: boll.low, lineStyle: { width: 1, type: 'dashed', opacity: 0.7, color: '#8b5cf6' } },
    )
  }
  series.push({
    name: '成交量',
    type: 'bar',
    xAxisIndex: 1,
    yAxisIndex: 1,
    data: k.volumes.map((v, i) => ({
      value: v,
      itemStyle: { color: ohlcv[i] && ohlcv[i][1] >= ohlcv[i][0] ? upColor : downColor },
    })),
  })
  // 副图指标系列挂在第三个窗格
  if (macd) {
    series.push(
      { name: 'DIF', ...trendLine, xAxisIndex: 2, yAxisIndex: 2, data: macd.dif, lineStyle: { width: 1, color: '#f59e0b' } },
      { name: 'DEA', ...trendLine, xAxisIndex: 2, yAxisIndex: 2, data: macd.dea, lineStyle: { width: 1, color: '#667eea' } },
      {
        name: 'MACD', type: 'bar', xAxisIndex: 2, yAxisIndex: 2,
        data: macd.hist.map((v) => ({ value: v, itemStyle: { color: v >= 0 ? upColor : downColor } })),
      },
    )
  } else if (kdj) {
    series.push(
      { name: 'K', ...trendLine, xAxisIndex: 2, yAxisIndex: 2, data: kdj.K, lineStyle: { width: 1, color: '#f59e0b' } },
      { name: 'D', ...trendLine, xAxisIndex: 2, yAxisIndex: 2, data: kdj.D, lineStyle: { width: 1, color: '#667eea' } },
      { name: 'J', ...trendLine, xAxisIndex: 2, yAxisIndex: 2, data: kdj.J, lineStyle: { width: 1, color: '#8b5cf6' } },
    )
  } else if (rsi6 && rsi12 && rsi24) {
    series.push(
      { name: 'RSI6', ...trendLine, xAxisIndex: 2, yAxisIndex: 2, data: rsi6, lineStyle: { width: 1, color: '#f59e0b' } },
      { name: 'RSI12', ...trendLine, xAxisIndex: 2, yAxisIndex: 2, data: rsi12, lineStyle: { width: 1, color: '#667eea' } },
      { name: 'RSI24', ...trendLine, xAxisIndex: 2, yAxisIndex: 2, data: rsi24, lineStyle: { width: 1, color: '#64748b' } },
    )
  }

  const monthTicks = monthTickConfig(dates)

  return {
    title: {
      text: `${k.name || k.code} ${isUS ? '(美股)' : '(A股)'}`,
      subtext: `${periodLabel}${adjustLabel ? ' · ' + adjustLabel : ''}`,
      left: 'center',
      top: 2,
      textStyle: { fontSize: 15, fontWeight: 600 },
      subtextStyle: { fontSize: 11, color: '#9ca3af' },
    },
    // 多窗格十字光标联动（骨架件见 chart/kline）
    axisPointer: linkedCrosshair(),
    tooltip: {
      trigger: 'axis',
      axisPointer: crosshairPointer(),
      // TradingView 式固定数值面板：tooltip 吸顶并水平钳制在图内，消除对蜡烛的遮挡
      position: (point: number[], _params: unknown, _dom: unknown, _rect: unknown, size: { contentSize: number[]; viewSize: number[] }) => {
        const w = size.contentSize[0] ?? 220
        const viewW = size.viewSize[0] ?? 600
        const x = Math.min(Math.max((point[0] ?? 0) - w / 2, 8), Math.max(8, viewW - w - 8))
        return [x, 8]
      },
      backgroundColor: 'rgba(255,255,255,0.97)',
      borderColor: '#e5e7eb',
      borderWidth: 1,
      textStyle: { color: '#1f2937', fontSize: 12 },
      formatter(params: any) {
        const arr: any[] = Array.isArray(params) ? params : [params]
        const idx = arr[0]?.dataIndex ?? 0
        const date = dates[idx] ?? ''
        const o = ohlcv[idx]
        if (!o) return date
        // 前收/涨跌口径统一走 chart/kline（首根回退为开盘价）
        const { prev, chgPct: chg } = chgVsPrevClose(ohlcv, idx)
        const amp = ((o[3] - o[2]) / prev) * 100
        const valColor = (v: number) => (v > 0 ? upText : v < 0 ? downText : 'inherit')
        const pctStr = (v: number) => `${v > 0 ? '+' : ''}${v.toFixed(2)}%`
        const pv = (label: string, v: number) =>
          `<span style="color:${valColor(v - prev)}">${label} ${fmtPriceNum(v)}</span>`
        const lines = [`<div style="font-weight:600;margin-bottom:4px">${date} · ${periodLabel}</div>`]
        lines.push(`${pv('开', o[0])} &nbsp; ${pv('高', o[3])}<br/>${pv('低', o[2])} &nbsp; ${pv('收', o[1])}`)
        lines.push(
          `<span style="color:${valColor(chg)}">涨跌 ${pctStr(chg)}</span> &nbsp; ` +
          `<span style="color:${valColor(chg)}">振幅 ${pctStr(amp)}</span>`,
        )
        if (overlay === 'ma') {
          const m5 = ma5[idx], m20 = ma20[idx], m60 = ma60[idx]
          const maLine: string[] = []
          if (m5 != null) maLine.push(`<span style="color:#f59e0b">MA5 ${m5.toFixed(2)}</span>`)
          if (m20 != null) maLine.push(`<span style="color:#667eea">MA20 ${m20.toFixed(2)}</span>`)
          if (m60 != null) maLine.push(`<span style="color:#10b981">MA60 ${m60.toFixed(2)}</span>`)
          if (maLine.length) lines.push(maLine.join(' &nbsp; '))
        } else if (boll) {
          const bm = boll.mid[idx], bu = boll.up[idx], bl = boll.low[idx]
          if (bu != null && bl != null) {
            lines.push(
              `<span style="color:#8b5cf6">UP ${bu!.toFixed(2)}</span> &nbsp; ` +
              `<span style="color:#8b5cf6">MB ${bm!.toFixed(2)}</span> &nbsp; ` +
              `<span style="color:#8b5cf6">DN ${bl!.toFixed(2)}</span>`,
            )
          }
        }
        if (macd) {
          const h = macd.hist[idx] ?? 0
          lines.push(
            `<span style="color:#f59e0b">DIF ${macd.dif[idx]?.toFixed(3)}</span> &nbsp; ` +
            `<span style="color:#667eea">DEA ${macd.dea[idx]?.toFixed(3)}</span> &nbsp; ` +
            `<span style="color:${h >= 0 ? upText : downText}">MACD ${h.toFixed(3)}</span>`,
          )
        } else if (kdj) {
          lines.push(
            `<span style="color:#f59e0b">K ${kdj.K[idx]}</span> &nbsp; ` +
            `<span style="color:#667eea">D ${kdj.D[idx]}</span> &nbsp; ` +
            `<span style="color:#8b5cf6">J ${kdj.J[idx]}</span>`,
          )
        } else if (sub === 'rsi') {
          const r6 = rsi6![idx], r12 = rsi12![idx], r24 = rsi24![idx]
          const rl: string[] = []
          if (r6 != null) rl.push(`<span style="color:#f59e0b">RSI6 ${r6}</span>`)
          if (r12 != null) rl.push(`<span style="color:#667eea">RSI12 ${r12}</span>`)
          if (r24 != null) rl.push(`<span style="color:#64748b">RSI24 ${r24}</span>`)
          if (rl.length) lines.push(rl.join(' &nbsp; '))
        }
        const vol = k.volumes[idx]
        if (vol != null) lines.push(`成交量 ${fmtVol(vol)}`)
        return lines.join('<br/>')
      },
    },
    legend: { data: legendData, top: 50, left: 'center', itemWidth: 14, itemHeight: 8, textStyle: { fontSize: 11 } },
    grid: hasSub
      ? [
          { left: '7%', right: '4%', top: 74, height: '44%' },
          { left: '7%', right: '4%', top: '64%', height: '11%' },
          { left: '7%', right: '4%', top: '77%', height: '11%' },
        ]
      : [
          { left: '7%', right: '4%', top: 74, height: '58%' },
          { left: '7%', right: '4%', top: '81%', height: '12%' },
        ],
    xAxis: [
      klineXAxis({ data: dates, labelShow: false }),
      klineXAxis({ data: dates, labelShow: !hasSub, ticks: monthTicks }),
      ...(hasSub ? [klineXAxis({ data: dates, labelShow: true, ticks: monthTicks })] : []),
    ],
    yAxis: [
      { scale: true, splitArea: { show: true }, axisLabel: { formatter: (v: number) => fmtPriceNum(v) } },
      { gridIndex: 1, splitNumber: 2, axisLabel: { show: false } },
      ...(hasSub
        ? [{ gridIndex: 2, scale: true, splitNumber: 2, splitArea: { show: false }, axisLabel: { show: true, fontSize: 10 } }]
        : []),
    ],
    dataZoom: klineDataZoom({
      xAxisIndex: hasSub ? [0, 1, 2] : [0, 1],
      start: 60,
      sliderTop: hasSub ? '89%' : '94%',
      preventDefaultMouseMove: true,
    }),
    series,
  }
})

const heatLabelColor = (chg: number): string => (Math.abs(chg) >= 2 ? '#fff' : '#1f2937')

// 热力图 ECharts 配置：面积=成交额、颜色=涨跌幅，全市场 90 行业按成交额取前 28
const heatmapOption = computed(() => {
  const sectors = sectorBoard.value?.sectors
  if (!sectors?.length) return {}
  const top = [...sectors].sort((a, b) => b.turnover - a.turnover).slice(0, 28)
  return {
    tooltip: {
      backgroundColor: 'rgba(255,255,255,0.97)',
      borderColor: '#e5e7eb',
      textStyle: { color: '#1f2937', fontSize: 12 },
      formatter(info: any) {
        const c = info.data as any
        return `${c.nameRaw}<br/>涨跌幅 ${c.chg > 0 ? '+' : ''}${c.chg.toFixed(2)}%<br/>成交额 ${c.value.toFixed(1)}亿 &nbsp; 领涨 ${c.leader || '-'}`
      },
    },
    series: [
      {
        type: 'treemap',
        roam: false,
        nodeClick: false,
        breadcrumb: { show: false },
        label: {
          show: true,
          formatter(param: any) {
            const c = param.data as any
            return `${c.nameRaw}\n${c.chg > 0 ? '+' : ''}${c.chg.toFixed(2)}%`
          },
          fontSize: 11,
          color: '#1f2937',
          // satureted cells are dark; per-label color override applied via itemStyle label
        },
        upperLabel: { show: false },
        itemStyle: { borderColor: '#fff', borderWidth: 1, gapWidth: 1 },
        data: top.map((s) => ({
          name: s.name,
          nameRaw: s.name,
          value: Math.max(1, s.turnover || 1),
          chg: s.chg_pct,
          leader: s.leader,
          label: { color: heatLabelColor(s.chg_pct) },
          itemStyle: { color: heatColor(s.chg_pct) },
        })),
      },
    ],
  }
})

// ===== 自选分布环图（Wealthfolio holdings 启发：市场/当日涨跌/行业 三维切换） =====
type AllocDim = 'market' | 'change' | 'sector'
const allocDim = ref<AllocDim>('market')

// 行业映射来自舆情板块的成分股列表（零新增后端成本；无匹配归入"其他"）
const sectorByCode = computed(() => {
  const map = new Map<string, string>()
  for (const s of sentiment.value?.sectors || []) {
    for (const st of s.stocks || []) map.set(st.code, s.name)
  }
  return map
})

function allocColor(name: string): string | undefined {
  // 涨跌分组沿用 A股涨跌 token（"当日涨跌"视图固定按 A股红涨绿跌语义展示）
  const zh = chartPalette('zh_a')
  const palette: Record<string, string> = {
    A股: '#667eea',
    美股: '#10b981',
    指数: '#8b5cf6',
    上涨: zh.up,
    平盘: NEUTRAL_HEX,
    下跌: zh.down,
    其他: '#cbd5e1',
  }
  return palette[name]
}

const allocationOption = computed(() => {
  const items = watchlistStore.items
  if (!items.length) return {}
  let entries: { name: string; value: number }[] = []
  if (allocDim.value === 'market') {
    const groups: Record<string, number> = {}
    for (const it of items) {
      const g = it.kind === 'index' ? '指数' : it.market === 'us' ? '美股' : 'A股'
      groups[g] = (groups[g] || 0) + 1
    }
    entries = Object.entries(groups).map(([name, value]) => ({ name, value }))
  } else if (allocDim.value === 'change') {
    const counts = { 上涨: 0, 平盘: 0, 下跌: 0 }
    for (const it of items) {
      const q = quoteOf(it.code, it.market, it.kind)
      if (!q) continue
      if (q.chgPct > 0) counts['上涨'] += 1
      else if (q.chgPct < 0) counts['下跌'] += 1
      else counts['平盘'] += 1
    }
    entries = Object.entries(counts)
      .map(([name, value]) => ({ name, value }))
      .filter((e) => e.value > 0)
  } else {
    const groups: Record<string, number> = {}
    for (const it of items) {
      if (it.kind === 'index') continue
      const g = sectorByCode.value.get(it.code) || '其他'
      groups[g] = (groups[g] || 0) + 1
    }
    entries = Object.entries(groups)
      .map(([name, value]) => ({ name, value }))
      .sort((a, b) => b.value - a.value)
      .slice(0, 8)
  }
  if (!entries.length) return {}
  return {
    tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
    legend: {
      bottom: 0,
      type: 'scroll',
      icon: 'circle',
      itemWidth: 10,
      itemHeight: 10,
      textStyle: { fontSize: 11 },
    },
    series: [
      {
        type: 'pie',
        radius: ['46%', '70%'],
        center: ['50%', '44%'],
        avoidLabelOverlap: true,
        itemStyle: { borderColor: '#fff', borderWidth: 1, borderRadius: 4 },
        label: { show: false },
        data: entries.map((e) => ({ ...e, itemStyle: { color: allocColor(e.name) } })),
      },
    ],
  }
})

const sectorFallbackList = computed(() => {
  const top = recommend.value?.top_sectors
  if (top?.length) return top.map((s) => ({ name: s.name, val: s.sentiment, label: `${s.sentiment}` }))
  const board = sectorBoard.value?.sectors
  if (board?.length) return board.slice(0, 6).map((s) => ({ name: s.name, val: Math.abs(s.chg_pct), label: `${s.chg_pct > 0 ? '+' : ''}${s.chg_pct.toFixed(2)}%` }))
  const senti = sentiment.value?.sectors
  if (senti?.length) return senti.slice(0, 6).map((s) => ({ name: s.name, val: s.sentiment, label: `${s.sentiment}` }))
  return [] as { name: string; val: number; label: string }[]
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
    <!-- 布局工具栏 -->
    <div class="layout-toolbar">
      <span class="layout-hint"><el-icon><Rank /></el-icon> 拖动卡片右上角手柄可调整顺序</span>
      <el-button size="small" text @click="replayTour">
        <el-icon><QuestionFilled /></el-icon> 新手引导
      </el-button>
      <el-button size="small" text @click="resetLayout">
        <el-icon><Refresh /></el-icon> 重置布局
      </el-button>
    </div>

    <!-- 可拖拽 widget 容器（按持久化顺序渲染） -->
    <div
      v-for="(w, index) in orderedWidgets"
      :key="w.id"
      class="widget"
      :class="{ dragging: draggingIndex === index }"
      draggable="true"
      @dragstart="onDragStart($event, index)"
      @dragend="onDragEnd"
      @dragover.prevent="onDragOver"
      @drop.prevent="onDrop(index)"
    >
      <!-- 拖拽手柄 -->
      <div class="widget-handle" :title="`${w.meta.title} · 拖动调整顺序`">
        <el-icon :size="14"><Rank /></el-icon>
      </div>

      <!-- quick：快捷入口 -->
      <template v-if="w.id === 'quick'">
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
      </template>

      <!-- indexes：大盘指数速览（点击卡片在主图查看对应指数） -->
      <template v-else-if="w.id === 'indexes'">
        <el-row :gutter="12" class="index-row">
          <el-col v-for="idx in INDEX_PRESETS" :key="idx.code" :xs="24" :sm="8">
            <div class="index-card" title="点击在主图查看该指数" @click="selectIndex(idx)">
              <span class="index-name">{{ idx.name }}</span>
              <MiniSparkline
                :values="quoteOf(idx.code, idx.market, idx.kind)?.closes ?? []"
                :width="56"
                :height="20"
                :color="chgSparkColor(idx.market, quoteOf(idx.code, idx.market, idx.kind)?.chgPct)"
              />
              <template v-if="quoteOf(idx.code, idx.market, idx.kind)">
                <span class="index-close" :class="flashOf(idx.code, idx.market, idx.kind)">
                  <AnimNumber :value="quoteOf(idx.code, idx.market, idx.kind)!.close" />
                </span>
                <span
                  class="delta-badge"
                  :style="deltaBadgeStyle(idx.market, quoteOf(idx.code, idx.market, idx.kind)!.chgPct)"
                >
                  {{ quoteOf(idx.code, idx.market, idx.kind)!.chgPct >= 0 ? '▲' : '▼' }}
                  {{ quoteOf(idx.code, idx.market, idx.kind)!.chgPct >= 0 ? '+' : '' }}{{ quoteOf(idx.code, idx.market, idx.kind)!.chgPct.toFixed(2) }}%
                </span>
              </template>
              <el-skeleton v-else animated style="width: 120px; flex: 1">
                <template #template>
                  <el-skeleton-item variant="text" style="width: 70px; height: 14px" />
                  <el-skeleton-item variant="text" style="width: 48px; height: 14px; margin-left: 8px" />
                </template>
              </el-skeleton>
            </div>
          </el-col>
        </el-row>
      </template>

      <!-- breadth：市场宽度风向标 -->
      <template v-else-if="w.id === 'breadth'">
        <el-card shadow="never" class="info-card breadth-card">
          <template #header>
            <div class="card-head-row">
              <span class="section-title" style="margin: 0; border: none; padding: 0">
                <el-icon><Odometer /></el-icon> 市场宽度
              </span>
              <small v-if="breadth" class="card-updated">{{ breadth.updated_at }}</small>
            </div>
          </template>
          <div v-if="loadingBreadth" class="info-body" style="min-height: 110px">
            <el-skeleton animated :rows="3" />
          </div>
          <template v-else-if="breadth">
            <div class="breadth-stats">
              <div class="breadth-stat">
                <span class="b-label">上涨</span>
                <strong class="b-val" style="color: var(--danger)">{{ breadth.up }}</strong>
              </div>
              <div class="breadth-stat">
                <span class="b-label">下跌</span>
                <strong class="b-val" style="color: var(--success)">{{ breadth.down }}</strong>
              </div>
              <div class="breadth-stat">
                <span class="b-label">涨停</span>
                <strong class="b-val" style="color: #b91c1c">{{ breadth.limit_up ?? '—' }}</strong>
              </div>
              <div class="breadth-stat">
                <span class="b-label">跌停</span>
                <strong class="b-val" style="color: #14532d">{{ breadth.limit_down ?? '—' }}</strong>
              </div>
              <div class="breadth-stat">
                <span class="b-label">上涨板块</span>
                <strong class="b-val">{{ breadth.rising_sectors }}/{{ breadth.total_sectors }}</strong>
              </div>
            </div>
            <div class="breadth-bar">
              <div class="breadth-seg up" :style="{ width: breadthUpPct + '%' }"></div>
              <div class="breadth-seg down" :style="{ width: (100 - breadthUpPct) + '%' }"></div>
            </div>
            <div class="breadth-foot">
              <span>领涨板块 <strong :style="{ color: breadth.top_sector.chg_pct > 0 ? 'var(--danger)' : 'var(--success)' }">{{ breadth.top_sector.name }} {{ breadth.top_sector.chg_pct > 0 ? '+' : '' }}{{ breadth.top_sector.chg_pct.toFixed(2) }}%</strong></span>
              <span class="b-meta">上涨占比 {{ breadthUpPct }}%</span>
            </div>
          </template>
          <el-empty v-else :image-size="60" description="暂无市场宽度数据" />
        </el-card>
      </template>

      <!-- kline：K线主图 + 右栏自选/最近回测 -->
      <template v-else-if="w.id === 'kline'">
        <el-row :gutter="16">
          <el-col :xs="24" :md="16">
            <el-card shadow="never" class="kline-card">
              <template #header>
                <div class="kline-header">
                  <span class="section-title" style="margin: 0; border: none; padding: 0">
                    <el-icon><CandlestickChart /></el-icon> 行情看板
                  </span>
                  <div class="kline-toolbar">
                    <el-radio-group v-model="klinePeriod" size="small">
                      <el-radio-button value="day">日</el-radio-button>
                      <el-radio-button value="week">周</el-radio-button>
                      <el-radio-button value="month">月</el-radio-button>
                    </el-radio-group>
                    <el-select
                      v-model="klineAdjust"
                      size="small"
                      style="width: 92px"
                      title="复权方式（指数无复权概念）"
                      :disabled="isIndexTarget"
                    >
                      <el-option label="前复权" value="qfq" />
                      <el-option label="后复权" value="hfq" />
                      <el-option label="不复权" value="nfq" />
                    </el-select>
                    <el-select v-model="klineOverlay" size="small" style="width: 96px" title="主图叠加指标">
                      <el-option label="主图：MA" value="ma" />
                      <el-option label="主图：BOLL" value="boll" />
                      <el-option label="主图：无" value="none" />
                    </el-select>
                    <el-select v-model="klineSub" size="small" style="width: 106px" title="副图指标">
                      <el-option label="副图：MACD" value="macd" />
                      <el-option label="副图：KDJ" value="kdj" />
                      <el-option label="副图：RSI" value="rsi" />
                      <el-option label="副图：无" value="none" />
                    </el-select>
                    <el-button size="small" text @click="resetKlineZoom">
                      <el-icon><Refresh /></el-icon> 重置缩放
                    </el-button>
                    <el-select
                      v-model="activeKey"
                      placeholder="选择标的"
                      style="width: 180px"
                      filterable
                    >
                      <el-option
                        v-for="t in watchlistStore.items"
                        :key="targetKey(t.code, t.market, t.kind)"
                        :label="`${t.name} (${t.code})`"
                        :value="targetKey(t.code, t.market, t.kind)"
                      />
                    </el-select>
                  </div>
                </div>
              </template>
              <div class="kline-body">
                <el-skeleton v-if="loadingKline" animated :rows="5" style="padding: 16px" />
                <template v-else>
                  <v-chart
                    ref="klineChartRef"
                    v-if="kline && kline.dates.length"
                    class="kline-chart"
                    :option="klineOption"
                    :update-options="{ notMerge: true }"
                    autoresize
                  />
                  <el-empty v-else description="暂无K线数据" />
                </template>
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
                  ref="newCodeInput"
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
                  :key="targetKey(item.code, item.market, item.kind)"
                  class="watch-item"
                  :class="{ active: activeKey === targetKey(item.code, item.market, item.kind) }"
                  @click="activeKey = targetKey(item.code, item.market, item.kind)"
                >
                  <div class="watch-name">
                    <span class="watch-title">{{ item.name }}</span>
                    <code class="watch-code">{{ item.code }}</code>
                  </div>
                  <MiniSparkline
                    v-if="(quoteOf(item.code, item.market, item.kind)?.closes?.length ?? 0) > 2"
                    :values="quoteOf(item.code, item.market, item.kind)?.closes ?? []"
                    :width="60"
                    :height="20"
                    :color="sparkColor(item)"
                  />
                  <template v-if="quoteOf(item.code, item.market, item.kind)">
                    <span class="watch-close" :class="flashOf(item.code, item.market, item.kind)">
                      <AnimNumber :value="quoteOf(item.code, item.market, item.kind)!.close" />
                    </span>
                    <span
                      class="delta-badge delta-badge-sm"
                      :style="deltaBadgeStyle(item.market, quoteOf(item.code, item.market, item.kind)!.chgPct)"
                    >
                      {{ quoteOf(item.code, item.market, item.kind)!.chgPct >= 0 ? '+' : '' }}{{ quoteOf(item.code, item.market, item.kind)!.chgPct.toFixed(2) }}%
                    </span>
                  </template>
                  <el-skeleton v-else animated style="width: 90px">
                    <template #template>
                      <el-skeleton-item variant="text" style="width: 40px; height: 12px" />
                    </template>
                  </el-skeleton>
                  <el-button
                    class="watch-del"
                    text
                    circle
                    size="small"
                    title="移除自选"
                    @click.stop="removeWatch(item.code, item.market, item.kind)"
                  >
                    <el-icon :size="14"><Close /></el-icon>
                  </el-button>
                </div>
                <el-empty
                  v-if="!watchlistStore.items.length"
                  :image-size="60"
                  description="暂无自选"
                >
                  <el-button type="primary" size="small" @click="focusWatchInput">输入代码添加</el-button>
                </el-empty>
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
                >
                  <el-button type="primary" size="small" @click="router.push('/backtest')">去运行回测</el-button>
                </el-empty>
              </div>
            </el-card>
          </el-col>
        </el-row>
      </template>

      <!-- heatmap：行业热力图 -->
      <template v-else-if="w.id === 'heatmap'">
        <el-card shadow="never" class="info-card heatmap-card">
          <template #header>
            <div class="card-head-row">
              <span class="section-title" style="margin: 0; border: none; padding: 0">
                <el-icon><Grid /></el-icon> 行业热力图
              </span>
              <span class="card-head-right">
                <small v-if="sectorBoard" class="card-updated">{{ sectorBoard.updated_at }}</small>
                <router-link to="/sentiment" class="card-more">板块情绪 →</router-link>
              </span>
            </div>
          </template>
          <div v-if="loadingSectors" style="min-height: 320px; padding: 16px">
            <el-skeleton animated :rows="6" />
          </div>
          <template v-else-if="sectorBoard?.sectors?.length">
            <v-chart class="heatmap-chart" :option="heatmapOption" autoresize />
            <div class="heatmap-legend">
              <span class="hl" style="background:#14532d"></span> 跌 &gt;3%
              <span class="hl" style="background:#4ade80"></span> 跌
              <span class="hl" style="background:#f3f4f6;border:1px solid #e5e7eb"></span> 平
              <span class="hl" style="background:#f87171"></span> 涨
              <span class="hl" style="background:#991b1b"></span> 涨 &gt;3%
              <span class="hl-meta">面积=成交额 · 颜色=涨跌幅</span>
            </div>
          </template>
          <el-empty v-else :image-size="60" description="暂无板块数据" />
        </el-card>
      </template>

      <!-- sectors：热门板块 -->
      <template v-else-if="w.id === 'sectors'">
        <el-card shadow="never" class="info-card">
          <template #header>
            <span class="section-title" style="margin: 0; border: none; padding: 0">
              <el-icon><Sunrise /></el-icon> 热门板块 TOP
            </span>
          </template>
          <div class="info-body">
            <div
              v-for="s in sectorFallbackList"
              :key="s.name"
              class="sector-row"
            >
              <div class="sector-row-head">
                <span class="sector-name">{{ s.name }}</span>
                <span class="sector-score" :style="{ color: sectorColor(s.val) }">{{ s.label }}</span>
              </div>
              <el-progress
                :percentage="Math.min(100, Math.abs(s.val))"
                :color="sectorColor(s.val)"
                :stroke-width="6"
                :show-text="false"
              />
            </div>
            <el-empty v-if="!sectorFallbackList.length" :image-size="60" description="暂无板块数据" />
          </div>
        </el-card>
      </template>

      <!-- news：当日舆情 -->
      <template v-else-if="w.id === 'news'">
        <el-card shadow="never" class="info-card">
          <template #header>
            <div class="card-head-row">
              <span class="section-title" style="margin: 0; border: none; padding: 0">
                <el-icon><ChatDotRound /></el-icon> 当日舆情
              </span>
              <router-link to="/sentiment" class="card-more">舆情分析 →</router-link>
            </div>
          </template>
          <div class="info-body news-body">
            <div v-if="newsSources.length > 2" class="news-filter">
              <el-radio-group v-model="newsSourceFilter" size="small">
                <el-radio-button v-for="s in newsSources" :key="s" :value="s">{{ s }}</el-radio-button>
              </el-radio-group>
            </div>
            <div v-for="(n, i) in filteredNews" :key="n.id || i" class="news-item">
              <div class="news-source">
                <span class="news-badge" :style="{ background: newsSourceColor(n.source) }">{{ cleanNewsSource(n.source) }}</span>
                <span v-if="n.date" class="news-date">{{ n.date }}</span>
              </div>
              <a v-if="n.url" :href="n.url" target="_blank" rel="noopener" class="news-title">{{ n.title }}</a>
              <div v-else class="news-title">{{ n.title }}</div>
            </div>
            <el-empty v-if="!sentiment?.news_list?.length" :image-size="60" description="暂无舆情数据" />
          </div>
        </el-card>
      </template>

      <!-- recommend：个股推荐 -->
      <template v-else-if="w.id === 'recommend'">
        <el-card shadow="never" class="info-card">
          <template #header>
            <span class="section-title" style="margin: 0; border: none; padding: 0">
              <el-icon><Star /></el-icon> 个股推荐
            </span>
          </template>
          <div class="info-body">
            <div
              v-for="r in (recommend?.recommendations || []).slice(0, 6)"
              :key="r.code"
              class="rec-item"
              :title="`${r.name} · 点击在主图查看`"
              @click="openRecInChart(r)"
            >
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
      </template>

      <!-- allocation：自选分布（市场/当日涨跌/行业三维环图） -->
      <template v-else-if="w.id === 'allocation'">
        <el-card shadow="never" class="info-card allocation-card">
          <template #header>
            <div class="card-head-row">
              <span class="section-title" style="margin: 0; border: none; padding: 0">
                <el-icon><PieChart /></el-icon> 自选分布
              </span>
              <el-radio-group v-model="allocDim" size="small">
                <el-radio-button value="market">市场</el-radio-button>
                <el-radio-button value="change">当日涨跌</el-radio-button>
                <el-radio-button value="sector">行业</el-radio-button>
              </el-radio-group>
            </div>
          </template>
          <v-chart
            v-if="watchlistStore.items.length && Object.keys(allocationOption).length"
            class="allocation-chart"
            :option="allocationOption"
            autoresize
          />
          <el-empty v-else :image-size="60" description="添加自选后查看分布" />
        </el-card>
      </template>

      <!-- srchealth：数据源心跳（近 7 次取数成败，排查 akshare/网络抖动） -->
      <template v-else-if="w.id === 'srchealth'">
        <el-card shadow="never" class="info-card health-card">
          <template #header>
            <div class="card-head-row">
              <span class="section-title" style="margin: 0; border: none; padding: 0">
                <el-icon><Monitor /></el-icon> 数据源心跳
              </span>
              <small class="card-updated">各数据源近 7 次取数</small>
            </div>
          </template>
          <div class="health-body">
            <div v-for="s in HEALTH_SOURCES" :key="s.key" class="health-row">
              <span class="health-name">{{ s.label }}</span>
              <span class="health-beats">
                <span
                  v-for="(b, i) in beatsOf(s.key)"
                  :key="i"
                  class="health-beat"
                  :class="b == null ? 'empty' : b.ok ? 'ok' : 'bad'"
                  :title="beatTitle(b)"
                ></span>
              </span>
              <small class="health-last">{{ lastBeatText(s.key) }}</small>
            </div>
            <div v-if="!hasHealthData" class="health-hint">
              暂无取数记录：查询行情/回测后自动生成（仅统计本进程，重启清零）
            </div>
          </div>
        </el-card>
      </template>
    </div>

    <!-- 情绪日历 -->
    <div class="widget">
      <el-card shadow="never" class="info-card">
        <template #header>
          <span class="section-title" style="margin: 0; border: none; padding: 0">
            <el-icon><Calendar /></el-icon> 情绪日历
          </span>
        </template>
        <SentimentCalendar :calendar="calendar" />
      </el-card>
    </div>
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

/* 布局工具栏 */
.layout-toolbar {
  display: flex;
  justify-content: flex-end;
  align-items: center;
  gap: 12px;
}
.layout-hint {
  font-size: 0.78rem;
  color: var(--text-muted);
  display: flex;
  align-items: center;
  gap: 4px;
}

/* 可拖拽 widget 容器 */
.widget {
  position: relative;
  width: 100%;
}
.widget.dragging {
  opacity: 0.5;
  cursor: grabbing;
}
.widget-handle {
  position: absolute;
  top: 8px;
  right: 12px;
  z-index: 10;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 26px;
  height: 26px;
  border-radius: 6px;
  color: var(--text-muted);
  background: var(--surface);
  border: 1px solid var(--border);
  cursor: grab;
  opacity: 0;
  transition: opacity 0.15s, color 0.15s;
}
.widget:hover .widget-handle {
  opacity: 1;
}
.widget-handle:hover {
  color: var(--brand-start);
  border-color: var(--brand-start);
}
.widget-handle:active {
  cursor: grabbing;
}
@media (pointer: coarse) {
  .widget-handle {
    opacity: 1;
  }
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
  align-items: center;
  gap: 10px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 10px 16px;
  margin-bottom: 12px;
  min-height: 48px;
  cursor: pointer;
  transition: border-color 0.15s, box-shadow 0.15s;
}
.index-card:hover {
  border-color: var(--brand-start);
  box-shadow: var(--shadow);
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
.delta-badge {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  font-size: 0.82rem;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  padding: 2px 8px;
  border-radius: 999px;
  line-height: 1.4;
}
.delta-badge-sm {
  font-size: 0.76rem;
  padding: 1px 6px;
}
.card-head-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.card-updated {
  color: var(--text-muted);
  font-size: 0.72rem;
}

/* 市场宽度风向标 */
.breadth-card :deep(.el-card__body) { padding-top: 12px; }
.breadth-stats {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 12px;
}
.breadth-stat {
  flex: 1;
  min-width: 72px;
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 8px 10px;
  text-align: center;
}
.b-label { display: block; font-size: 0.72rem; color: var(--text-muted); margin-bottom: 2px; }
.b-val { font-size: 1.15rem; font-variant-numeric: tabular-nums; }
.breadth-bar {
  display: flex;
  height: 10px;
  border-radius: 999px;
  overflow: hidden;
  background: var(--border);
  margin-bottom: 10px;
}
.breadth-seg.up { background: var(--danger); }
.breadth-seg.down { background: var(--success); }
.breadth-foot {
  display: flex;
  justify-content: space-between;
  font-size: 0.82rem;
  color: var(--text-muted);
}
.b-meta { font-variant-numeric: tabular-nums; }

/* 热力图 */
.heatmap-card :deep(.el-card__body) { padding-top: 8px; }
.heatmap-chart { height: 360px; width: 100%; }
.heatmap-legend {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  font-size: 0.72rem;
  color: var(--text-muted);
  margin-top: 8px;
}
.heatmap-legend .hl { width: 14px; height: 10px; border-radius: 3px; display: inline-block; }
.hl-meta { margin-left: auto; }

/* K线主图 */
.kline-card {
  border-radius: var(--radius);
}
.kline-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}
.kline-toolbar {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}
.kline-body {
  min-height: 520px;
}
.kline-chart {
  height: 520px;
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

/* 卡片头右侧：更新时间 + 下钻入口 */
.card-head-right {
  display: flex;
  align-items: center;
  gap: 8px;
}
.card-more {
  font-size: 0.75rem;
  color: var(--brand-start);
  text-decoration: none;
  font-weight: 500;
}
.card-more:hover {
  text-decoration: underline;
}

/* 推荐行点击下钻 */
.rec-item {
  cursor: pointer;
  border-radius: 8px;
  padding: 2px 4px;
  margin-left: -4px;
  transition: background 0.12s;
}
.rec-item:hover {
  background: var(--bg);
}

/* 行情刷新闪烁（方向由 flashMap 决定，A股红涨绿跌） */
.up {
  animation: flashUp 0.9s ease-out;
}
.down {
  animation: flashDown 0.9s ease-out;
}
@keyframes flashUp {
  0% {
    color: var(--danger);
    text-shadow: 0 0 8px rgba(239, 35, 42, 0.45);
  }
  100% {
    text-shadow: none;
  }
}
@keyframes flashDown {
  0% {
    color: var(--success);
    text-shadow: 0 0 8px rgba(20, 178, 67, 0.45);
  }
  100% {
    text-shadow: none;
  }
}

/* 自选分布环图 */
.allocation-chart {
  height: 260px;
  width: 100%;
}

/* 快讯流：来源过滤 + 徽标 */
.news-filter {
  margin-bottom: 4px;
}
.news-badge {
  display: inline-block;
  font-size: 0.68rem;
  color: #fff;
  border-radius: 4px;
  padding: 0 6px;
  line-height: 16px;
}

/* 数据源心跳条（beat bar） */
.health-body {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.health-row {
  display: flex;
  align-items: center;
  gap: 10px;
}
.health-name {
  width: 68px;
  font-size: 0.8rem;
  font-weight: 600;
  color: var(--text-muted);
}
.health-beats {
  display: flex;
  gap: 3px;
  flex: 1;
}
.health-beat {
  width: 18px;
  height: 10px;
  border-radius: 2px;
}
.health-beat.ok {
  background: #22c55e;
}
.health-beat.bad {
  background: #ef4444;
}
.health-beat.empty {
  background: var(--border);
}
.health-last {
  width: 76px;
  text-align: right;
  color: var(--text-muted);
  font-size: 0.72rem;
  font-variant-numeric: tabular-nums;
}
.health-hint {
  color: var(--text-muted);
  font-size: 0.75rem;
}
</style>
