<script setup lang="ts">
/**
 * MarketView —— 行情终端独立页（/market）：左栏标的列表（指数预设 ∪ 自选，可搜索/添加），
 * 右侧大字报价头 + 多周期 K 线（指数与个股同页）。
 *
 * 复用而非重造（AGENTS：chart/kline.ts 是蜡烛图骨架唯一实现，HomeView/BacktestView 共享）：
 * - 蜡烛图尺寸/配色/轴/十字光标/dataZoom/前收涨跌口径全部来自 chart/kline.ts，
 *   指标序列来自 lib/indicators.ts，涨跌色一律经 lib/marketColors（DOM 走 CSS 变量、ECharts 走 hex）；
 * - 图内文案（周期/复权/系列名/tooltip 字段）复用 home.kline.*，指数名复用 home.index.*——
 *   同一张图的同一批标签只翻译一次；本页自有文案在 locales/market.ts。
 *
 * 数据面：GET /api/kline（tail 模式走 quote_cache SWR，毫秒级回缓存 + 后台刷新）。
 * 范围外：分钟线/分时/五档（后端无对应 API，故不留入口）。
 */
import { computed, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { klineApi } from '@/api'
import type { KlineData, Market } from '@/api/types'
import type { KlineAdjust, KlinePeriod } from '@/stores/klinePrefs'
import { useWatchlistStore, targetKey, watchDisplayName } from '@/stores/watchlist'
import { chartPalette, deltaColor } from '@/lib/marketColors'
import { chartTheme } from '@/lib/chartTheme'
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
import { calcMA } from '@/lib/indicators'
import { fmtBigNum } from '@/lib/format'
import { t } from '@/locales'
import { usePolling } from '@/composables/usePolling'
import { VChart } from '@/composables/useECharts'
import AnimNumber from '@/components/AnimNumber.vue'

const watchlistStore = useWatchlistStore()
const th = chartTheme()

// ===== 指数预设（与 HomeView 的 INDEX_PRESETS 同源五条；000001 二义性必须带 kind） =====
const INDEX_PRESETS: { code: string; market: Market; nameKey: string; kind: 'index' }[] = [
  { code: '000001', market: 'zh_a', nameKey: 'home.index.sse', kind: 'index' },
  { code: '000300', market: 'zh_a', nameKey: 'home.index.csi300', kind: 'index' },
  { code: '399001', market: 'zh_a', nameKey: 'home.index.szse', kind: 'index' },
  { code: 'SP500', market: 'us', nameKey: 'home.index.sp500', kind: 'index' },
  { code: 'NASDAQ', market: 'us', nameKey: 'home.index.nasdaq', kind: 'index' },
]

/** 列表行：身份只用 code/market/kind（key 即 targetKey），name 仅用于展示 */
interface SymbolRow {
  key: string
  code: string
  market: Market
  kind?: 'index'
  name: string
}

// ===== 页面状态 =====
const market = ref<Market>('zh_a')
const keyword = ref('')
const activeKey = ref('')
const period = ref<KlinePeriod>('day')
/** 复权默认前复权（与首页 K 线默认一致）；指数无复权概念，选择器禁用 */
const adjust = ref<KlineAdjust>('qfq')
const adding = ref(false)

// ===== 列表（指数预设 ∪ 自选，按 targetKey 去重：预设指数不重复出现在自选分组） =====
const presetRows = computed<SymbolRow[]>(() =>
  INDEX_PRESETS.filter((p) => p.market === market.value).map((p) => ({
    key: targetKey(p.code, p.market, p.kind),
    code: p.code,
    market: p.market,
    kind: p.kind,
    name: t(p.nameKey),
  })),
)

const watchRows = computed<SymbolRow[]>(() => {
  const taken = new Set(presetRows.value.map((r) => r.key))
  return watchlistStore.items
    .filter((it) => it.market === market.value && !taken.has(targetKey(it.code, it.market, it.kind)))
    .map((it) => ({
      key: targetKey(it.code, it.market, it.kind),
      code: it.code,
      market: it.market,
      kind: it.kind,
      name: watchDisplayName(it),
    }))
})

const rows = computed<SymbolRow[]>(() => [...presetRows.value, ...watchRows.value])

function matches(row: SymbolRow, kw: string): boolean {
  return row.code.toLowerCase().includes(kw) || row.name.toLowerCase().includes(kw)
}
const kw = computed(() => keyword.value.trim().toLowerCase())
const matchedPresets = computed(() => (kw.value ? presetRows.value.filter((r) => matches(r, kw.value)) : presetRows.value))
const matchedWatch = computed(() => (kw.value ? watchRows.value.filter((r) => matches(r, kw.value)) : watchRows.value))
/** 渲染分组（空组不占位；行渲染只有一份，见模板） */
const groups = computed(() =>
  [
    { key: 'indexes', label: t('market.groupIndexes'), rows: matchedPresets.value },
    { key: 'watchlist', label: t('market.groupWatchlist'), rows: matchedWatch.value },
  ].filter((g) => g.rows.length),
)
const totalMatches = computed(() => matchedPresets.value.length + matchedWatch.value.length)

/** 搜索词像代码吗（A股 6 位数字 / 美股字母代码）——像才给「添加并查看」入口 */
function looksLikeCode(q: string, m: Market): boolean {
  const s = q.trim()
  if (!s) return false
  return m === 'zh_a' ? /^\d{6}$/.test(s) : /^[A-Za-z][A-Za-z.\-]{0,9}$/.test(s)
}
const canAdd = computed(() => totalMatches.value === 0 && looksLikeCode(keyword.value, market.value))

const activeTarget = computed<SymbolRow | null>(
  () => rows.value.find((r) => r.key === activeKey.value) ?? null,
)
/** 是否指数标的：指数无复权概念（复权选择器禁用，图表副标题走 home.kline.indexAdjust） */
const isIndexTarget = computed(() => activeTarget.value?.kind === 'index')

// ===== 行情（列表价 + 大报价头；30 根日线一次取齐最新价/涨跌） =====
interface Quote {
  close: number
  /** 前收（涨跌额/涨跌幅口径，与首页自选一致） */
  prevClose: number
  chg: number
  chgPct: number
}
const quotes = ref<Record<string, Quote>>({})

function quoteOf(key: string): Quote | undefined {
  return quotes.value[key]
}
const closeOf = (key: string): number => quotes.value[key]?.close ?? 0
const chgPctOf = (key: string): number => quotes.value[key]?.chgPct ?? 0
const activeQuote = computed(() => quoteOf(activeKey.value))

async function loadQuote(row: SymbolRow) {
  try {
    // 复权口径与 K 线工具栏一致（指数由后端强制不复权）：大报价头/列表价与图上最后一根
    // K 线同源，避免首页自选常用的「空 adjust（A股=hfq）」与本页 qfq 图产生量级差
    const d = await klineApi.get(row.code, row.market, 30, 'day', adjust.value, row.kind ?? '')
    if (!d.ohlcv.length) return
    const closes = d.ohlcv.map((o) => o[1])
    const close = closes[closes.length - 1] ?? 0
    const prev = closes.length > 1 ? closes[closes.length - 2]! : close
    quotes.value[row.key] = {
      close,
      prevClose: prev,
      chg: close - prev,
      chgPct: prev ? (close / prev - 1) * 100 : 0,
    }
  } catch {
    // 单只行情失败静默降级（不阻塞页面；下一轮轮询会补）
  }
}

function loadQuotes() {
  rows.value.forEach((row) => void loadQuote(row))
}

// 行情 60s 轮询（SWR：后端 quote_cache 只在该 TTL 窗口真实出网一次）
usePolling(loadQuotes, { intervalMs: 60_000 })

// ===== K 线主图 =====
const kline = ref<KlineData | null>(null)
const loadingKline = ref(false)
const chartRef = ref<InstanceType<typeof VChart> | null>(null)

async function loadKline() {
  const target = activeTarget.value
  if (!target) return
  loadingKline.value = true
  try {
    kline.value = await klineApi.get(
      target.code,
      target.market,
      180,
      period.value,
      adjust.value,
      target.kind === 'index' ? 'index' : '',
    )
  } catch (e) {
    ElMessage.warning(t('home.kline.loadFailed') + (e as Error).message)
    kline.value = null
  } finally {
    loadingKline.value = false
  }
}

// 可选项变化（切市场/增删自选/新增标的）→ 校正选中项并补拉行情
const rowsSignature = computed(() => rows.value.map((r) => r.key).join(','))
watch(
  rowsSignature,
  () => {
    const keys = rows.value.map((r) => r.key)
    if (!keys.includes(activeKey.value)) activeKey.value = keys[0] ?? ''
    loadQuotes()
  },
  { immediate: true },
)
// 标的/周期/复权切换 → 重拉 K 线
watch([activeKey, period, adjust], () => void loadKline(), { immediate: true })
// 复权切换 → 列表价/大报价头跟随同一口径重拉（图与价始终一致）
watch(adjust, () => loadQuotes())
// 切市场时清空搜索词（上一市场的关键词会让新市场列表看起来是空的）
watch(market, () => {
  keyword.value = ''
})

function selectRow(key: string) {
  activeKey.value = key
}

/** 搜索结果为空且输入像代码：拉一次行情解析名称 → 加入自选并选中 */
async function addAndView() {
  const code = keyword.value.trim()
  if (!code || adding.value) return
  adding.value = true
  try {
    const d = await klineApi.get(code, market.value, 30)
    if (!d.ohlcv.length) throw new Error(t('common.noData'))
    const name = d.name || code
    activeKey.value = watchlistStore.ensureTracked(code, market.value, name)
    keyword.value = ''
    ElMessage.success(t('market.addDone', { name }))
  } catch (e) {
    ElMessage.error(t('market.addFailed') + (e as Error).message)
  } finally {
    adding.value = false
  }
}

/** 图表重置缩放：回到与首页一致的初始窗口（近端 40%），两个 dataZoom（inside + slider）各重置一次 */
function resetZoom() {
  const inst = (
    chartRef.value as unknown as {
      chart?: { dispatchAction?: (o: Record<string, unknown>) => void }
    }
  )?.chart
  try {
    if (inst?.dispatchAction) {
      for (let i = 0; i < 2; i++) {
        inst.dispatchAction({ type: 'dataZoom', dataZoomIndex: i, start: 60, end: 100 })
      }
    }
  } catch {
    /* 图表未就绪时忽略 */
  }
}

// ===== 展示助手（符号无色差语义，配色一律走 lib/marketColors） =====
const deltaArrow = (v: number): string => (v > 0 ? '▲' : v < 0 ? '▼' : '●')
const signPct = (v: number): string => `${v > 0 ? '+' : ''}${v.toFixed(2)}%`
const signNum = (v: number): string => `${v > 0 ? '+' : ''}${fmtPriceNum(v)}`
const priceDecimals = (v: number): number => (Math.abs(v) >= 1000 ? 0 : 2)

// ===== K 线 option（蜡烛 + MA + 成交量两窗格；骨架件全部来自 chart/kline） =====
const chartOption = computed(() => {
  const k = kline.value
  if (!k || !k.dates.length) return {}
  // A股红涨绿跌 / 美股绿涨红跌（用户全局偏好自动生效）
  const { up: upColor, down: downColor, upText, downText } = chartPalette(k.market)

  const dates = k.dates
  const ohlcv = k.ohlcv
  const closes = ohlcv.map((o) => o[1])
  const lastClose = closes[closes.length - 1]!
  const lastUp = ohlcv.length > 1 ? lastClose >= ohlcv[ohlcv.length - 2]![1] : true

  // 副标题：周期 + 复权（index 走「指数」；/api/kline 总返回 period/adjust，缺省回退本地工具栏值）
  const periodLabel = t(`home.kline.period.${k.period ?? period.value}`)
  const adjustLabel =
    k.kind === 'index'
      ? t('home.kline.indexAdjust')
      : t(`home.kline.adjust.${k.adjust ?? adjust.value}`)

  const ma5 = calcMA(closes, 5)
  const ma20 = calcMA(closes, 20)
  const ma60 = calcMA(closes, 60)
  const monthTicks = monthTickConfig(dates)

  // 蜡烛宽度按数据密度分档（与首页看板同口径）
  const nBars = dates.length
  const candleWidth = nBars <= 70 ? 9 : nBars <= 140 ? 7 : nBars <= 260 ? 4 : nBars <= 420 ? 3 : 2

  const trendLine = { type: 'line', smooth: true, showSymbol: false, connectNulls: true }
  const maSeries = (name: string, data: (number | null)[], color: string) => ({
    name,
    ...trendLine,
    data,
    lineStyle: { width: 1.2, color },
  })

  const series: any[] = [
    {
      name: t('home.kline.series.dayK'),
      type: 'candlestick',
      data: ohlcv,
      barWidth: candleWidth,
      barMinWidth: 1,
      itemStyle: candleItemStyle(k.market),
      // 最新价虚线 + 右侧价格标签（TradingView 式，与首页看板一致）
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
    maSeries('MA5', ma5, '#f59e0b'),
    maSeries('MA20', ma20, '#667eea'),
    maSeries('MA60', ma60, '#10b981'),
    {
      name: t('home.kline.series.volume'),
      type: 'bar',
      xAxisIndex: 1,
      yAxisIndex: 1,
      data: k.volumes.map((v, i) => ({
        value: v,
        itemStyle: { color: ohlcv[i] && ohlcv[i]![1] >= ohlcv[i]![0] ? upColor : downColor },
      })),
    },
  ]

  return {
    title: {
      text: `${k.name || k.code} (${k.market === 'us' ? t('home.kline.marketTag.us') : t('home.kline.marketTag.zhA')})`,
      subtext: `${periodLabel}${adjustLabel ? ' · ' + adjustLabel : ''}`,
      left: 'center',
      top: 2,
      textStyle: { fontSize: 15, fontWeight: 600 },
      subtextStyle: { fontSize: 11, color: '#9ca3af' },
    },
    axisPointer: linkedCrosshair(),
    tooltip: {
      trigger: 'axis',
      axisPointer: crosshairPointer(),
      // 固定数值面板：吸顶并水平钳制在图内，消除对蜡烛的遮挡（与首页看板同款）
      position: (
        point: number[],
        _params: unknown,
        _dom: unknown,
        _rect: unknown,
        size: { contentSize: number[]; viewSize: number[] },
      ) => {
        const w = size.contentSize[0] ?? 220
        const viewW = size.viewSize[0] ?? 600
        const x = Math.min(Math.max((point[0] ?? 0) - w / 2, 8), Math.max(8, viewW - w - 8))
        return [x, 8]
      },
      backgroundColor: th.tooltipBg.value,
      borderColor: th.dark.value ? 'rgba(255,255,255,0.14)' : '#e5e7eb',
      borderWidth: 1,
      textStyle: { color: th.text.value, fontSize: 12 },
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
        // tooltip 文案在悬停时取当前语言（formatter 不在 computed 内执行，需现取 t()）
        lines.push(
          `${pv(t('home.kline.tooltip.open'), o[0])} &nbsp; ${pv(t('home.kline.tooltip.high'), o[3])}<br/>` +
            `${pv(t('home.kline.tooltip.low'), o[2])} &nbsp; ${pv(t('home.kline.tooltip.close'), o[1])}`,
        )
        lines.push(
          `<span style="color:${valColor(chg)}">${t('home.kline.tooltip.change')} ${pctStr(chg)}</span> &nbsp; ` +
            `<span style="color:${valColor(chg)}">${t('home.kline.tooltip.amplitude')} ${pctStr(amp)}</span>`,
        )
        const maLine: string[] = []
        const m5 = ma5[idx]
        const m20 = ma20[idx]
        const m60 = ma60[idx]
        if (m5 != null) maLine.push(`<span style="color:#f59e0b">MA5 ${m5.toFixed(2)}</span>`)
        if (m20 != null) maLine.push(`<span style="color:#667eea">MA20 ${m20.toFixed(2)}</span>`)
        if (m60 != null) maLine.push(`<span style="color:#10b981">MA60 ${m60.toFixed(2)}</span>`)
        if (maLine.length) lines.push(maLine.join(' &nbsp; '))
        const vol = k.volumes[idx]
        if (vol != null) lines.push(`${t('home.kline.tooltip.volume')} ${fmtBigNum(vol)}`)
        return lines.join('<br/>')
      },
    },
    legend: {
      data: [t('home.kline.series.dayK'), 'MA5', 'MA20', 'MA60', t('home.kline.series.volume')],
      top: 50,
      left: 'center',
      itemWidth: 14,
      itemHeight: 8,
      textStyle: { fontSize: 11 },
    },
    // 主图 + 成交量两窗格（无副图）；gridIndex 与各窗格 xAxis/yAxis 一一对应
    grid: [
      { left: '7%', right: '4%', top: 74, height: '58%' },
      { left: '7%', right: '4%', top: '81%', height: '12%' },
    ],
    xAxis: [
      klineXAxis({ data: dates, gridIndex: 0, labelShow: false }),
      klineXAxis({ data: dates, gridIndex: 1, labelShow: true, ticks: monthTicks }),
    ],
    yAxis: [
      { scale: true, splitArea: { show: true }, axisLabel: { formatter: (v: number) => fmtPriceNum(v) } },
      { gridIndex: 1, splitNumber: 2, axisLabel: { show: false } },
    ],
    dataZoom: klineDataZoom({
      xAxisIndex: [0, 1],
      start: 60,
      sliderTop: '94%',
      preventDefaultMouseMove: true,
    }),
    series,
  }
})
</script>

<template>
  <div class="market-page">
    <div class="page-head">
      <h2 class="page-title">{{ t('market.title') }}</h2>
      <p class="page-subtitle">{{ t('market.subtitle') }}</p>
    </div>

    <div class="market-body">
      <!-- 左栏：市场切换 + 搜索 + 标的列表（指数预设 ∪ 自选） -->
      <aside class="symbol-panel">
        <el-radio-group v-model="market" size="small" class="market-switch">
          <el-radio-button value="zh_a">{{ t('common.market.zhA') }}</el-radio-button>
          <el-radio-button value="us">{{ t('common.market.us') }}</el-radio-button>
        </el-radio-group>
        <el-input
          v-model="keyword"
          size="small"
          clearable
          :placeholder="t('market.searchPlaceholder')"
          class="symbol-search"
        >
          <template #prefix><el-icon><Search /></el-icon></template>
        </el-input>

        <el-scrollbar class="symbol-scroll" max-height="600px">
          <template v-for="group in groups" :key="group.key">
            <div class="symbol-group">{{ group.label }}</div>
            <div
              v-for="row in group.rows"
              :key="row.key"
              class="symbol-item"
              :class="{ active: row.key === activeKey }"
              @click="selectRow(row.key)"
            >
              <div class="sym-main">
                <span class="sym-name">{{ row.name }}</span>
                <code class="sym-code">{{ row.code }}</code>
              </div>
              <template v-if="quoteOf(row.key)">
                <span class="sym-price">{{ fmtPriceNum(closeOf(row.key)) }}</span>
                <span class="sym-chg" :style="{ color: deltaColor(row.market, chgPctOf(row.key)) }">
                  {{ signPct(chgPctOf(row.key)) }}
                </span>
              </template>
              <span v-else class="sym-pending">—</span>
            </div>
          </template>

          <!-- 搜索无结果且输入像代码：添加并查看 -->
          <div
            v-if="canAdd"
            class="symbol-item add-row"
            :class="{ disabled: adding }"
            @click="addAndView"
          >
            <el-icon><Plus /></el-icon>
            <span>{{ t('market.addAndView', { code: keyword.trim() }) }}</span>
          </div>
          <el-empty
            v-else-if="!totalMatches"
            :image-size="60"
            :description="t('market.empty')"
          />
        </el-scrollbar>
      </aside>

      <!-- 右侧：大字报价头 + K 线 -->
      <section class="detail-panel">
        <el-card shadow="never" class="quote-card">
          <div v-if="activeTarget" class="quote-head">
            <div class="quote-id">
              <span class="quote-name">{{ activeTarget.name }}</span>
              <code class="quote-code">{{ activeTarget.code }}</code>
              <el-tag size="small" :type="activeTarget.market === 'us' ? 'warning' : 'danger'">
                {{ activeTarget.market === 'us' ? t('common.market.us') : t('common.market.zhA') }}
              </el-tag>
              <el-tag v-if="activeTarget.kind === 'index'" size="small" type="info">
                {{ t('market.indexTag') }}
              </el-tag>
            </div>
            <div v-if="activeQuote" class="quote-price">
              <AnimNumber
                :value="activeQuote.close"
                :decimals="priceDecimals(activeQuote.close)"
                class="big-price"
                :style="{ color: deltaColor(activeTarget.market, activeQuote.chgPct) }"
              />
              <span
                class="delta-badge"
                :style="{ color: deltaColor(activeTarget.market, activeQuote.chgPct) }"
              >
                {{ deltaArrow(activeQuote.chgPct) }}
                {{ signNum(activeQuote.chg) }} ({{ signPct(activeQuote.chgPct) }})
              </span>
            </div>
            <el-skeleton v-else animated class="quote-skeleton">
              <template #template>
                <el-skeleton-item variant="text" style="width: 160px; height: 34px" />
              </template>
            </el-skeleton>
          </div>
          <el-empty v-else :image-size="60" :description="t('market.selectHint')" />
        </el-card>

        <el-card shadow="never" class="kline-card">
          <template #header>
            <div class="kline-header">
              <span class="section-title" style="margin: 0; border: none; padding: 0">
                <el-icon><CandlestickChart /></el-icon> {{ t('market.kline.title') }}
              </span>
              <div class="kline-toolbar">
                <el-radio-group v-model="period" size="small">
                  <el-radio-button value="day">{{ t('home.kline.periodShort.day') }}</el-radio-button>
                  <el-radio-button value="week">{{ t('home.kline.periodShort.week') }}</el-radio-button>
                  <el-radio-button value="month">{{ t('home.kline.periodShort.month') }}</el-radio-button>
                </el-radio-group>
                <el-select
                  v-model="adjust"
                  size="small"
                  class="tb-adjust"
                  :title="t('home.kline.adjustTitle')"
                  :disabled="isIndexTarget"
                >
                  <el-option :label="t('home.kline.adjust.qfq')" value="qfq" />
                  <el-option :label="t('home.kline.adjust.hfq')" value="hfq" />
                  <el-option :label="t('home.kline.adjust.nfq')" value="nfq" />
                </el-select>
                <el-button size="small" text @click="resetZoom">
                  <el-icon><Refresh /></el-icon> {{ t('home.kline.resetZoom') }}
                </el-button>
              </div>
            </div>
          </template>
          <div class="kline-body">
            <el-skeleton v-if="loadingKline" animated :rows="5" style="padding: 16px" />
            <template v-else>
              <v-chart
                v-if="kline && kline.dates.length"
                ref="chartRef"
                class="kline-chart"
                :option="chartOption"
                :update-options="{ notMerge: true }"
                autoresize
              />
              <el-empty v-else :description="t('home.kline.empty')" />
            </template>
          </div>
        </el-card>
      </section>
    </div>
  </div>
</template>

<style scoped>
.market-page {
  padding: 4px 4px 24px;
}
.page-head {
  margin-bottom: 12px;
}
.page-title {
  margin: 6px 0 4px;
  font-size: 22px;
}
.page-subtitle {
  margin: 0;
  color: var(--el-text-color-secondary);
  font-size: 13px;
}
.market-body {
  display: flex;
  gap: 16px;
  align-items: flex-start;
}

/* 左栏：标的列表 */
.symbol-panel {
  flex: 0 0 280px;
  width: 280px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-height: 320px;
}
.market-switch {
  width: 100%;
}
.market-switch :deep(.el-radio-button) {
  flex: 1;
}
.market-switch :deep(.el-radio-button__inner) {
  width: 100%;
}
.symbol-scroll {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 6px;
  min-height: 320px;
}
.symbol-group {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-muted);
  padding: 8px 8px 4px;
}
.symbol-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 8px;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.12s;
}
.symbol-item:hover {
  background: var(--bg);
}
.symbol-item.active {
  background: rgba(102, 126, 234, 0.12);
}
.sym-main {
  flex: 1;
  min-width: 0;
  display: flex;
  align-items: baseline;
  gap: 6px;
  overflow: hidden;
}
.sym-name {
  font-weight: 600;
  font-size: 0.88rem;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.sym-code {
  font-size: 0.72rem;
  color: var(--text-muted);
  flex-shrink: 0;
}
.sym-price {
  font-size: 0.86rem;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
  flex-shrink: 0;
}
.sym-chg {
  font-size: 0.76rem;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  min-width: 56px;
  text-align: right;
  flex-shrink: 0;
}
.sym-pending {
  color: var(--text-muted);
  min-width: 56px;
  text-align: right;
}
.symbol-item.add-row {
  color: var(--brand-start);
  font-size: 0.86rem;
  font-weight: 600;
  gap: 6px;
}
.symbol-item.add-row.disabled {
  opacity: 0.6;
  pointer-events: none;
}

/* 右侧：报价头 + K 线 */
.detail-panel {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.quote-card,
.kline-card {
  border-radius: var(--radius);
}
.quote-card :deep(.el-card__body) {
  padding: 14px 18px;
}
.quote-head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 10px 16px;
}
.quote-id {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}
.quote-name {
  font-size: 1.15rem;
  font-weight: 700;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.quote-code {
  font-size: 0.82rem;
  color: var(--text-muted);
}
.quote-price {
  display: flex;
  align-items: baseline;
  gap: 12px;
}
.big-price {
  font-size: 2rem;
  font-weight: 700;
  line-height: 1.1;
}
.delta-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 0.85rem;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  padding: 2px 9px;
  border-radius: 999px;
  background: var(--bg);
  border: 1px solid var(--border);
  white-space: nowrap;
}
.quote-skeleton {
  min-width: 180px;
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
/* 复权下拉宽度按英文最长档位「Backward Adj.」预留（EP small select 内距 + 箭头） */
.tb-adjust {
  width: 112px;
}
.kline-body {
  min-height: 520px;
}
.kline-chart {
  height: 520px;
  width: 100%;
}

/* 窄屏：左栏列表改为整行置顶，K 线仍占满宽度 */
@media (max-width: 992px) {
  .market-body {
    flex-direction: column;
  }
  .symbol-panel {
    flex: 0 0 auto;
    width: 100%;
  }
  .symbol-scroll {
    max-height: 320px;
  }
}
</style>
