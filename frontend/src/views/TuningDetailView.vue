<script setup lang="ts">
/**
 * TuningDetailView —— 参数调优任务详情（/tuning/:taskId）。
 * 头部任务信息 + 归一化净值对比（每组 / 首值，基准加粗）+ 组合表
 * （参数/指标/应用此参数）。任务非终态时每 3s 轮询；apply 只写策略参数
 * （code→DB 参数列 / template→strategies.json），源码永不改动。
 */
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { tuningApi } from '@/api'
import type { TuningCombo, TuningTask } from '@/api/types'
import { chartPalette } from '@/lib/marketColors'
import { t } from '@/locales'
import { VChart } from '@/composables/useECharts'

const route = useRoute()
const router = useRouter()
const taskId = computed(() => Number(route.params.taskId))

const loading = ref(false)
const task = ref<TuningTask | null>(null)
let pollTimer: ReturnType<typeof setTimeout> | null = null

const isActive = computed(() => !!task.value && (task.value.status === 'queued' || task.value.status === 'running'))

async function load(silent = false) {
  if (!silent) loading.value = true
  try {
    task.value = await tuningApi.detail(taskId.value)
    if (isActive.value) schedulePoll()
  } catch (e) {
    if (!silent) ElMessage.error((e as Error).message || t('tuning.loadFailed'))
  } finally {
    if (!silent) loading.value = false
  }
}

function schedulePoll() {
  if (pollTimer) clearTimeout(pollTimer)
  pollTimer = setTimeout(() => void load(true), 3000)
}

// ---- 归一化净值对比 ----
const compareOption = computed(() => {
  const taskVal = task.value
  if (!taskVal?.combos?.length) return {}
  const succeeded = taskVal.combos.filter((c) => c.status === 'succeeded' && (c.equity_curve?.length ?? 0) > 1)
  if (!succeeded.length) return {}
  // x 轴取基准（缺则首个成功组合）的日期
  const base = succeeded.find((c) => c.is_baseline) ?? succeeded[0]
  const dates = base.dates ?? []
  const palette = chartPalette(taskVal.market)
  const series = succeeded.map((c) => {
    const eq = c.equity_curve ?? []
    const first = eq[0] || 1
    const isBaseline = c.is_baseline
    const isBest = c.combo_index === taskVal!.best_combo_index
    return {
      name: comboName(c),
      type: 'line' as const,
      data: eq.map((v) => Number((v / first).toFixed(6))),
      showSymbol: false,
      lineStyle: {
        width: isBaseline || isBest ? 2.2 : 1,
        color: isBaseline ? '#909399' : isBest ? palette.up : '#c0c4cc',
        opacity: isBaseline || isBest || succeeded.length <= 8 ? 1 : 0.55,
      },
    }
  })
  return {
    tooltip: { trigger: 'axis', valueFormatter: (v: number) => v?.toFixed(4) },
    legend: succeeded.length <= 10 ? { top: 0, type: 'scroll' } : { show: false },
    grid: { left: 60, right: 24, top: succeeded.length <= 10 ? 36 : 24, bottom: 52 },
    xAxis: { type: 'category', data: dates },
    yAxis: { type: 'value', scale: true, axisLabel: { formatter: (v: number) => v.toFixed(2) } },
    dataZoom: [{ type: 'inside' }, { type: 'slider' }],
    series,
  }
})

function comboName(c: TuningCombo): string {
  const prefix = c.is_baseline ? `${t('tuning.baseline')} #${c.combo_index}` : `#${c.combo_index}`
  return `${prefix} · ${gridParams(c)}`
}

function gridParams(c: TuningCombo): string {
  return (task.value?.grid_keys ?? [])
    .filter((k) => k in c.params)
    .map((k) => `${k}=${c.params[k]}`)
    .join(', ')
}

// ---- 应用参数 ----
const applying = ref<Set<number>>(new Set())

