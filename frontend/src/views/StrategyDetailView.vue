<script setup lang="ts">
/**
 * StrategyDetailView —— 策略库代码策略详情：参数设置 / 策略代码 / 历史版本 / 回测历史。
 * 数据面：/api/v2/strategies/{id}（含源码）、/api/v2/backtest/runs（异步回测）。
 * 生效参数以 DB 参数列为真相（源码 STRATEGY_PARAMS 只是初始默认）。
 */
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { libraryApi, runsApi, tuningApi } from '@/api'
import type {
  BacktestRunDetail,
  BacktestRunSummary,
  CodeStrategyDetail,
  StrategyVersion,
  TuningTask,
} from '@/api/types'
import { chartPalette } from '@/lib/marketColors'
import { t } from '@/locales'
import CodeEditor from '@/components/CodeEditor.vue'
import RunDetailDialog from '@/components/RunDetailDialog.vue'
import { VChart } from '@/composables/useECharts'

const route = useRoute()
const router = useRouter()
const strategyId = computed(() => Number(route.params.id))

const loading = ref(false)
const detail = ref<CodeStrategyDetail | null>(null)
const activeTab = ref('params')

// ---- 策略代码 Tab ----
const codeText = ref('')
const codeDirty = ref(false)
const validating = ref(false)
const validateErrors = ref<string[]>([])
let validateTimer: ReturnType<typeof setTimeout> | null = null

const codeStatus = computed(() => {
  if (validating.value) return { type: 'info' as const, label: t('library.detail.code.validating') }
  if (validateErrors.value.length) return { type: 'danger' as const, label: t('library.detail.code.validateFail') }
  return { type: 'success' as const, label: t('library.detail.code.validateOk') }
})

function scheduleValidate() {
  if (validateTimer) clearTimeout(validateTimer)
  validateTimer = setTimeout(() => void runValidate(), 800)
}

async function runValidate() {
  validating.value = true
  try {
    const result = await libraryApi.validate(codeText.value)
    validateErrors.value = result.errors
  } catch (e) {
    validateErrors.value = [(e as Error).message]
  } finally {
    validating.value = false
  }
}

async function saveCode() {
  validating.value = true
  try {
    const result = await libraryApi.validate(codeText.value)
    validateErrors.value = result.errors
    if (!result.ok) {
      ElMessage.warning(t('library.detail.code.fixErrorsFirst'))
      return
    }
    await libraryApi.update(strategyId.value, {
      source: codeText.value,
      params: result.params,
      note: t('library.detail.code.save'),
    })
    codeDirty.value = false
    ElMessage.success(t('library.detail.code.saved'))
    await loadDetail(false)
    await loadVersions()
  } catch (e) {
    ElMessage.error((e as Error).message)
  } finally {
    validating.value = false
  }
}

// ---- 参数设置 Tab（回测表单 + 运行） ----
const form = ref({
  stock_code: '',
  start_date: '2023-01-03',
  end_date: '2025-01-02',
  initial_capital: 100000,
  commission_rate: 0.0003,
})
const submitting = ref(false)
const polling = ref(false)
const lastRun = ref<BacktestRunDetail | null>(null)
let pollTimer: ReturnType<typeof setTimeout> | null = null

async function submitRun() {
  if (!detail.value) return
  submitting.value = true
  try {
    const res = await runsApi.submit({
      strategy_kind: 'code',
      strategy_id: strategyId.value,
      strategy_name: detail.value.name,
      stock_code: form.value.stock_code,
      start_date: form.value.start_date,
      end_date: form.value.end_date,
      initial_capital: Number(form.value.initial_capital),
      commission_rate: Number(form.value.commission_rate),
      market: detail.value.market,
    })
    ElMessage.success(t('library.detail.params.submitted'))
    polling.value = true
    pollRun(res.id)
  } catch (e) {
    ElMessage.error((e as Error).message)
  } finally {
    submitting.value = false
  }
}

