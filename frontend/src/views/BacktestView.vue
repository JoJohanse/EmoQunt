<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { backtestApi, strategyApi, klineApi } from '@/api'
import type { BacktestMetrics, BacktestRequest, BacktestResult, BacktestTrade, KlineData, Market, StrategyDetail } from '@/api/types'
import { chartPalette, deltaTone } from '@/lib/marketColors'
import {
  candleItemStyle,
  chgVsPrevClose,
  crosshairPointer,
  fmtPriceNum,
  klineDataZoom,
  klineXAxis,
} from '@/chart/kline'
import { useBacktestHistoryStore } from '@/stores/backtestHistory'
import { t } from '@/locales'
import { fmtCurrency, fmtNum } from '@/lib/format'
import { VChart } from '@/composables/useECharts'

const route = useRoute()
const historyStore = useBacktestHistoryStore()

const strategies = ref<StrategyDetail[]>([])
const loading = ref(false)
const result = ref<BacktestResult | null>(null)

const form = ref<BacktestRequest>({
  strategy_name: '',
  stock_code: '000001',
  start_date: '2024-01-01',
  end_date: '2024-12-31',
  initial_capital: 100000,
  commission_rate: 0.0003,
  market: 'zh_a',
})

// 恢复上次填写的表单（本地持久化）；首页"重跑"通过 historyId 覆盖
if (historyStore.lastForm) {
  form.value = { ...historyStore.lastForm }
}
const historyId = route.query.historyId as string | undefined
if (historyId) {
  const rec = historyStore.records.find((r) => r.id === historyId)
  if (rec) {
    form.value = { ...rec.params }
    ElMessage.info(
      t('backtest.formRestored', { name: rec.strategyName, code: rec.stockCode }),
    )
  }
}

watch(
  () => route.query.historyId,
  (hid) => {
    if (typeof hid === 'string' && hid) {
      const rec = historyStore.records.find((r) => r.id === hid)
      if (rec) {
        form.value = { ...rec.params }
        ElMessage.info(
          t('backtest.formRestored', { name: rec.strategyName, code: rec.stockCode }),
        )
      }
    }
  },
)

// 加载策略列表
;(async () => {
  try {
    strategies.value = await strategyApi.list()
    if (strategies.value.length && !form.value.strategy_name) {
      form.value.strategy_name = strategies.value[0].name
    }
  } catch (e: any) {
    ElMessage.warning(t('backtest.strategiesLoadFailed') + e.message)
  }
})()

const isUS = computed(() => form.value.market === 'us')
const currencyLabel = computed(() => t(isUS.value ? 'backtest.currency.usd' : 'backtest.currency.cny'))
const stockHint = computed(() => t(isUS.value ? 'backtest.stockHint.us' : 'backtest.stockHint.zh_a'))
const commissionHint = computed(() =>
  t(isUS.value ? 'backtest.commissionHint.us' : 'backtest.commissionHint.zh_a'),
)

function onMarketChange() {
  form.value.stock_code = isUS.value ? 'AAPL' : '000001'
  form.value.commission_rate = isUS.value ? 0.0005 : 0.0003
}

async function runBacktest() {
  if (!form.value.strategy_name) {
    ElMessage.warning(t('backtest.selectStrategyRequired'))
    return
  }
  loading.value = true
  result.value = null
  try {
    result.value = await backtestApi.run(form.value)
    // 记录回测历史并记忆表单（localStorage，首页"最近回测"展示）
    historyStore.add(form.value, result.value)
    ElMessage.success(t('backtest.done'))
  } catch (e: any) {
    ElMessage.error(t('backtest.runFailed') + e.message)
  } finally {
    loading.value = false
  }
}

// 指标显示译文：键是后端 JSON 的中文契约字段名，值是当前语言下的标签
const metricLabel = computed<Record<string, string>>(() => ({
  总收益率: t('backtest.metric.总收益率'),
  年化收益率: t('backtest.metric.年化收益率'),
  夏普比率: t('backtest.metric.夏普比率'),
  最大回撤: t('backtest.metric.最大回撤'),
  胜率: t('backtest.metric.胜率'),
  盈亏比: t('backtest.metric.盈亏比'),
  信息比率: t('backtest.metric.信息比率'),
  年化波动率: t('backtest.metric.年化波动率'),
  卡玛比率: t('backtest.metric.卡玛比率'),
  下行标准差: t('backtest.metric.下行标准差'),
  'VaR (95%)': t('backtest.metric.var95'),
  'CVaR (95%)': t('backtest.metric.cvar95'),
  交易次数: t('backtest.metric.交易次数'),
  盈利交易数: t('backtest.metric.盈利交易数'),
  亏损交易数: t('backtest.metric.亏损交易数'),
}))