async function applyCombo(c: TuningCombo) {
  const paramsText = gridParams(c)
  try {
    await ElMessageBox.confirm(
      t('tuning.table.applyConfirm', { params: paramsText }),
      t('tuning.title'),
      { type: 'warning' },
    )
  } catch {
    return
  }
  applying.value.add(c.combo_index)
  try {
    await tuningApi.apply(taskId.value, c.combo_index)
    ElMessage.success(t('tuning.table.applied'))
  } catch (e) {
    ElMessage.error((e as Error).message || t('tuning.table.applyFailed'))
  } finally {
    applying.value.delete(c.combo_index)
  }
}

// ---- 展示助手 ----
function statusTag(s: string): string {
  const map: Record<string, string> = {
    queued: 'info', running: 'primary', succeeded: 'success', failed: 'danger', cancelled: 'warning',
  }
  return map[s] ?? 'info'
}
function fmtPct(v: number | null | undefined): string {
  if (v === null || v === undefined) return '—'
  return (v * 100).toFixed(2) + '%'
}
function fmtNum(v: number | null | undefined, nd = 2): string {
  if (v === null || v === undefined) return '—'
  return Number(v).toFixed(nd)
}
function fmtDuration(ms: number | null | undefined): string {
  if (!ms && ms !== 0) return '—'
  return ms >= 1000 ? (ms / 1000).toFixed(1) + 's' : ms + 'ms'
}
function rowClass({ row }: { row: TuningCombo }): string {
  return row.combo_index === task.value?.best_combo_index ? 'best-row' : ''
}

function comboMetrics(c: TuningCombo) {
  return c.metrics ?? null
}

function strategyPath(): string {
  const tk = task.value
  return tk?.strategy_kind === 'code' && tk.strategy_id ? `/strategy-library/${tk.strategy_id}` : '/strategies'
}

onMounted(() => void load())
onBeforeUnmount(() => {
  if (pollTimer) clearTimeout(pollTimer)
})
</script>

