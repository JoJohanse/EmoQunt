<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { backtestApi, strategyApi, klineApi } from '@/api'
import type { BacktestMetrics, BacktestRequest, BacktestResult, BacktestTrade, KlineData, Market, StrategyDetail } from '@/api/types'
import { useBacktestHistoryStore } from '@/stores/backtestHistory'
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
    ElMessage.info(`已回填历史回测参数：${rec.strategyName} · ${rec.stockCode}`)
  }
}

watch(
  () => route.query.historyId,
  (hid) => {
    if (typeof hid === 'string' && hid) {
      const rec = historyStore.records.find((r) => r.id === hid)
      if (rec) {
        form.value = { ...rec.params }
        ElMessage.info(`已回填历史回测参数：${rec.strategyName} · ${rec.stockCode}`)
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
    ElMessage.warning('策略列表加载失败：' + e.message)
  }
})()

const isUS = computed(() => form.value.market === 'us')
const currencyLabel = computed(() => (isUS.value ? '美元' : '元'))
const stockHint = computed(() =>
  isUS.value ? '美股字母代码，如 AAPL、MSFT、BRK.B' : '不带前缀的 6 位 A 股代码',
)
const commissionHint = computed(() =>
  isUS.value
    ? '美股仅佣金（双边），无印花税/过户费'
    : 'A 股已自动叠加印花税（卖出 0.05%）与过户费（双边 0.001%）',
)

function onMarketChange() {
  form.value.stock_code = isUS.value ? 'AAPL' : '000001'
  form.value.commission_rate = isUS.value ? 0.0005 : 0.0003
}

async function runBacktest() {
  if (!form.value.strategy_name) {
    ElMessage.warning('请选择策略')
    return
  }
  loading.value = true
  result.value = null
  try {
    result.value = await backtestApi.run(form.value)
    // 记录回测历史并记忆表单（localStorage，首页"最近回测"展示）
    historyStore.add(form.value, result.value)
    ElMessage.success('回测完成')
  } catch (e: any) {
    ElMessage.error('回测失败：' + e.message)
  } finally {
    loading.value = false
  }
}

// 指标卡片
const metricCards = computed(() => {
  if (!result.value) return []
  const m = result.value.metrics
  const fmtPct = (v: number) => (v * 100).toFixed(2) + '%'
  const fmtNum = (v: number) => v.toFixed(2)
  const opt = (key: keyof BacktestMetrics, label: string, fmt: (v: number) => string, type: (v: number) => 'success' | 'danger' | 'neutral', group: string) =>
    m[key] !== undefined ? [{ label, value: fmt(m[key] as number), type: type(m[key] as number), group }] : []
  return [
    { label: '总收益率', value: fmtPct(m.总收益率), type: m.总收益率 >= 0 ? 'success' : 'danger', group: 'return' },
    { label: '年化收益率', value: fmtPct(m.年化收益率), type: m.年化收益率 >= 0 ? 'success' : 'danger', group: 'return' },
    { label: '夏普比率', value: fmtNum(m.夏普比率), type: m.夏普比率 >= 0 ? 'success' : 'danger', group: 'return' },
    { label: '最大回撤', value: fmtPct(m.最大回撤), type: 'danger', group: 'risk' },
    { label: '胜率', value: fmtPct(m.胜率), type: 'neutral', group: 'return' },
    { label: '盈亏比', value: fmtNum(m.盈亏比), type: m.盈亏比 >= 1 ? 'success' : 'danger', group: 'return' },
    ...(m.Alpha !== undefined ? [{ label: 'Alpha', value: fmtPct(m.Alpha), type: m.Alpha >= 0 ? 'success' : 'danger', group: 'benchmark' }] : []),
    ...(m.Beta !== undefined ? [{ label: 'Beta', value: fmtNum(m.Beta), type: 'neutral', group: 'benchmark' }] : []),
    ...(m.信息比率 !== undefined ? [{ label: '信息比率', value: fmtNum(m.信息比率), type: m.信息比率 >= 0 ? 'success' : 'danger', group: 'benchmark' }] : []),
    // 完整绩效报告新增指标（可选）
    ...opt('年化波动率', '年化波动率', fmtPct, (v) => (v <= 0.25 ? 'success' : 'danger'), 'risk'),
    ...opt('卡玛比率', '卡玛比率', fmtNum, (v) => (v >= 1 ? 'success' : 'danger'), 'return'),
    ...opt('下行标准差', '下行标准差', fmtPct, () => 'neutral', 'risk'),
    ...opt('VaR (95%)', 'VaR(95%)', fmtNum, () => 'danger', 'risk'),
    ...opt('CVaR (95%)', 'CVaR(95%)', fmtNum, () => 'danger', 'risk'),
    ...opt('交易次数', '交易次数', fmtNum, () => 'neutral', 'return'),
    ...opt('盈利交易数', '盈利交易', fmtNum, () => 'success', 'return'),
    ...opt('亏损交易数', '亏损交易', fmtNum, () => 'danger', 'return'),
  ]
})

// 风险报告（VaR/压力测试）——独立面板
const riskReport = computed(() => result.value?.risk_report ?? null)
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
  const benchmarkName = r.market === 'us' ? '标普500' : '沪深300'
  // 货币格式化（金额，非百分比）
  const fmtMoney = (v: number) =>
    v.toLocaleString('zh-CN', { maximumFractionDigits: 2 }) +
    (r.market === 'us' ? ' $' : ' 元')
  const series: any[] = [
    {
      name: '策略净值',
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
      axisLabel: { formatter: (v: number) => v.toLocaleString('zh-CN', { maximumFractionDigits: 0 }) },
      name: isUS.value ? '美元' : '元',
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
        name: '回撤',
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
        name: '日收益率',
        type: 'bar',
        data: r.daily_returns.map((v) => ({
          value: v,
          itemStyle: { color: v >= 0 ? '#28a745' : '#dc3545' },
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
  const isUS = k.market === 'us'
  // 与 K 线主图一致的涨跌配色：A股红涨绿跌 / 美股绿涨红跌
  const upColor = isUS ? '#26a69a' : '#ef232a'
  const downColor = isUS ? '#ef5350' : '#14b143'

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
      axisPointer: { type: 'cross', label: { backgroundColor: '#6a7985' } },
      formatter(params: any) {
        const arr: any[] = Array.isArray(params) ? params : [params]
        const idx = arr[0]?.dataIndex ?? 0
        const o = k.ohlcv[idx]
        if (!o) return k.dates[idx] ?? ''
        const prev = idx > 0 ? k.ohlcv[idx - 1]![1] : o[0]
        const chg = prev ? (o[1] / prev - 1) * 100 : 0
        return (
          `<b>${k.dates[idx]}</b><br/>` +
          `开 ${o[0].toFixed(2)} 收 ${o[1].toFixed(2)}<br/>` +
          `低 ${o[2].toFixed(2)} 高 ${o[3].toFixed(2)}<br/>` +
          `涨跌 ${chg >= 0 ? '+' : ''}${chg.toFixed(2)}%`
        )
      },
    },
    grid: { left: '3%', right: '4%', top: 34, bottom: 52, containLabel: true },
    xAxis: {
      type: 'category',
      data: k.dates,
      boundaryGap: true,
      min: 'dataMin',
      max: 'dataMax',
      axisLine: { onZero: false },
      axisTick: { show: false },
    },
    yAxis: {
      scale: true,
      axisLabel: {
        formatter: (v: number) =>
          v.toLocaleString('zh-CN', {
            minimumFractionDigits: Math.abs(v) >= 1000 ? 0 : 2,
            maximumFractionDigits: Math.abs(v) >= 1000 ? 0 : 2,
          }),
      },
    },
    dataZoom: [
      { type: 'inside', start: 0, end: 100, minValueSpan: 15, zoomOnMouseWheel: true, moveOnMouseMove: true },
      { type: 'slider', start: 0, end: 100, height: 18, bottom: 12 },
    ],
    series: [
      {
        name: '日K',
        type: 'candlestick',
        data: k.ohlcv,
        itemStyle: { color: upColor, color0: downColor, borderColor: upColor, borderColor0: downColor },
        markPoint: { data: markPointData, animation: false },
        // 买入加权平均成本线（对标 Lightweight Charts PriceLine：带标题的价格线）
        ...(cost != null
          ? {
              markLine: {
                symbol: ['none', 'none'],
                silent: true,
                animation: false,
                lineStyle: { type: 'dotted', width: 1.2, color: '#f59e0b' },
                label: { formatter: () => `成本均价 ${cost.toFixed(2)}`, color: '#b45309', fontSize: 11 },
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
  <div v-loading.fullscreen="loading" element-loading-text="正在运行回测，请稍候...">
    <div class="page-hero">
      <h1><el-icon><TrendCharts /></el-icon> 策略回测</h1>
      <p class="subtitle">选择市场、策略与标的，运行回测查看动态绩效图表（Alpha/Beta、回撤、日收益）</p>
    </div>

    <el-card shadow="never" class="form-card">
      <el-form :model="form" label-width="110px" label-position="right">
        <el-form-item label="市场">
          <el-radio-group v-model="form.market" @change="onMarketChange">
            <el-radio-button value="zh_a">A 股</el-radio-button>
            <el-radio-button value="us">美股</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-row :gutter="20">
          <el-col :xs="24" :md="12">
            <el-form-item label="选择策略">
              <el-select v-model="form.strategy_name" placeholder="请选择策略" style="width: 100%">
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
            <el-form-item label="股票代码">
              <el-input v-model="form.stock_code" :placeholder="stockHint" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :xs="12" :md="6">
            <el-form-item label="初始资金">
              <el-input-number v-model="form.initial_capital" :min="1000" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :xs="12" :md="6">
            <el-form-item label="佣金费率">
              <el-input-number v-model="form.commission_rate" :step="0.0001" :min="0" :max="0.01" :precision="4" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :xs="12" :md="6">
            <el-form-item label="开始日期">
              <el-date-picker v-model="form.start_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :xs="12" :md="6">
            <el-form-item label="结束日期">
              <el-date-picker v-model="form.end_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item>
          <el-button type="primary" :loading="loading" @click="runBacktest">
            <el-icon><VideoPlay /></el-icon> 运行回测
          </el-button>
          <small class="hint">{{ commissionHint }}</small>
        </el-form-item>
      </el-form>
    </el-card>

    <template v-if="result">
      <div class="section-title"><el-icon><DataAnalysis /></el-icon> 绩效指标</div>
      <el-row :gutter="12" class="metrics-row">
        <el-col v-for="mc in metricCards" :key="mc.label" :xs="8" :sm="6" :md="4" :lg="3">
          <div class="metric-card" :class="'g-' + mc.group">
            <div class="metric-label">{{ mc.label }}</div>
            <div class="metric-value" :class="'v-' + mc.type">{{ mc.value }}</div>
          </div>
        </el-col>
      </el-row>

      <div class="section-title"><el-icon><CandlestickChart /></el-icon> 回测 K 线 · 买卖点标注</div>
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
          <el-empty v-else :image-size="60" description="K线数据加载失败或回测区间无效" />
        </template>
        <div v-if="!loadingTradesKline && result && !(result.trades ?? []).length" class="trades-hint">
          回测期间无成交记录（策略未触发买卖信号）
        </div>
      </el-card>

      <div class="section-title"><el-icon><TrendCharts /></el-icon> 累计收益曲线</div>
      <el-card shadow="never" class="chart-card">
        <v-chart class="chart" :option="equityOption" autoresize />
      </el-card>

      <div class="section-title"><el-icon><Bottom /></el-icon> 最大回撤曲线</div>
      <el-card shadow="never" class="chart-card">
        <v-chart class="chart" :option="drawdownOption" autoresize />
      </el-card>

      <div class="section-title"><el-icon><Histogram /></el-icon> 日收益率分布</div>
      <el-card shadow="never" class="chart-card">
        <v-chart class="chart" :option="returnsOption" autoresize />
      </el-card>

      <!-- 风险分析面板（激活 RiskManager）-->
      <template v-if="riskReport">
        <div class="section-title"><el-icon><Warning /></el-icon> 风险分析</div>
        <el-card shadow="never" class="risk-card">
          <el-row :gutter="12">
            <el-col :xs="12" :sm="8" :md="6">
              <div class="risk-item">
                <div class="risk-label">历史 VaR (95%)</div>
                <div class="risk-value v-danger">{{ currencyLabel }} {{ riskReport.var_analysis.historical_var.toFixed(2) }}</div>
              </div>
            </el-col>
            <el-col :xs="12" :sm="8" :md="6">
              <div class="risk-item">
                <div class="risk-label">参数 VaR (95%)</div>
                <div class="risk-value v-danger">{{ currencyLabel }} {{ riskReport.var_analysis.parametric_var.toFixed(2) }}</div>
              </div>
            </el-col>
            <el-col :xs="12" :sm="8" :md="6">
              <div class="risk-item">
                <div class="risk-label">CVaR (95%)</div>
                <div class="risk-value v-danger">{{ currencyLabel }} {{ riskReport.var_analysis.cvar.toFixed(2) }}</div>
              </div>
            </el-col>
            <el-col :xs="12" :sm="8" :md="6">
              <div class="risk-item">
                <div class="risk-label">年化波动率</div>
                <div class="risk-value">{{ (riskReport.volatility * 100).toFixed(2) }}%</div>
              </div>
            </el-col>
            <el-col :xs="12" :sm="8" :md="6">
              <div class="risk-item">
                <div class="risk-label">当前回撤</div>
                <div class="risk-value v-danger">{{ (riskReport.current_drawdown * 100).toFixed(2) }}%</div>
              </div>
            </el-col>
            <el-col :xs="12" :sm="8" :md="6">
              <div class="risk-item">
                <div class="risk-label">回撤上限</div>
                <div class="risk-value">{{ (riskReport.max_drawdown_limit * 100).toFixed(1) }}%</div>
              </div>
            </el-col>
          </el-row>

          <div class="stress-title">压力测试场景（基准 VaR：{{ currencyLabel }} {{ stressRows.length ? stressRows[0].value.toFixed(2) : '0.00' }}）</div>
          <el-table :data="stressRows" stripe size="small" style="width: 100%">
            <el-table-column prop="scenario" label="场景" />
            <el-table-column label="VaR（元）">
              <template #default="{ row }">{{ row.value.toFixed(2) }}</template>
            </el-table-column>
          </el-table>
        </el-card>
      </template>
    </template>

    <el-empty v-else-if="!loading" description="运行回测后在此查看动态绩效图表" />
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