// 指标卡片
const metricCards = computed(() => {
  if (!result.value) return []
  const m = result.value.metrics
  const market = result.value.market
  const fmtPct = (v: number) => (v * 100).toFixed(2) + '%'
  const fmtFixed = (v: number) => v.toFixed(2)
  // 正/负收益的语义色调：A股红涨绿跌 / 美股绿涨红跌（此前固定绿涨，A股正收益误显示为绿）
  const retTone = (v: number) => deltaTone(market, v >= 0 ? 'up' : 'down')
  const opt = (key: keyof BacktestMetrics, fmt: (v: number) => string, type: (v: number) => 'success' | 'danger' | 'neutral', group: string) =>
    m[key] !== undefined ? [{ label: metricLabel.value[key], value: fmt(m[key] as number), type: type(m[key] as number), group }] : []
  return [
    { label: metricLabel.value.总收益率, value: fmtPct(m.总收益率), type: retTone(m.总收益率), group: 'return' },
    { label: metricLabel.value.年化收益率, value: fmtPct(m.年化收益率), type: retTone(m.年化收益率), group: 'return' },
    { label: metricLabel.value.夏普比率, value: fmtFixed(m.夏普比率), type: retTone(m.夏普比率), group: 'return' },
    { label: metricLabel.value.最大回撤, value: fmtPct(m.最大回撤), type: 'danger', group: 'risk' },
    { label: metricLabel.value.胜率, value: fmtPct(m.胜率), type: 'neutral', group: 'return' },
    { label: metricLabel.value.盈亏比, value: fmtFixed(m.盈亏比), type: m.盈亏比 >= 1 ? 'success' : 'danger', group: 'return' },
    ...(m.Alpha !== undefined ? [{ label: 'Alpha', value: fmtPct(m.Alpha), type: retTone(m.Alpha), group: 'benchmark' }] : []),
    ...(m.Beta !== undefined ? [{ label: 'Beta', value: fmtFixed(m.Beta), type: 'neutral', group: 'benchmark' }] : []),
    ...(m.信息比率 !== undefined ? [{ label: metricLabel.value.信息比率, value: fmtFixed(m.信息比率), type: retTone(m.信息比率), group: 'benchmark' }] : []),
    // 完整绩效报告新增指标（可选）
    ...opt('年化波动率', fmtPct, (v) => (v <= 0.25 ? 'success' : 'danger'), 'risk'),
    ...opt('卡玛比率', fmtFixed, (v) => (v >= 1 ? 'success' : 'danger'), 'return'),
    ...opt('下行标准差', fmtPct, () => 'neutral', 'risk'),
    ...opt('VaR (95%)', fmtFixed, () => 'danger', 'risk'),
    ...opt('CVaR (95%)', fmtFixed, () => 'danger', 'risk'),
    ...opt('交易次数', fmtFixed, () => 'neutral', 'return'),
    ...opt('盈利交易数', fmtFixed, () => 'success', 'return'),
    ...opt('亏损交易数', fmtFixed, () => 'danger', 'return'),
  ]
})

// 风险报告（VaR/压力测试）——独立面板
const riskReport = computed(() => result.value?.risk_report ?? null)
// 风险面板金额所用的市场口径（与最近一次回测结果一致，无结果时回退当前表单）
const resultMarket = computed<Market>(() => result.value?.market ?? form.value.market)
const stressRows = computed(() => {
  const s = riskReport.value?.stress_test
  if (!s) return []
  return Object.entries(s).map(([k, v]) => ({ scenario: k, value: v as number }))
})

