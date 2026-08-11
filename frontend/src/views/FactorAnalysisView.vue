<script setup lang="ts">
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { factorApi } from '@/api'
import type { FactorAnalysisRequest, FactorAnalysisResult, FactorType } from '@/api/types'
import { VChart } from '@/composables/useECharts'

const loading = ref(false)
const result = ref<FactorAnalysisResult | null>(null)

const form = ref<FactorAnalysisRequest>({
  factor_type: 'momentum',
  start_date: '2024-01-01',
  end_date: '2024-12-31',
  universe: 'hs300',
  n_quantiles: 5,
  forward_period: 5,
})

const factorOptions: { label: string; value: FactorType; desc: string }[] = [
  { label: '动量 (20日收益)', value: 'momentum', desc: '过去 20 个交易日收益率' },
  { label: 'RSI (14)', value: 'rsi', desc: '14 日相对强弱指标' },
  { label: '波动率 (20日)', value: 'volatility', desc: '20 日日收益标准差' },
  { label: '成交量比', value: 'volume_ratio', desc: '当日量 / 20 日均量' },
]

async function runAnalysis() {
  loading.value = true
  result.value = null
  try {
    result.value = await factorApi.analyze(form.value)
    if (result.value.error) {
      ElMessage.error(result.value.error)
      result.value = null
    } else {
      ElMessage.success('因子分析完成')
    }
  } catch (e: any) {
    ElMessage.error('分析失败：' + e.message)
  } finally {
    loading.value = false
  }
}

// IC 时序图
const icOption = computed(() => {
  if (!result.value || !result.value.ic_series.length) return {}
  const dates = result.value.ic_series.map((d) => d.date)
  return {
    tooltip: { trigger: 'axis' },
    legend: { top: 0, data: ['IC', 'Rank IC'] },
    grid: { left: 50, right: 30, top: 40, bottom: 60 },
    xAxis: { type: 'category', data: dates },
    yAxis: { type: 'value', name: 'IC' },
    dataZoom: [{ type: 'inside' }, { type: 'slider' }],
    series: [
      { name: 'IC', type: 'bar', data: result.value.ic_series.map((d) => d.ic) },
      { name: 'Rank IC', type: 'line', showSymbol: false, data: result.value.ic_series.map((d) => d.rank_ic) },
    ],
  }
})

// 分层累计收益曲线
const quantOption = computed(() => {
  const r = result.value
  if (!r || !r.quantile_cumreturns.length) return {}
  const dates = r.quantile_cumreturns.map((d) => d.date)
  const labels = r.quantile_labels
  const series = labels.map((label, i) => ({
    name: label,
    type: 'line',
    showSymbol: false,
    data: r.quantile_cumreturns.map((d) => d.values[i]),
  }))
  return {
    tooltip: { trigger: 'axis' },
    legend: { top: 0 },
    grid: { left: 50, right: 30, top: 40, bottom: 60 },
    xAxis: { type: 'category', data: dates },
    yAxis: { type: 'value', name: '累计净值' },
    dataZoom: [{ type: 'inside' }, { type: 'slider' }],
    series,
  }
})

// IC 概览卡片
const icCards = computed(() => {
  if (!result.value) return []
  const s = result.value.ic_stats
  const fmt = (v: number | null | undefined, nd = 4) =>
    v === null || v === undefined ? '—' : v.toFixed(nd)
  return [
    { label: 'IC 均值', value: fmt(s.ic_mean) },
    { label: 'Rank IC 均值', value: fmt(s.rank_ic_mean) },
    { label: 'ICIR', value: fmt(s.ic_ir) },
    { label: 'Rank ICIR', value: fmt(s.rank_ic_ir) },
    { label: 'IC 胜率', value: fmt(s.ic_win_rate) },
    { label: 'IC 正率', value: fmt(s.ic_positive_rate) },
  ]
})
</script>

