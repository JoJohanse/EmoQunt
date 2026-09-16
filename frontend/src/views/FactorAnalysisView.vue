<script setup lang="ts">
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { factorApi } from '@/api'
import type { FactorAnalysisRequest, FactorAnalysisResult, FactorType } from '@/api/types'
import { VChart } from '@/composables/useECharts'
import { t } from '@/locales'

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

// 因子下拉项（computed 内读 t()，切换语言即重算）
const factorOptions = computed<{ label: string; value: FactorType; desc: string }[]>(() => [
  { label: t('factor.type.momentum'), value: 'momentum', desc: t('factor.type.momentumDesc') },
  { label: t('factor.type.rsi'), value: 'rsi', desc: t('factor.type.rsiDesc') },
  { label: t('factor.type.volatility'), value: 'volatility', desc: t('factor.type.volatilityDesc') },
  { label: t('factor.type.volumeRatio'), value: 'volume_ratio', desc: t('factor.type.volumeRatioDesc') },
])

async function runAnalysis() {
  loading.value = true
  result.value = null
  try {
    result.value = await factorApi.analyze(form.value)
    if (result.value.error) {
      ElMessage.error(result.value.error)
      result.value = null
    } else {
      ElMessage.success(t('factor.done'))
    }
  } catch (e: any) {
    ElMessage.error(t('factor.failed') + e.message)
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
    yAxis: { type: 'value', name: t('factor.chart.cumNavAxis') },
    dataZoom: [{ type: 'inside' }, { type: 'slider' }],
    series,
  }
})

// IC 概览卡片（标签随语言切换重算）
const icCards = computed(() => {
  if (!result.value) return []
  const s = result.value.ic_stats
  const fmt = (v: number | null | undefined, nd = 4) =>
    v === null || v === undefined ? '—' : v.toFixed(nd)
  return [
    { label: t('factor.cards.icMean'), value: fmt(s.ic_mean) },
    { label: t('factor.cards.rankIcMean'), value: fmt(s.rank_ic_mean) },
    { label: t('factor.cards.icir'), value: fmt(s.ic_ir) },
    { label: t('factor.cards.rankIcir'), value: fmt(s.rank_ic_ir) },
    { label: t('factor.cards.icWinRate'), value: fmt(s.ic_win_rate) },
    { label: t('factor.cards.icPositiveRate'), value: fmt(s.ic_positive_rate) },
  ]
})
</script>

<template>
  <div class="page">
    <div class="page-hero">
      <h1><el-icon><DataAnalysis /></el-icon> {{ t('factor.title') }}</h1>
      <p class="subtitle">{{ t('factor.subtitle') }}</p>
    </div>

    <el-card shadow="never" class="form-card" v-loading="loading">
      <el-form :model="form" label-width="100px" label-position="right">
        <el-form-item :label="t('factor.form.factorType')">
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
            <el-form-item :label="t('factor.form.startDate')">
              <el-input v-model="form.start_date" placeholder="2024-01-01" />
            </el-form-item>
          </el-col>
          <el-col :xs="12" :md="6">
            <el-form-item :label="t('factor.form.endDate')">
              <el-input v-model="form.end_date" placeholder="2024-12-31" />
            </el-form-item>
          </el-col>
          <el-col :xs="12" :md="6">
            <el-form-item :label="t('factor.form.quantiles')">
              <el-input-number v-model="form.n_quantiles" :min="2" :max="10" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :xs="12" :md="6">
            <el-form-item :label="t('factor.form.forwardPeriod')">
              <el-input-number v-model="form.forward_period" :min="1" :max="20" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item>
          <el-button type="primary" :loading="loading" @click="runAnalysis">
            <el-icon><DataAnalysis /></el-icon> {{ t('factor.run') }}
          </el-button>
          <span class="hint">{{ t('factor.form.hint') }}</span>
        </el-form-item>
      </el-form>
    </el-card>

    <template v-if="result">
      <div class="section-title"><el-icon><DataLine /></el-icon> {{ t('factor.section.icOverview') }}</div>
      <el-row :gutter="12" class="metrics-row">
        <el-col v-for="c in icCards" :key="c.label" :xs="8" :sm="4">
          <div class="metric-card">
            <div class="metric-label">{{ c.label }}</div>
            <div class="metric-value">{{ c.value }}</div>
          </div>
        </el-col>
      </el-row>
      <div class="meta">
        {{ t('factor.meta.universe', { n: result.universe_size }) }} ·
        {{ t('factor.meta.monotonicity') }}
        <el-tag :type="result.monotonicity.monotonic ? 'success' : 'info'" size="small">
          {{ result.monotonicity.monotonic ? t('factor.meta.monotonic') : t('factor.meta.notMonotonic') }}
        </el-tag>
        {{ t('factor.meta.ratio', { ratio: result.monotonicity.monotonicity_ratio ?? '—' }) }}
      </div>

      <div class="section-title"><el-icon><TrendCharts /></el-icon> {{ t('factor.section.icSeries') }}</div>
      <el-card shadow="never" class="chart-card">
        <v-chart class="chart" :option="icOption" autoresize />
      </el-card>

      <div class="section-title"><el-icon><DataLine /></el-icon> {{ t('factor.section.quantileCumReturns') }}</div>
      <el-card shadow="never" class="chart-card">
        <v-chart class="chart" :option="quantOption" autoresize />
      </el-card>

      <div class="section-title"><el-icon><DataAnalysis /></el-icon> {{ t('factor.section.quantileStats') }}</div>
      <el-card shadow="never">
        <el-table :data="result.quantile_stats" stripe style="width: 100%">
          <el-table-column prop="quantile" :label="t('factor.table.quantile')" />
          <el-table-column :label="t('factor.table.meanReturn')">
            <template #default="{ row }">{{ row.mean_return == null ? '—' : (row.mean_return * 100).toFixed(4) + '%' }}</template>
          </el-table-column>
          <el-table-column :label="t('factor.table.sharpe')">
            <template #default="{ row }">{{ row.sharpe_ratio == null ? '—' : row.sharpe_ratio.toFixed(4) }}</template>
          </el-table-column>
          <el-table-column :label="t('factor.table.winRate')">
            <template #default="{ row }">{{ row.win_rate == null ? '—' : (row.win_rate * 100).toFixed(2) + '%' }}</template>
          </el-table-column>
        </el-table>
      </el-card>
    </template>
    <el-empty v-else-if="!loading" :description="t('factor.empty')" />
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