// 收益曲线 ECharts 配置（动态，可缩放）
const equityOption = computed(() => {
  if (!result.value) return {}
  const r = result.value
  // 基准名称按市场确定：A股=沪深300，美股=标普500
  const benchmarkName = t(r.market === 'us' ? 'backtest.benchmark.sp500' : 'backtest.benchmark.csi300')
  // 货币格式化（金额，非百分比）：符号由市场决定、千分位随当前语言
  const fmtMoney = (v: number) => fmtCurrency(v, r.market)
  const series: any[] = [
    {
      name: t('backtest.series.strategyNav'),
      type: 'line',
      data: r.equity_curve,
      smooth: true,
      showSymbol: false,
      lineStyle: { width: 2, color: '#667eea' },
      areaStyle: { opacity: 0.1 },
    },
  ]
  if (r.benchmark_curve && r.benchmark_curve.length) {
    // 基准原始归一化为 1.0，缩放到与策略相同的初始资金，便于同坐标比较
    const scale = r.equity_curve.length ? r.equity_curve[0] : 1.0
    const benchmarkScaled = r.benchmark_curve.map((v) => +(v * scale).toFixed(2))
    series.push({
      name: benchmarkName,
      type: 'line',
      data: benchmarkScaled,
      smooth: true,
      showSymbol: false,
      lineStyle: { width: 2, color: '#f59e0b', type: 'dashed' },
    })
  }
  return {
    tooltip: { trigger: 'axis', valueFormatter: (v: number) => fmtMoney(v) },
    legend: { data: series.map((s) => s.name), top: 0 },
    grid: { left: '3%', right: '3%', bottom: '15%', containLabel: true },
    toolbox: { feature: { dataZoom: { yAxisIndex: 'none' }, saveAsImage: {} } },
    dataZoom: [
      { type: 'inside', start: 0, end: 100 },
      { type: 'slider', start: 0, end: 100 },
    ],
    xAxis: { type: 'category', data: r.dates, boundaryGap: false },
    yAxis: {
      type: 'value',
      scale: true,
      axisLabel: { formatter: (v: number) => fmtNum(v, { maximumFractionDigits: 0 }) },
      name: currencyLabel.value,
    },
    series,
  }
})

// 回撤曲线（动态）
const drawdownOption = computed(() => {
  if (!result.value) return {}
  const r = result.value
  return {
    tooltip: { trigger: 'axis', valueFormatter: (v: number) => (v * 100).toFixed(2) + '%' },
    grid: { left: '3%', right: '3%', bottom: '15%', containLabel: true },
    dataZoom: [
      { type: 'inside', start: 0, end: 100 },
      { type: 'slider', start: 0, end: 100 },
    ],
    xAxis: { type: 'category', data: r.dates, boundaryGap: false },
    yAxis: { type: 'value', axisLabel: { formatter: (v: number) => (v * 100).toFixed(0) + '%' } },
    series: [
      {
        name: t('backtest.series.drawdown'),
        type: 'line',
        data: r.drawdown,
        showSymbol: false,
        lineStyle: { width: 1.5, color: '#dc3545' },
        areaStyle: { color: 'rgba(220, 53, 69, 0.25)' },
      },
    ],
  }
})

// 日收益率柱状（动态）
const returnsOption = computed(() => {
  if (!result.value) return {}
  const r = result.value
  // 日收益柱涨跌色按回测市场取 token：A股红涨绿跌 / 美股绿涨红跌（此前固定绿涨）
  const { up, down } = chartPalette(r.market)
  return {
    tooltip: { trigger: 'axis', valueFormatter: (v: number) => (v * 100).toFixed(2) + '%' },
    grid: { left: '3%', right: '3%', bottom: '15%', containLabel: true },
    dataZoom: [
      { type: 'inside', start: 0, end: 100 },
      { type: 'slider', start: 0, end: 100 },
    ],
    xAxis: { type: 'category', data: r.dates },
    yAxis: { type: 'value', axisLabel: { formatter: (v: number) => (v * 100).toFixed(1) + '%' } },
    series: [
      {
        name: t('backtest.series.dailyReturns'),
        type: 'bar',
        data: r.daily_returns.map((v) => ({
          value: v,
          itemStyle: { color: v >= 0 ? up : down },
        })),
      },
    ],
  }
})

// ===== 回测 K 线（买卖点标注，P0-5） =====
const tradesKline = ref<KlineData | null>(null)
const loadingTradesKline = ref(false)

// 复权口径与回测核心一致（A股后复权 / 美股前复权），成交价才能与蜡烛对齐
const tradesKlineAdjust = computed<'qfq' | 'hfq'>(() => (result.value?.market === 'us' ? 'qfq' : 'hfq'))

