<script setup lang="ts">
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { compareApi, strategyApi } from '@/api'
import type { CompareResult, StrategyDetail, Market } from '@/api/types'
import { VChart } from '@/composables/useECharts'
import { t } from '@/locales'

const strategies = ref<StrategyDetail[]>([])
const loading = ref(false)
const result = ref<CompareResult | null>(null)

const form = ref({
  strategy_names: [] as string[],
  stock_code: '000001',
  start_date: '2024-01-01',
  end_date: '2024-12-31',
  initial_capital: 100000,
  commission_rate: 0.0003,
  market: 'zh_a' as Market,
})

;(async () => {
  try {
    strategies.value = await strategyApi.list()
  } catch (e: any) {
    ElMessage.warning(t('compare.loadStrategiesFailed') + e.message)
  }
})()

// A 股 / 美股代码格式提示（computed 内读 t()，切换语言即重算）
const stockHint = computed(() =>
  form.value.market === 'us' ? t('compare.form.hintUs') : t('compare.form.hintZhA'),
)

function onMarketChange() {
  form.value.stock_code = form.value.market === 'us' ? 'AAPL' : '000001'
  form.value.commission_rate = form.value.market === 'us' ? 0.0005 : 0.0003
}

async function runCompare() {
  if (form.value.strategy_names.length < 2) {
    ElMessage.warning(t('compare.needAtLeastTwo'))
    return
  }
  if (form.value.strategy_names.length > 5) {
    ElMessage.warning(t('compare.atMostFive'))
    return
  }
  loading.value = true
  result.value = null
  try {
    result.value = await compareApi.run(form.value)
    if (result.value.error) {
      ElMessage.error(result.value.error)
      result.value = null
    } else {
      ElMessage.success(t('compare.done'))
    }
  } catch (e: any) {
    ElMessage.error(t('compare.failed') + e.message)
  } finally {
    loading.value = false
  }
}

// 叠加净值曲线
const equityOption = computed(() => {
  if (!result.value || !result.value.series.length) return {}
  const r = result.value
  const series = r.series.map((s) => ({
    name: s.name,
    type: 'line',
    data: s.equity_curve,
    showSymbol: false,
    smooth: false,
  }))
  return {
    tooltip: { trigger: 'axis' },
    legend: { top: 0 },
    grid: { left: 50, right: 30, top: 40, bottom: 60 },
    xAxis: { type: 'category', data: r.dates },
    yAxis: { type: 'value', name: t('compare.chart.equityAxis') },
    dataZoom: [{ type: 'inside' }, { type: 'slider' }],
    series,
  }
})

// 对比指标表：行对象的键沿用后端指标的中文字段名（表格列 prop 与之一一对应），
// 中文键不参与 i18n——只有列头 label 走 t('compare.metric.<中文键>')
const tableRows = computed(() => {
  if (!result.value) return []
  const fmtPct = (v: number | null | undefined) =>
    v === null || v === undefined ? '—' : (v * 100).toFixed(2) + '%'
  const fmtNum = (v: number | null | undefined, nd = 2) =>
    v === null || v === undefined ? '—' : v.toFixed(nd)
  return result.value.series.map((s) => ({
    name: s.name,
    总收益率: fmtPct(s.metrics.总收益率),
    年化收益率: fmtPct(s.metrics.年化收益率),
    夏普比率: fmtNum(s.metrics.夏普比率),
    最大回撤: fmtPct(s.metrics.最大回撤),
    胜率: fmtPct(s.metrics.胜率),
    盈亏比: fmtNum(s.metrics.盈亏比),
    Alpha: fmtPct(s.metrics.Alpha ?? null),
    Beta: fmtNum(s.metrics.Beta ?? null),
  }))
})
</script>

<template>
  <div class="page">
    <div class="page-hero">
      <h1><el-icon><DataLine /></el-icon> {{ t('compare.title') }}</h1>
      <p class="subtitle">{{ t('compare.subtitle') }}</p>
    </div>

    <el-card shadow="never" class="form-card" v-loading="loading">
      <el-form :model="form" label-width="100px" label-position="right">
        <el-form-item :label="t('compare.form.market')">
          <el-radio-group v-model="form.market" @change="onMarketChange">
            <el-radio-button value="zh_a">{{ t('compare.market.zhA') }}</el-radio-button>
            <el-radio-button value="us">{{ t('compare.market.us') }}</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item :label="t('compare.form.strategies')">
          <el-select
            v-model="form.strategy_names"
            multiple
            :multiple-limit="5"
            :placeholder="t('compare.form.strategiesPlaceholder')"
            style="width: 100%"
          >
            <el-option
              v-for="s in strategies"
              :key="s.name"
              :label="s.name"
              :value="s.name"
            />
          </el-select>
        </el-form-item>
        <el-row :gutter="20">
          <el-col :xs="12" :md="6">
            <el-form-item :label="t('compare.form.stockCode')">
              <el-input v-model="form.stock_code" :placeholder="stockHint" />
            </el-form-item>
          </el-col>
          <el-col :xs="12" :md="6">
            <el-form-item :label="t('compare.form.initialCapital')">
              <el-input-number v-model="form.initial_capital" :min="1000" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :xs="12" :md="6">
            <el-form-item :label="t('compare.form.startDate')">
              <el-input v-model="form.start_date" placeholder="2024-01-01" />
            </el-form-item>
          </el-col>
          <el-col :xs="12" :md="6">
            <el-form-item :label="t('compare.form.endDate')">
              <el-input v-model="form.end_date" placeholder="2024-12-31" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item>
          <el-button type="primary" :loading="loading" @click="runCompare">
            <el-icon><TrendCharts /></el-icon> {{ t('compare.run') }}
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <template v-if="result">
      <div class="section-title"><el-icon><TrendCharts /></el-icon> {{ t('compare.section.equity') }}</div>
      <el-card shadow="never" class="chart-card">
        <v-chart class="chart" :option="equityOption" autoresize />
      </el-card>

      <div class="section-title"><el-icon><DataAnalysis /></el-icon> {{ t('compare.section.metrics') }}</div>
      <el-card shadow="never">
        <el-table :data="tableRows" stripe style="width: 100%">
          <el-table-column prop="name" :label="t('compare.table.strategy')" />
          <el-table-column prop="总收益率" :label="t('compare.metric.总收益率')" />
          <el-table-column prop="年化收益率" :label="t('compare.metric.年化收益率')" />
          <el-table-column prop="夏普比率" :label="t('compare.metric.夏普比率')" />
          <el-table-column prop="最大回撤" :label="t('compare.metric.最大回撤')" />
          <el-table-column prop="胜率" :label="t('compare.metric.胜率')" />
          <el-table-column prop="盈亏比" :label="t('compare.metric.盈亏比')" />
          <el-table-column prop="Alpha" label="Alpha" />
          <el-table-column prop="Beta" label="Beta" />
        </el-table>
      </el-card>

      <div v-if="result.errors?.length" class="errors">
        <el-alert
          v-for="(e, i) in result.errors"
          :key="i"
          :title="t('compare.strategyFailed', { name: e.name }) + e.error"
          type="warning"
          :closable="false"
          style="margin-bottom: 6px"
        />
      </div>
    </template>
    <el-empty v-else-if="!loading" :description="t('compare.empty')" />
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
.chart {
  height: 420px;
  width: 100%;
}
.errors {
  margin-top: 1rem;
}
</style>