<template>
  <div class="page">
    <div class="page-hero">
      <h1><el-icon><DataAnalysis /></el-icon> 因子分析</h1>
      <p class="subtitle">在沪深300成分股上做多因子 IC/分层分析（对标 Qlib 多因子框架）</p>
    </div>

    <el-card shadow="never" class="form-card" v-loading="loading">
      <el-form :model="form" label-width="100px" label-position="right">
        <el-form-item label="因子类型">
          <el-select v-model="form.factor_type" style="width: 100%">
            <el-option
              v-for="f in factorOptions"
              :key="f.value"
              :label="f.label"
              :value="f.value"
            />
          </el-select>
        </el-form-item>
        <el-row :gutter="20">
          <el-col :xs="12" :md="6">
            <el-form-item label="开始日期">
              <el-input v-model="form.start_date" placeholder="2024-01-01" />
            </el-form-item>
          </el-col>
          <el-col :xs="12" :md="6">
            <el-form-item label="结束日期">
              <el-input v-model="form.end_date" placeholder="2024-12-31" />
            </el-form-item>
          </el-col>
          <el-col :xs="12" :md="6">
            <el-form-item label="分层数">
              <el-input-number v-model="form.n_quantiles" :min="2" :max="10" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :xs="12" :md="6">
            <el-form-item label="前瞻周期">
              <el-input-number v-model="form.forward_period" :min="1" :max="20" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item>
          <el-button type="primary" :loading="loading" @click="runAnalysis">
            <el-icon><DataAnalysis /></el-icon> 开始分析
          </el-button>
          <span class="hint">首次运行会拉取 HS300 全量数据，依赖数据库缓存；请耐心等待</span>
        </el-form-item>
      </el-form>
    </el-card>

    <template v-if="result">
      <div class="section-title"><el-icon><DataLine /></el-icon> IC 概览</div>
      <el-row :gutter="12" class="metrics-row">
        <el-col v-for="c in icCards" :key="c.label" :xs="8" :sm="4">
          <div class="metric-card">
            <div class="metric-label">{{ c.label }}</div>
            <div class="metric-value">{{ c.value }}</div>
          </div>
        </el-col>
      </el-row>
      <div class="meta">
        股票池规模：{{ result.universe_size }} 只 · 单调性：
        <el-tag :type="result.monotonicity.monotonic ? 'success' : 'info'" size="small">
          {{ result.monotonicity.monotonic ? '单调 ✓' : '非单调' }}
        </el-tag>
        （比率 {{ result.monotonicity.monotonicity_ratio ?? '—' }}）
      </div>

      <div class="section-title"><el-icon><TrendCharts /></el-icon> IC 时序</div>
      <el-card shadow="never" class="chart-card">
        <v-chart class="chart" :option="icOption" autoresize />
      </el-card>

      <div class="section-title"><el-icon><DataLine /></el-icon> 分层累计收益</div>
      <el-card shadow="never" class="chart-card">
        <v-chart class="chart" :option="quantOption" autoresize />
      </el-card>

      <div class="section-title"><el-icon><DataAnalysis /></el-icon> 分层统计</div>
      <el-card shadow="never">
        <el-table :data="result.quantile_stats" stripe style="width: 100%">
          <el-table-column prop="quantile" label="分层" />
          <el-table-column label="平均收益">
            <template #default="{ row }">{{ row.mean_return == null ? '—' : (row.mean_return * 100).toFixed(4) + '%' }}</template>
          </el-table-column>
          <el-table-column label="夏普">
            <template #default="{ row }">{{ row.sharpe_ratio == null ? '—' : row.sharpe_ratio.toFixed(4) }}</template>
          </el-table-column>
          <el-table-column label="胜率">
            <template #default="{ row }">{{ row.win_rate == null ? '—' : (row.win_rate * 100).toFixed(2) + '%' }}</template>
          </el-table-column>
        </el-table>
      </el-card>
    </template>
    <el-empty v-else-if="!loading" description="选择因子类型后开始分析" />
  </div>
</template>

<style scoped>
.page {
  max-width: 1200px;
  margin: 0 auto;
}
.form-card,
.chart-card {
  border-radius: var(--radius);
  margin-bottom: 1.25rem;
}
.hint {
  color: var(--text-muted);
  margin-left: 12px;
  font-size: 0.85rem;
}
.chart {
  height: 380px;
  width: 100%;
}
.metrics-row {
  margin-bottom: 0.5rem;
}
.metric-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 12px 8px;
  text-align: center;
  margin-bottom: 12px;
  border-top: 3px solid var(--brand-start);
}
.metric-label {
  color: var(--text-muted);
  font-size: 0.82rem;
  margin-bottom: 4px;
}
.metric-value {
  font-size: 1.2rem;
  font-weight: 700;
}
.meta {
  color: var(--text-muted);
  margin-bottom: 1.25rem;
  font-size: 0.9rem;
}
</style>