async function loadTradesKline(r: BacktestResult) {
  if (!r.dates.length) return
  loadingTradesKline.value = true
  try {
    // 区间模式：按回测区间 ±5 个自然日取数（服务端忽略 days 裁剪），
    // 保证成交日期与 K 线类目轴一一对应，markPoint 才能打上
    const shift = (d: string, days: number) => {
      const t = new Date(d)
      t.setDate(t.getDate() + days)
      return t.toISOString().slice(0, 10)
    }
    const range = { start: shift(r.dates[0], -5), end: shift(r.dates[r.dates.length - 1], 5) }
    tradesKline.value = await klineApi.get(r.stock_code, r.market, 30, 'day', tradesKlineAdjust.value, '', range)
  } catch (e: any) {
    console.warn('回测K线加载失败', e.message)
    tradesKline.value = null
  } finally {
    loadingTradesKline.value = false
  }
}

watch(result, (r) => {
  if (r) loadTradesKline(r)
})

const tradesKlineOption = computed(() => {
  const k = tradesKline.value
  if (!k || !k.dates.length || !result.value) return {}
  const trades: BacktestTrade[] = result.value.trades ?? []
  // 与 K 线主图一致的涨跌配色：A股红涨绿跌 / 美股绿涨红跌（token 见 lib/marketColors）
  const { up: upColor, down: downColor } = chartPalette(k.market)

  const buys = trades.filter((t) => t.side === 'buy')
  const cost = buys.length
    ? buys.reduce((s, t) => s + t.price * t.size, 0) / buys.reduce((s, t) => s + t.size, 0)
    : null

  const markPointData = trades.slice(0, 200).map((t) => ({
    coord: [t.date, t.price] as [string, number],
    symbol: 'arrow',
    symbolSize: 11,
    symbolRotate: t.side === 'buy' ? 0 : 180,
    symbolOffset: t.side === 'buy' ? [0, '130%'] : [0, '-130%'],
    itemStyle: { color: t.side === 'buy' ? upColor : downColor },
    label: { show: false },
  }))

  return {
    tooltip: {
      trigger: 'axis',
      axisPointer: crosshairPointer(),
      formatter(params: any) {
        const arr: any[] = Array.isArray(params) ? params : [params]
        const idx = arr[0]?.dataIndex ?? 0
        const o = k.ohlcv[idx]
        if (!o) return k.dates[idx] ?? ''
        // 前收涨跌口径统一走 chart/kline（首根回退为开盘价）
        const chg = chgVsPrevClose(k.ohlcv, idx).chgPct
        return (
          `<b>${k.dates[idx]}</b><br/>` +
          `${t('backtest.tooltip.open')} ${o[0].toFixed(2)} ${t('backtest.tooltip.close')} ${o[1].toFixed(2)}<br/>` +
          `${t('backtest.tooltip.low')} ${o[2].toFixed(2)} ${t('backtest.tooltip.high')} ${o[3].toFixed(2)}<br/>` +
          `${t('backtest.tooltip.change')} ${chg >= 0 ? '+' : ''}${chg.toFixed(2)}%`
        )
      },
    },
    grid: { left: '3%', right: '4%', top: 34, bottom: 52, containLabel: true },
    xAxis: klineXAxis({ data: k.dates }),
    yAxis: {
      scale: true,
      axisLabel: { formatter: fmtPriceNum },
    },
    dataZoom: klineDataZoom({ sliderBottom: 12 }),
    series: [
      {
        name: t('backtest.series.dailyK'),
        type: 'candlestick',
        data: k.ohlcv,
        itemStyle: candleItemStyle(k.market),
        markPoint: { data: markPointData, animation: false },
        // 买入加权平均成本线（对标 Lightweight Charts PriceLine：带标题的价格线）
        ...(cost != null
          ? {
              markLine: {
                symbol: ['none', 'none'],
                silent: true,
                animation: false,
                lineStyle: { type: 'dotted', width: 1.2, color: '#f59e0b' },
                label: {
                  // formatter 在 ECharts 渲染时执行，闭包内调用 t() 仍随语言切换
                  formatter: () => `${t('backtest.avgCost')} ${cost.toFixed(2)}`,
                  color: '#b45309',
                  fontSize: 11,
                },
                data: [{ yAxis: +cost.toFixed(2) }],
              },
            }
          : {}),
      },
    ],
  }
})
</script>