<template>
  <div v-loading="loading" class="tuning-page">
    <div class="page-head">
      <div class="head-left">
        <el-button text @click="task?.strategy_kind === 'code' && task?.strategy_id ? router.push(strategyPath()) : router.push('/strategies')">
          <el-icon><Back /></el-icon> {{ t('tuning.backToStrategy') }}
        </el-button>
        <h2 class="page-title">
          {{ t('tuning.taskOf', { name: task?.strategy_name ?? '' }) }}
          <el-tag v-if="task" size="small" :type="statusTag(task.status)">{{ t(`common.status.${task.status}`) }}</el-tag>
          <el-tag v-if="task?.best_combo_index !== null && task?.best_combo_index !== undefined" size="small" type="success">
            {{ t('tuning.best') }} #{{ task.best_combo_index }}
          </el-tag>
        </h2>
      </div>
    </div>

    <template v-if="task">
      <div class="info-bar">
        <el-tag size="small" type="info">{{ task.market === 'us' ? 'US' : 'A股' }}</el-tag>
        <span>{{ t('tuning.head.stock') }}: {{ task.stock_code }}</span>
        <span>{{ t('tuning.head.range') }}: {{ task.start_date }} ~ {{ task.end_date }}</span>
        <span>{{ t('tuning.head.targetMetric') }}: {{ t(`backtest.metric.${task.target_metric}`) }}</span>
        <span>{{ t('tuning.head.capital') }}: ¥{{ Number(task.initial_capital).toLocaleString() }}</span>
        <span v-if="task.duration_ms">{{ t('tuning.head.duration') }}: {{ fmtDuration(task.duration_ms) }}</span>
        <span class="progress-cell">
          <el-progress
            :percentage="task.total_combos ? Math.round((task.done_combos / task.total_combos) * 100) : 0"
            :stroke-width="8"
            :status="task.status === 'succeeded' ? 'success' : task.status === 'failed' ? 'exception' : undefined"
            class="progress-bar"
          />
          <span class="progress-text">{{ t('tuning.head.combos') }} {{ task.done_combos }}/{{ task.total_combos }}</span>
        </span>
      </div>
      <el-alert v-if="task.error" type="error" :title="task.error" :closable="false" class="task-error" />

      <el-card shadow="never" class="chart-card">
        <template #header>{{ t('tuning.chartTitle') }}</template>
        <v-chart v-if="Object.keys(compareOption).length" :option="compareOption" autoresize class="compare-chart" />
        <el-empty v-else :description="t('common.noData')" :image-size="72" />
      </el-card>

      <el-table :data="task.combos ?? []" size="small" class="combo-table" :row-class-name="rowClass">
        <el-table-column prop="combo_index" :label="t('tuning.table.index')" width="56" />
        <el-table-column :label="t('tuning.table.params')" min-width="220">
          <template #default="{ row }">
            <el-tag v-if="row.is_baseline" size="small" type="info" class="param-tag">{{ t('tuning.baseline') }}</el-tag>
            <el-tag v-else-if="row.combo_index === task.best_combo_index" size="small" type="success" class="param-tag">{{ t('tuning.best') }}</el-tag>
            <span class="param-text">{{ gridParams(row) }}</span>
          </template>
        </el-table-column>
        <el-table-column :label="t('backtest.metric.总收益率')" width="106">
          <template #default="{ row }">{{ comboMetrics(row) ? fmtPct(comboMetrics(row)!['总收益率']) : '—' }}</template>
        </el-table-column>
        <el-table-column :label="t('backtest.metric.夏普比率')" width="96">
          <template #default="{ row }">{{ comboMetrics(row) ? fmtNum(comboMetrics(row)!['夏普比率']) : '—' }}</template>
        </el-table-column>
        <el-table-column :label="t('backtest.metric.最大回撤')" width="106">
          <template #default="{ row }">{{ comboMetrics(row) ? fmtPct(comboMetrics(row)!['最大回撤']) : '—' }}</template>
        </el-table-column>
        <el-table-column :label="t('tuning.table.status')" width="96">
          <template #default="{ row }">
            <el-tooltip v-if="row.status === 'failed' && row.error" :content="row.error" placement="top">
              <el-tag size="small" :type="statusTag(row.status)">{{ t(`common.status.${row.status}`) }}</el-tag>
            </el-tooltip>
            <el-tag v-else size="small" :type="statusTag(row.status)">{{ t(`common.status.${row.status}`) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column :label="t('tuning.table.duration')" width="88">
          <template #default="{ row }">{{ fmtDuration(row.duration_ms) }}</template>
        </el-table-column>
        <el-table-column :label="t('tuning.table.action')" width="120" fixed="right">
          <template #default="{ row }">
            <el-button
              text
              size="small"
              type="primary"
              :disabled="row.status !== 'succeeded' || isActive"
              :loading="applying.has(row.combo_index)"
              @click="applyCombo(row)"
            >
              {{ t('tuning.table.apply') }}
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </template>
  </div>
</template>

<style scoped>
.tuning-page {
  padding: 4px 4px 24px;
}
.page-head {
  margin-bottom: 10px;
}
.page-title {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 6px 0 4px;
  font-size: 20px;
}
.info-bar {
  display: flex;
  flex-wrap: wrap;
  gap: 14px;
  align-items: center;
  margin-bottom: 10px;
  font-size: 13px;
  color: var(--el-text-color-regular);
}
.progress-cell {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 220px;
}
.progress-bar {
  width: 130px;
}
.progress-text {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  white-space: nowrap;
}
.task-error {
  margin-bottom: 10px;
}
.chart-card {
  margin-bottom: 12px;
}
.compare-chart {
  width: 100%;
  height: 340px;
}
.combo-table :deep(.best-row) {
  background: var(--el-color-success-light-9);
}
.param-tag {
  margin-right: 6px;
}
.param-text {
  font-family: monospace;
  font-size: 12px;
}
</style>
