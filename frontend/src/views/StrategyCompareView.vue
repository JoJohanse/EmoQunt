<script setup lang="ts">
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { compareApi, strategyApi } from '@/api'
import type { CompareResult, StrategyDetail, Market } from '@/api/types'
import { VChart } from '@/composables/useECharts'

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
    ElMessage.warning('策略列表加载失败：' + e.message)
  }
})()

const stockHint = computed(() =>
  form.value.market === 'us'
    ? '美股字母代码，如 AAPL'
    : '不带前缀的 6 位 A 股代码',
)

function onMarketChange() {
  form.value.stock_code = form.value.market === 'us' ? 'AAPL' : '000001'
  form.value.commission_rate = form.value.market === 'us' ? 0.0005 : 0.0003
}

async function runCompare() {
  if (form.value.strategy_names.length < 2) {
    ElMessage.warning('请至少选择 2 个策略进行对比')
    return
  }
  if (form.value.strategy_names.length > 5) {
    ElMessage.warning('最多对比 5 个策略')
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
      ElMessage.success('对比完成')
    }
  } catch (e: any) {
    ElMessage.error('对比失败：' + e.message)
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
    yAxis: { type: 'value', name: '净值' },
    dataZoom: [{ type: 'inside' }, { type: 'slider' }],
    series,
  }
})

// 对比指标表
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
      <h1><el-icon><DataLine /></el-icon> 策略对比</h1>
      <p class="subtitle">选择 2-5 个策略，在同一标的上对比净值曲线与绩效指标</p>
    </div>

    <el-card shadow="never" class="form-card" v-loading="loading">
      <el-form :model="form" label-width="100px" label-position="right">
        <el-form-item label="市场">
          <el-radio-group v-model="form.market" @change="onMarketChange">
            <el-radio-button value="zh_a">A 股</el-radio-button>
            <el-radio-button value="us">美股</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="选择策略">
          <el-select
            v-model="form.strategy_names"
            multiple
            :multiple-limit="5"
            placeholder="选择 2-5 个策略"
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
            <el-form-item label="股票代码">
              <el-input v-model="form.stock_code" :placeholder="stockHint" />
            </el-form-item>
          </el-col>
          <el-col :xs="12" :md="6">
            <el-form-item label="初始资金">
              <el-input-number v-model="form.initial_capital" :min="1000" style="width: 100%" />
            </el-form-item>
          </el-col>
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
        </el-row>
        <el-form-item>
          <el-button type="primary" :loading="loading" @click="runCompare">
            <el-icon><TrendCharts /></el-icon> 开始对比
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <template v-if="result">
      <div class="section-title"><el-icon><TrendCharts /></el-icon> 净值曲线对比</div>
      <el-card shadow="never" class="chart-card">
        <v-chart class="chart" :option="equityOption" autoresize />
      </el-card>

      <div class="section-title"><el-icon><DataAnalysis /></el-icon> 绩效指标对比</div>
      <el-card shadow="never">
        <el-table :data="tableRows" stripe style="width: 100%">
          <el-table-column prop="name" label="策略" />
          <el-table-column prop="总收益率" label="总收益率" />
          <el-table-column prop="年化收益率" label="年化收益率" />
          <el-table-column prop="夏普比率" label="夏普比率" />
          <el-table-column prop="最大回撤" label="最大回撤" />
          <el-table-column prop="胜率" label="胜率" />
          <el-table-column prop="盈亏比" label="盈亏比" />
          <el-table-column prop="Alpha" label="Alpha" />
          <el-table-column prop="Beta" label="Beta" />
        </el-table>
      </el-card>

      <div v-if="result.errors?.length" class="errors">
        <el-alert
          v-for="(e, i) in result.errors"
          :key="i"
          :title="`策略 ${e.name} 失败：${e.error}`"
          type="warning"
          :closable="false"
          style="margin-bottom: 6px"
        />
      </div>
    </template>
    <el-empty v-else-if="!loading" description="选择多个策略后在此查看对比结果" />
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
