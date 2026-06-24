<script setup lang="ts">
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { backtestApi, strategyApi } from '@/api'
import type { BacktestRequest, BacktestResult, Market, StrategyDetail } from '@/api/types'
import { VChart } from '@/composables/useECharts'

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
  ]
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
</script>

<template>
  <div>
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
</style>