<template>
  <div v-loading.fullscreen="loading" :element-loading-text="t('backtest.running')">
    <div class="page-hero">
      <h1><el-icon><TrendCharts /></el-icon> {{ t('layout.nav.backtest') }}</h1>
      <p class="subtitle">{{ t('backtest.subtitle') }}</p>
    </div>

    <el-card shadow="never" class="form-card">
      <el-form :model="form" label-width="110px" label-position="right">
        <el-form-item :label="t('backtest.form.market')">
          <el-radio-group v-model="form.market" @change="onMarketChange">
            <el-radio-button value="zh_a">{{ t('backtest.market.zh_a') }}</el-radio-button>
            <el-radio-button value="us">{{ t('backtest.market.us') }}</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-row :gutter="20">
          <el-col :xs="24" :md="12">
            <el-form-item :label="t('backtest.form.strategy')">
              <el-select v-model="form.strategy_name" :placeholder="t('backtest.form.strategyPlaceholder')" style="width: 100%">
                <el-option
                  v-for="s in strategies"
                  :key="s.name"
                  :label="s.name"
                  :value="s.name"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="12">
            <el-form-item :label="t('backtest.form.stockCode')">
              <el-input v-model="form.stock_code" :placeholder="stockHint" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :xs="12" :md="6">
            <el-form-item :label="t('backtest.form.initialCapital')">
              <el-input-number v-model="form.initial_capital" :min="1000" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :xs="12" :md="6">
            <el-form-item :label="t('backtest.form.commissionRate')">
              <el-input-number v-model="form.commission_rate" :step="0.0001" :min="0" :max="0.01" :precision="4" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :xs="12" :md="6">
            <el-form-item :label="t('backtest.form.startDate')">
              <el-date-picker v-model="form.start_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :xs="12" :md="6">
            <el-form-item :label="t('backtest.form.endDate')">
              <el-date-picker v-model="form.end_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item>
          <el-button type="primary" :loading="loading" @click="runBacktest">
            <el-icon><VideoPlay /></el-icon> {{ t('backtest.form.run') }}
          </el-button>
          <small class="hint">{{ commissionHint }}</small>
        </el-form-item>
      </el-form>
    </el-card>

    <template v-if="result">
      <div class="section-title"><el-icon><DataAnalysis /></el-icon> {{ t('backtest.section.metrics') }}</div>
      <el-row :gutter="12" class="metrics-row">
        <el-col v-for="mc in metricCards" :key="mc.label" :xs="8" :sm="6" :md="4" :lg="3">
          <div class="metric-card" :class="'g-' + mc.group">
            <div class="metric-label">{{ mc.label }}</div>
            <div class="metric-value" :class="'v-' + mc.type">{{ mc.value }}</div>
          </div>
        </el-col>
      </el-row>

      <div class="section-title"><el-icon><CandlestickChart /></el-icon> {{ t('backtest.section.tradesKline') }}</div>
      <el-card shadow="never" class="chart-card">
        <div v-if="loadingTradesKline" style="padding: 16px">
          <el-skeleton animated :rows="5" />
        </div>
        <template v-else>
          <v-chart
            v-if="tradesKline && tradesKline.dates.length"
            class="chart chart-kline"
            :option="tradesKlineOption"
            :update-options="{ notMerge: true }"
            autoresize
          />
          <el-empty v-else :image-size="60" :description="t('backtest.empty.kline')" />
        </template>
        <div v-if="!loadingTradesKline && result && !(result.trades ?? []).length" class="trades-hint">
          {{ t('backtest.noTrades') }}
        </div>
      </el-card>

      <div class="section-title"><el-icon><TrendCharts /></el-icon> {{ t('backtest.section.equity') }}</div>
      <el-card shadow="never" class="chart-card">
        <v-chart class="chart" :option="equityOption" autoresize />
      </el-card>

      <div class="section-title"><el-icon><Bottom /></el-icon> {{ t('backtest.section.drawdown') }}</div>
      <el-card shadow="never" class="chart-card">
        <v-chart class="chart" :option="drawdownOption" autoresize />
      </el-card>

      <div class="section-title"><el-icon><Histogram /></el-icon> {{ t('backtest.section.dailyReturns') }}</div>
      <el-card shadow="never" class="chart-card">
        <v-chart class="chart" :option="returnsOption" autoresize />
      </el-card>

      <!-- 风险分析面板（激活 RiskManager）-->
      <template v-if="riskReport">
        <div class="section-title"><el-icon><Warning /></el-icon> {{ t('backtest.risk.title') }}</div>
        <el-card shadow="never" class="risk-card">
          <el-row :gutter="12">
            <el-col :xs="12" :sm="8" :md="6">
              <div class="risk-item">
                <div class="risk-label">{{ t('backtest.risk.historicalVar') }}</div>
                <div class="risk-value v-danger">{{ fmtCurrency(riskReport.var_analysis.historical_var, resultMarket) }}</div>
              </div>
            </el-col>
            <el-col :xs="12" :sm="8" :md="6">
              <div class="risk-item">
                <div class="risk-label">{{ t('backtest.risk.parametricVar') }}</div>
                <div class="risk-value v-danger">{{ fmtCurrency(riskReport.var_analysis.parametric_var, resultMarket) }}</div>
              </div>
            </el-col>
            <el-col :xs="12" :sm="8" :md="6">
              <div class="risk-item">
                <div class="risk-label">{{ t('backtest.risk.cvar') }}</div>
                <div class="risk-value v-danger">{{ fmtCurrency(riskReport.var_analysis.cvar, resultMarket) }}</div>
              </div>
            </el-col>
            <el-col :xs="12" :sm="8" :md="6">
              <div class="risk-item">
                <!-- 与指标卡片同一术语：复用 metric.* 译文，避免同一词两处漂移 -->
                <div class="risk-label">{{ t('backtest.metric.年化波动率') }}</div>
                <div class="risk-value">{{ (riskReport.volatility * 100).toFixed(2) }}%</div>
              </div>
            </el-col>
            <el-col :xs="12" :sm="8" :md="6">
              <div class="risk-item">
                <div class="risk-label">{{ t('backtest.risk.currentDrawdown') }}</div>
                <div class="risk-value v-danger">{{ (riskReport.current_drawdown * 100).toFixed(2) }}%</div>
              </div>
            </el-col>
            <el-col :xs="12" :sm="8" :md="6">
              <div class="risk-item">
                <div class="risk-label">{{ t('backtest.risk.maxDrawdownLimit') }}</div>
                <div class="risk-value">{{ (riskReport.max_drawdown_limit * 100).toFixed(1) }}%</div>
              </div>
            </el-col>
          </el-row>

          <div class="stress-title">
            {{ t('backtest.risk.stressTitle', { value: fmtCurrency(stressRows.length ? stressRows[0].value : 0, resultMarket) }) }}
          </div>
          <el-table :data="stressRows" stripe size="small" style="width: 100%">
            <el-table-column prop="scenario" :label="t('backtest.risk.scenario')" />
            <el-table-column :label="t('backtest.risk.varColumn', { unit: currencyLabel })">
              <template #default="{ row }">{{ row.value.toFixed(2) }}</template>
            </el-table-column>
          </el-table>
        </el-card>
      </template>
    </template>

    <el-empty v-else-if="!loading" :description="t('backtest.empty.result')" />
  </div>