function pollRun(runId: number) {
  if (pollTimer) clearTimeout(pollTimer)
  pollTimer = setTimeout(async () => {
    try {
      const d = await runsApi.detail(runId)
      if (d.status === 'queued' || d.status === 'running') {
        pollRun(runId)
        return
      }
      lastRun.value = d
      polling.value = false
    } catch (e) {
      polling.value = false
      ElMessage.error((e as Error).message || t('library.detail.params.pollFailed'))
    }
  }, 2000)
}

const runOption = computed(() => {
  const run = lastRun.value
  if (!run || !run.equity_curve.length) return {}
  const color = chartPalette(detail.value?.market ?? 'zh_a').up
  return {
    tooltip: { trigger: 'axis' },
    grid: { left: 60, right: 24, top: 24, bottom: 52 },
    xAxis: { type: 'category', data: run.dates },
    yAxis: { type: 'value', scale: true },
    dataZoom: [{ type: 'inside' }, { type: 'slider' }],
    series: [{ name: t('library.detail.history.equityCurve'), type: 'line', data: run.equity_curve, showSymbol: false, lineStyle: { color, width: 1.6 } }],
  }
})

// ---- 历史版本 Tab ----
const versions = ref<StrategyVersion[]>([])
const versionDialog = ref(false)
const versionSource = ref('')

async function loadVersions() {
  try {
    const data = await libraryApi.versions(strategyId.value)
    versions.value = data.versions
  } catch {
    versions.value = []
  }
}

async function viewVersion(v: StrategyVersion) {
  const full = await libraryApi.versionSource(v.id)
  versionSource.value = full.source
  versionDialog.value = true
}

async function restoreVersion(v: StrategyVersion) {
  try {
    await ElMessageBox.confirm(t('library.detail.versions.restoreConfirm'), t('library.title'), {
      type: 'warning',
    })
  } catch {
    return
  }
  try {
    await libraryApi.restoreVersion(strategyId.value, v.id)
    ElMessage.success(t('library.detail.versions.restored'))
    await loadDetail(false)
    await loadVersions()
    codeText.value = detail.value?.source ?? ''
    codeDirty.value = false
  } catch (e) {
    ElMessage.error((e as Error).message)
  }
}

// ---- 回测历史 Tab ----
const runs = ref<BacktestRunSummary[]>([])
const runsLoading = ref(false)
const runDetailVisible = ref(false)
const runDetail = ref<BacktestRunDetail | null>(null)

async function loadRuns() {
  runsLoading.value = true
  try {
    const data = await runsApi.list({ strategy_kind: 'code', strategy_id: strategyId.value, limit: 50 })
    runs.value = data.runs
  } catch (e) {
    ElMessage.error((e as Error).message)
  } finally {
    runsLoading.value = false
  }
}

async function openRun(runId: number) {
  runDetail.value = await runsApi.detail(runId)
  runDetailVisible.value = true
}

// ---- 调优 Tab ----
const tuningTasks = ref<TuningTask[]>([])

async function loadTuningTasks() {
  try {
    const data = await tuningApi.list({ strategy_kind: 'code', strategy_id: strategyId.value, limit: 20 })
    tuningTasks.value = data.tasks
  } catch {
    tuningTasks.value = []
  }
}

// ---- 新建调优对话框 ----
const tuningDialog = ref(false)
const tuningSubmitting = ref(false)
const gridEnabled = ref<Record<string, boolean>>({})
const gridValuesText = ref<Record<string, string>>({})
const tuningTargetMetric = ref('总收益率')
const TUNING_METRICS = ['总收益率', '夏普比率', '最大回撤']

const tuningForm = ref({
  stock_code: '',
  start_date: '2023-01-03',
  end_date: '2025-01-02',
  initial_capital: 100000,
  commission_rate: 0.0003,
})

function openTuningDialog() {
  tuningForm.value = {
    stock_code: form.value.stock_code,
    start_date: form.value.start_date,
    end_date: form.value.end_date,
    initial_capital: form.value.initial_capital,
    commission_rate: form.value.commission_rate,
  }
  tuningTargetMetric.value = '总收益率'
  gridEnabled.value = {}
  gridValuesText.value = {}
  tuningDialog.value = true
}

const TUNING_MAX_COMBOS = 63

