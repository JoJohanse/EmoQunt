<script setup lang="ts">
/**
 * FactorAnalysisPanel —— 因子横截面分析结果展示（IC 概览 + IC 时序 +
 * 分层累计收益 + 分层统计表）。因子库详情页与旧因子分析页共用；
 * 数据契约 = services/factor.py 的 JSON 序列化出口（FactorAnalysisResult）。
 * 文案住 factorlib.panel.*。
 */
import { computed } from 'vue'
import type { FactorAnalysisResult } from '@/api/types'
import { t } from '@/locales'
import { VChart } from '@/composables/useECharts'

const props = defineProps<{
  result: FactorAnalysisResult
}>()

// IC 时序图（IC 柱 + Rank IC 线）
const icOption = computed(() => {
  const r = props.result
  if (!r || !r.ic_series.length) return {}
  const dates = r.ic_series.map((d) => d.date)
  return {
    tooltip: { trigger: 'axis' },
    legend: { top: 0, data: ['IC', 'Rank IC'] },
    grid: { left: 50, right: 30, top: 40, bottom: 60 },
    xAxis: { type: 'category', data: dates },
    yAxis: { type: 'value', name: 'IC' },
    dataZoom: [{ type: 'inside' }, { type: 'slider' }],
    series: [
      { name: 'IC', type: 'bar', data: r.ic_series.map((d) => d.ic) },
      { name: 'Rank IC', type: 'line', showSymbol: false, data: r.ic_series.map((d) => d.rank_ic) },
    ],
  }
})

// 分层累计收益曲线
const quantOption = computed(() => {
  const r = props.result
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
    yAxis: { type: 'value', name: t('factorlib.panel.cumNavAxis') },
    dataZoom: [{ type: 'inside' }, { type: 'slider' }],
    series,
  }
})

// IC 概览卡片（标签随语言切换重算）
const icCards = computed(() => {
  const s = props.result.ic_stats
  const fmt = (v: number | null | undefined, nd = 4) =>
    v === null || v === undefined ? '—' : v.toFixed(nd)
  return [
    { label: t('factorlib.panel.icMean'), value: fmt(s.ic_mean) },
    { label: t('factorlib.panel.rankIcMean'), value: fmt(s.rank_ic_mean) },
    { label: t('factorlib.panel.icir'), value: fmt(s.ic_ir) },
    { label: t('factorlib.panel.rankIcir'), value: fmt(s.rank_ic_ir) },
    { label: t('factorlib.panel.icWinRate'), value: fmt(s.ic_win_rate) },
    { label: t('factorlib.panel.icPositiveRate'), value: fmt(s.ic_positive_rate) },
  ]
})

function fmtPct(v: number | null | undefined, nd = 2): string {
  if (v === null || v === undefined) return '—'
  return (v * 100).toFixed(nd) + '%'
}
function fmtNum(v: number | null | undefined, nd = 4): string {
  if (v === null || v === undefined) return '—'
  return Number(v).toFixed(nd)
}
</script>

<template>
  <div>
    <div class="section-title">{{ t('factorlib.panel.icOverview') }}</div>
    <el-row :gutter="12" class="metrics-row">
      <el-col v-for="c in icCards" :key="c.label" :xs="8" :sm="4">
        <div class="metric-card">
          <div class="metric-label">{{ c.label }}</div>
          <div class="metric-value">{{ c.value }}</div>
        </div>
      </el-col>
    </el-row>
    <div class="meta">
      {{ t('factorlib.panel.universe', { n: result.universe_size }) }} ·
      {{ t('factorlib.panel.monotonicity') }}
      <el-tag :type="result.monotonicity.monotonic ? 'success' : 'info'" size="small">
        {{ result.monotonicity.monotonic ? t('factorlib.panel.monotonic') : t('factorlib.panel.notMonotonic') }}
      </el-tag>
      {{ t('factorlib.panel.ratio', { ratio: result.monotonicity.monotonicity_ratio ?? '—' }) }}
    </div>

    <div class="section-title">{{ t('factorlib.panel.icSeries') }}</div>
    <el-card shadow="never" class="chart-card">
      <v-chart class="chart" :option="icOption" autoresize />
    </el-card>

    <div class="section-title">{{ t('factorlib.panel.quantileCumReturns') }}</div>
    <el-card shadow="never" class="chart-card">
      <v-chart class="chart" :option="quantOption" autoresize />
    </el-card>

    <div class="section-title">{{ t('factorlib.panel.quantileStats') }}</div>
    <el-card shadow="never">
      <el-table :data="result.quantile_stats" stripe style="width: 100%">
        <el-table-column prop="quantile" :label="t('factorlib.panel.quantile')" />
        <el-table-column :label="t('factorlib.panel.meanReturn')">
          <template #default="{ row }">{{ fmtPct(row.mean_return, 4) }}</template>
        </el-table-column>
        <el-table-column :label="t('factorlib.panel.sharpe')">
          <template #default="{ row }">{{ fmtNum(row.sharpe_ratio) }}</template>
        </el-table-column>
        <el-table-column :label="t('factorlib.panel.winRate')">
          <template #default="{ row }">{{ fmtPct(row.win_rate) }}</template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<style scoped>
.chart-card {
  margin-bottom: 1.25rem;
}
.chart {
  height: 380px;
  width: 100%;
}
.section-title {
  font-weight: 600;
  margin: 1.25rem 0 0.75rem;
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