</template>

<style scoped>
.form-card {
  border-radius: var(--radius);
  margin-bottom: 1rem;
}
.hint {
  color: var(--text-muted);
  margin-left: 12px;
}
.metrics-row {
  margin-bottom: 1rem;
}
.metric-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 12px 8px;
  text-align: center;
  margin-bottom: 12px;
  border-top: 3px solid var(--border);
}
.metric-card.g-return { border-top-color: var(--success); }
.metric-card.g-risk { border-top-color: var(--danger); }
.metric-card.g-benchmark { border-top-color: var(--info); }
.metric-label {
  color: var(--text-muted);
  font-size: 0.82rem;
  margin-bottom: 4px;
}
.metric-value {
  font-size: 1.25rem;
  font-weight: 700;
}
.v-success { color: var(--success); }
.v-danger { color: var(--danger); }
.v-neutral { color: var(--brand-start); }
.chart-card {
  border-radius: var(--radius);
  margin-bottom: 1.25rem;
}
.chart {
  height: 380px;
  width: 100%;
}
.chart-kline {
  height: 420px;
}
.trades-hint {
  color: var(--text-muted);
  font-size: 0.82rem;
  padding: 4px 4px 0;
}
.risk-card {
  border-radius: var(--radius);
  margin-bottom: 1.25rem;
  border-top: 3px solid var(--danger);
}
.risk-item {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 12px;
  text-align: center;
  margin-bottom: 12px;
}
.risk-label {
  color: var(--text-muted);
  font-size: 0.82rem;
  margin-bottom: 4px;
}
.risk-value {
  font-size: 1.15rem;
  font-weight: 700;
}
.stress-title {
  margin-top: 0.5rem;
  margin-bottom: 0.5rem;
  color: var(--text-muted);
  font-size: 0.9rem;
}
</style>