function parseGridValues(text: string): { ok: boolean; values: (number | boolean)[] } {
  const values: (number | boolean)[] = []
  for (const raw of text.split(',')) {
    const piece = raw.trim()
    if (!piece) continue
    if (/^(true|false)$/i.test(piece)) {
      values.push(piece.toLowerCase() === 'true')
    } else {
      const n = Number(piece)
      if (!Number.isFinite(n)) return { ok: false, values: [] }
      values.push(n)
    }
  }
  return { ok: values.length > 0, values }
}

const tuningCombos = computed(() => {
  const enabled = Object.keys(gridEnabled.value).filter((k) => gridEnabled.value[k])
  if (enabled.length === 0) return { count: 0, over: false, invalid: '' }
  let n = 1
  for (const name of enabled) {
    const parsed = parseGridValues(gridValuesText.value[name] ?? '')
    if (!parsed.ok) return { count: 0, over: false, invalid: name }
    n *= parsed.values.length
  }
  return { count: n, over: n > TUNING_MAX_COMBOS, invalid: '' }
})

async function submitTuning() {
  if (!detail.value) return
  const grid: Record<string, (number | boolean)[]> = {}
  for (const [name, on] of Object.entries(gridEnabled.value)) {
    if (!on) continue
    const parsed = parseGridValues(gridValuesText.value[name] ?? '')
    if (!parsed.ok) {
      ElMessage.warning(t('tuning.create.badValues', { name }))
      return
    }
    grid[name] = parsed.values
  }
  if (Object.keys(grid).length === 0) {
    ElMessage.warning(t('tuning.create.noGrid'))
    return
  }
  if (tuningCombos.value.over) return
  tuningSubmitting.value = true
  try {
    const res = await tuningApi.create({
      strategy_kind: 'code',
      strategy_id: strategyId.value,
      strategy_name: detail.value.name,
      stock_code: tuningForm.value.stock_code,
      market: detail.value.market,
      start_date: tuningForm.value.start_date,
      end_date: tuningForm.value.end_date,
      initial_capital: Number(tuningForm.value.initial_capital),
      commission_rate: Number(tuningForm.value.commission_rate),
      param_grid: grid,
      target_metric: tuningTargetMetric.value,
    })
    ElMessage.success(t('tuning.create.submitted'))
    tuningDialog.value = false
    await router.push(`/tuning/${res.id}`)
  } catch (e) {
    ElMessage.error((e as Error).message)
  } finally {
    tuningSubmitting.value = false
  }
}

// ---- 展示助手 ----
function fmtPct(v: number | null | undefined): string {
  if (v === null || v === undefined) return '—'
  return (v * 100).toFixed(2) + '%'
}
function fmtNum(v: number | null | undefined, nd = 2): string {
  if (v === null || v === undefined) return '—'
  return Number(v).toFixed(nd)
}
function statusTag(s: string): string {
  const map: Record<string, string> = {
    queued: 'info', running: 'primary', succeeded: 'success', failed: 'danger', cancelled: 'warning',
  }
  return map[s] ?? 'info'
}
function statusLabel(s: string): string {
  return t(`common.status.${s}`)
}
function stageLabel(stage: string): string {
  const map: Record<string, string> = {
    fetch_data: 'stagesFetchData', load_strategy: 'stagesLoadStrategy', backtest: 'stagesBacktest',
    metrics: 'stagesMetrics', benchmark: 'stagesBenchmark', enrich: 'stagesEnrich',
  }
  const key = map[stage]
  return key ? t(`library.detail.history.${key}`) : stage
}
function fmtDuration(ms: number | null | undefined): string {
  if (!ms && ms !== 0) return '—'
  return ms >= 1000 ? (ms / 1000).toFixed(1) + 's' : ms + 'ms'
}

// ---- 装配 ----
async function loadDetail(withCode = true) {
  loading.value = true
  try {
    const d = await libraryApi.detail(strategyId.value)
    detail.value = d
    if (withCode) {
      codeText.value = d.source
      codeDirty.value = false
    }
    if (d.market === 'us') form.value.stock_code = form.value.stock_code || ''
  } catch (e) {
    ElMessage.error((e as Error).message || t('library.loadFailed'))
  } finally {
    loading.value = false
  }
}

watch(codeText, (v) => {
  if (detail.value && v !== detail.value.source) {
    codeDirty.value = true
    scheduleValidate()
  }
})

watch(activeTab, (tab) => {
  if (tab === 'versions') void loadVersions()
  if (tab === 'history') void loadRuns()
  if (tab === 'tuning') void loadTuningTasks()
})

onMounted(async () => {
  await loadDetail()
  void runValidate()
})

onBeforeUnmount(() => {
  if (validateTimer) clearTimeout(validateTimer)
  if (pollTimer) clearTimeout(pollTimer)
})
</script>

<template>
  <div v-loading="loading" class="detail-page">
    <div class="page-head">
      <div class="head-left">
        <el-button text @click="router.push('/strategy-library')">
          <el-icon><Back /></el-icon> {{ t('library.detail.backToList') }}
        </el-button>
        <h2 v-if="detail" class="page-title">
          {{ detail.name }}
          <el-tag size="small" :type="detail.market === 'us' ? 'warning' : 'danger'" class="market-tag">
            {{ detail.market === 'us' ? t('common.market.us') : t('common.market.zhA') }}
          </el-tag>
        </h2>
        <p v-if="detail" class="page-subtitle">
          {{ detail.description || t('library.detail.noDescription') }} ·
          {{ t('library.detail.updatedAt') }} {{ detail.updated_at }}
        </p>
      </div>
    </div>

    <el-tabs v-if="detail" v-model="activeTab">
      <!-- ===================== 参数设置 ===================== -->
      <el-tab-pane :label="t('library.detail.tabs.params')" name="params">
        <el-form :model="form" label-width="110px" class="run-form">
          <el-row :gutter="16">
            <el-col :span="8">
              <el-form-item :label="t('library.detail.params.stockCode')" required>
                <el-input v-model="form.stock_code" :placeholder="t('library.detail.params.stockCodePlaceholder')" />
              </el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item :label="t('library.detail.params.startDate')" required>
                <el-date-picker v-model="form.start_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
              </el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item :label="t('library.detail.params.endDate')" required>
                <el-date-picker v-model="form.end_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
              </el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item :label="t('library.detail.params.initialCapital')">
                <el-input-number v-model="form.initial_capital" :min="10000" :step="10000" style="width: 100%" />
              </el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item :label="t('library.detail.params.commissionRate')">
                <el-input-number v-model="form.commission_rate" :min="0" :max="0.01" :step="0.0001" :precision="5" style="width: 100%" />
              </el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item label-width="0">
                <el-button type="primary" :loading="submitting || polling" @click="submitRun">
                  {{ polling ? t('library.detail.params.submitted') : t('library.detail.params.run') }}
                </el-button>
              </el-form-item>
            </el-col>
          </el-row>
        </el-form>

        <el-card v-if="lastRun" shadow="never" class="run-result">
          <template #header>
            <div class="result-head">
              <span>#{{ lastRun.id }} · {{ statusLabel(lastRun.status) }}</span>
              <span class="result-duration">{{ t('library.detail.history.duration') }} {{ fmtDuration(lastRun.duration_ms) }}</span>
            </div>
          </template>
          <el-alert v-if="lastRun.status === 'failed'" type="error" :title="t('library.detail.history.errorLabel')" :description="lastRun.error || ''" :closable="false" />
          <template v-else-if="lastRun.metrics">
            <div class="metric-grid">
              <div class="metric-item">
                <span class="metric-label">{{ t('backtest.metric.总收益率') }}</span>
                <span class="metric-value">{{ fmtPct(lastRun.metrics['总收益率']) }}</span>
              </div>
              <div class="metric-item">
                <span class="metric-label">{{ t('backtest.metric.夏普比率') }}</span>
                <span class="metric-value">{{ fmtNum(lastRun.metrics['夏普比率']) }}</span>
              </div>
              <div class="metric-item">
                <span class="metric-label">{{ t('backtest.metric.最大回撤') }}</span>
                <span class="metric-value">{{ fmtPct(lastRun.metrics['最大回撤']) }}</span>
              </div>
              <div class="metric-item">
                <span class="metric-label">{{ t('library.detail.history.metricTrades') }}</span>
                <span class="metric-value">{{ lastRun.trades.length }}</span>
              </div>
            </div>
            <v-chart v-if="lastRun.equity_curve.length" class="run-chart" :option="runOption" autoresize />
            <div v-if="lastRun.stages.length" class="stage-row">
              <el-tag v-for="st in lastRun.stages" :key="st.stage" size="small" type="info" class="stage-tag">
                {{ stageLabel(st.stage) }} {{ st.ms }}ms
              </el-tag>
            </div>
          </template>
        </el-card>
      </el-tab-pane>

      <!-- ===================== 策略代码 ===================== -->
      <el-tab-pane :label="t('library.detail.tabs.code')" name="code">
        <div class="code-toolbar">
          <el-tag :type="codeStatus.type" size="small">{{ codeStatus.label }}</el-tag>
          <span v-if="codeDirty" class="dirty-hint">{{ t('library.detail.code.unsaved') }}</span>
          <div class="toolbar-right">
            <el-button :loading="validating" @click="runValidate">{{ t('library.detail.code.validate') }}</el-button>
            <el-button type="primary" :loading="validating" @click="saveCode">{{ t('library.detail.code.save') }}</el-button>
          </div>
        </div>
        <CodeEditor v-model="codeText" height="480px" />
        <el-alert
          v-if="validateErrors.length"
          type="error"
          class="code-errors"
          :closable="false"
          :title="t('library.detail.code.validateFail')"
        >
          <div v-for="(err, i) in validateErrors" :key="i" class="code-error-line">{{ err }}</div>
        </el-alert>
      </el-tab-pane>

      <!-- ===================== 历史版本 ===================== -->
      <el-tab-pane :label="t('library.detail.tabs.versions')" name="versions">
        <el-empty v-if="versions.length === 0" :description="t('library.detail.versions.empty')" />
        <el-table v-else :data="versions" size="small">
          <el-table-column prop="id" label="#" width="70" />
          <el-table-column prop="created_at" :label="t('library.detail.versions.time')" width="180" />
          <el-table-column prop="note" :label="t('library.detail.versions.note')" min-width="200" />
          <el-table-column :label="t('library.detail.history.action')" width="180">
            <template #default="{ row }">
              <el-button text size="small" @click="viewVersion(row)">{{ t('library.detail.versions.view') }}</el-button>
              <el-button text size="small" type="warning" @click="restoreVersion(row)">
                {{ t('library.detail.versions.restore') }}
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <!-- ===================== 回测历史 ===================== -->
      <el-tab-pane :label="t('library.detail.tabs.history')" name="history">
        <div class="history-toolbar">
          <el-button size="small" @click="loadRuns">{{ t('library.detail.history.refresh') }}</el-button>
        </div>
        <el-empty v-if="!runsLoading && runs.length === 0" :description="t('library.detail.history.empty')" />
        <el-table v-else v-loading="runsLoading" :data="runs" size="small">
          <el-table-column prop="id" label="#" width="70" />
          <el-table-column :label="t('library.detail.history.status')" width="100">
            <template #default="{ row }">
              <el-tag size="small" :type="statusTag(row.status)">{{ statusLabel(row.status) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column :label="t('library.detail.history.range')" min-width="190">
            <template #default="{ row }">{{ row.start_date }} ~ {{ row.end_date }} · {{ row.stock_code }}</template>
          </el-table-column>
          <el-table-column :label="t('library.detail.history.metricTotalReturn')" width="100">
            <template #default="{ row }">{{ row.metrics ? fmtPct(row.metrics['总收益率']) : '—' }}</template>
          </el-table-column>
          <el-table-column :label="t('library.detail.history.metricSharpe')" width="90">
            <template #default="{ row }">{{ row.metrics ? fmtNum(row.metrics['夏普比率']) : '—' }}</template>
          </el-table-column>
          <el-table-column :label="t('library.detail.history.metricDrawdown')" width="100">
            <template #default="{ row }">{{ row.metrics ? fmtPct(row.metrics['最大回撤']) : '—' }}</template>
          </el-table-column>
          <el-table-column :label="t('library.detail.history.duration')" width="90">
            <template #default="{ row }">{{ fmtDuration(row.duration_ms) }}</template>
          </el-table-column>
          <el-table-column prop="created_at" :label="t('library.detail.history.time')" width="170" />
          <el-table-column :label="t('library.detail.history.action')" width="90">
            <template #default="{ row }">
              <el-button text size="small" :disabled="row.status !== 'succeeded'" @click="openRun(row.id)">
                {{ t('library.detail.history.viewRun') }}
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <!-- ===================== 调优历史 ===================== -->
      <el-tab-pane :label="t('library.detail.tabs.tuning')" name="tuning">
        <div class="history-toolbar">
          <el-button type="primary" size="small" @click="openTuningDialog">{{ t('tuning.list.create') }}</el-button>
          <el-button size="small" @click="loadTuningTasks">{{ t('common.refresh') }}</el-button>
        </div>
        <el-empty v-if="tuningTasks.length === 0" :description="t('tuning.list.empty')" />
        <el-table v-else :data="tuningTasks" size="small">
          <el-table-column prop="id" label="#" width="70" />
          <el-table-column :label="t('tuning.table.status')" width="100">
            <template #default="{ row }">
              <el-tag size="small" :type="statusTag(row.status)">{{ t(`common.status.${row.status}`) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column :label="t('tuning.list.progress')" min-width="180">
            <template #default="{ row }">
              <el-progress
                :percentage="row.total_combos ? Math.round((row.done_combos / row.total_combos) * 100) : 0"
                :stroke-width="8"
                class="tuning-progress"
              />
              <span class="tuning-progress-text">{{ row.done_combos }}/{{ row.total_combos }}</span>
            </template>
          </el-table-column>
          <el-table-column :label="t('tuning.list.target')" width="130">
            <template #default="{ row }">{{ t(`backtest.metric.${row.target_metric}`) }}</template>
          </el-table-column>
          <el-table-column :label="t('tuning.table.range')" min-width="190">
            <template #default="{ row }">{{ row.start_date }} ~ {{ row.end_date }} · {{ row.stock_code }}</template>
          </el-table-column>
          <el-table-column prop="created_at" :label="t('tuning.list.created')" width="170" />
          <el-table-column :label="t('tuning.list.action')" width="90">
            <template #default="{ row }">
              <el-button text size="small" type="primary" @click="router.push(`/tuning/${row.id}`)">
                {{ t('tuning.list.open') }}
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>
    </el-tabs>

    <!-- 版本全文对话框 -->
    <el-dialog v-model="versionDialog" :title="t('library.detail.tabs.versions')" width="780px">
      <CodeEditor v-model="versionSource" readonly height="420px" />
    </el-dialog>

    <!-- 运行详情对话框（与运行历史页共用） -->
    <RunDetailDialog v-model:visible="runDetailVisible" :run="runDetail" />

    <!-- 新建调优对话框 -->
    <el-dialog v-model="tuningDialog" :title="t('tuning.create.title')" width="720px">
      <el-alert type="info" :title="t('tuning.create.gridHint')" :closable="false" class="tuning-hint" />
      <h4 class="tuning-section">{{ t('tuning.create.gridTitle') }}</h4>
      <el-table :data="Object.keys(detail?.params ?? {})" size="small" max-height="260">
        <el-table-column width="56">
          <template #default="{ row }">
            <el-checkbox v-model="gridEnabled[row]" />
          </template>
        </el-table-column>
        <el-table-column :label="t('tuning.table.params')" min-width="160">
          <template #default="{ row }">
            <span class="param-text">{{ row }}</span>
            <span class="param-current"> = {{ (detail?.params as Record<string, unknown>)[row] }}</span>
          </template>
        </el-table-column>
        <el-table-column min-width="260">
          <template #default="{ row }">
            <el-input
              v-model="gridValuesText[row]"
              size="small"
              :disabled="!gridEnabled[row]"
              :placeholder="t('tuning.create.valuesPlaceholder')"
            />
          </template>
        </el-table-column>
      </el-table>
      <div class="tuning-count">
        <span v-if="tuningCombos.invalid" class="tuning-count-invalid">{{ t('tuning.create.badValues', { name: tuningCombos.invalid }) }}</span>
        <span v-else-if="tuningCombos.over" class="tuning-count-invalid">{{ t('tuning.create.comboCountOver') }}</span>
        <span v-else>{{ t('tuning.create.comboCount', { n: tuningCombos.count, total: tuningCombos.count + 1 }) }}</span>
      </div>
      <h4 class="tuning-section">{{ t('library.detail.tabs.params') }}</h4>
      <el-form label-width="110px">
        <el-row :gutter="16">
          <el-col :span="8">
            <el-form-item :label="t('library.detail.params.stockCode')" required>
              <el-input v-model="tuningForm.stock_code" :placeholder="t('library.detail.params.stockCodePlaceholder')" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item :label="t('library.detail.params.startDate')">
              <el-date-picker v-model="tuningForm.start_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item :label="t('library.detail.params.endDate')">
              <el-date-picker v-model="tuningForm.end_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item :label="t('library.detail.params.initialCapital')">
              <el-input-number v-model="tuningForm.initial_capital" :min="10000" :step="10000" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item :label="t('library.detail.params.commissionRate')">
              <el-input-number v-model="tuningForm.commission_rate" :min="0" :max="0.01" :step="0.0001" :precision="5" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item :label="t('tuning.create.targetMetric')">
              <el-select v-model="tuningTargetMetric" style="width: 100%">
                <el-option v-for="m in TUNING_METRICS" :key="m" :value="m" :label="t(`backtest.metric.${m}`)" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>
      <div class="tuning-count">
        <span class="tuning-target-hint">{{ t('tuning.create.targetHint') }}</span>
      </div>
      <template #footer>
        <el-button @click="tuningDialog = false">{{ t('common.cancel') }}</el-button>
        <el-button
          type="primary"
          :loading="tuningSubmitting"
          :disabled="tuningCombos.over || !!tuningCombos.invalid || !tuningForm.stock_code"
          @click="submitTuning"
        >
          {{ t('tuning.create.submit') }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.detail-page {
  padding: 4px 4px 24px;
}
.page-head {
  margin-bottom: 12px;
}
.page-title {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 6px 0 4px;
  font-size: 22px;
}
.market-tag {
  transform: translateY(-2px);
}
.page-subtitle {
  margin: 0;
  color: var(--el-text-color-secondary);
  font-size: 13px;
}
.run-form {
  margin-top: 4px;
}
.run-result {
  margin-top: 8px;
}
.result-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.result-duration {
  color: var(--el-text-color-secondary);
  font-size: 13px;
}
.metric-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 12px;
  margin-bottom: 12px;
}
.metric-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.metric-label {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.metric-value {
  font-size: 18px;
  font-weight: 600;
}
.run-chart {
  width: 100%;
  height: 260px;
}
.stage-row {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
  margin-top: 10px;
}
.stage-title {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.stage-tag {
  font-family: monospace;
}
.code-toolbar {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
}
.dirty-hint {
  color: var(--el-color-warning);
  font-size: 12px;
}
.toolbar-right {
  margin-left: auto;
  display: flex;
  gap: 8px;
}
.code-errors {
  margin-top: 10px;
}
.code-error-line {
  font-family: monospace;
  font-size: 12px;
}
.history-toolbar {
  margin-bottom: 10px;
}
.tuning-hint {
  margin-bottom: 12px;
}
.tuning-section {
  margin: 6px 0 8px;
}
.tuning-count {
  margin: 8px 0 4px;
  font-size: 13px;
}
.tuning-count-invalid {
  color: var(--el-color-danger);
}
.tuning-target-hint {
  color: var(--el-text-color-secondary);
  font-size: 12px;
}
.param-text {
  font-family: monospace;
  font-size: 12px;
}
.param-current {
  color: var(--el-text-color-secondary);
  font-size: 12px;
}
.tuning-progress {
  width: 110px;
  display: inline-flex;
  vertical-align: middle;
}
.tuning-progress-text {
  margin-left: 8px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
</style>
