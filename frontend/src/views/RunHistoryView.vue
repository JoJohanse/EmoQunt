<script setup lang="ts">
/**
 * RunHistoryView —— 运行历史独立页（/runs）：服务端落库的全部回测运行。
 * 筛选（策略/类型/市场/状态）+ 可切换指标列 + 净值缩略 + 详情弹窗（RunDetailDialog）。
 * 数据面：GET /api/v2/backtest/runs（摘要，含 ≤60 点 equity_preview）。
 */
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { libraryApi, runsApi, strategyApi } from '@/api'
import type { BacktestRunDetail, BacktestRunSummary, Market } from '@/api/types'
import { chartPalette } from '@/lib/marketColors'
import { t } from '@/locales'
import RunDetailDialog from '@/components/RunDetailDialog.vue'
import MiniSparkline from '@/components/MiniSparkline.vue'

const loading = ref(false)
const runs = ref<BacktestRunSummary[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = 50

// ---- 筛选 ----
const kindFilter = ref<'' | 'template' | 'code'>('')
const marketFilter = ref<'' | Market>('')
const statusFilter = ref('')
// 策略下拉值："template:<name>" | "code:<id>"
const strategyFilter = ref('')
const templateStrategies = ref<{ key: string; name: string }[]>([])
const codeStrategies = ref<{ key: string; id: number; name: string; market: string }[]>([])

const strategyOptions = computed(() => {
  const opts: { key: string; label: string; kind: string }[] = []
  if (kindFilter.value !== 'code') {
    for (const s of templateStrategies.value) {
      opts.push({ key: s.key, label: `${s.name}`, kind: 'template' })
    }
  }
  if (kindFilter.value !== 'template') {
    for (const s of codeStrategies.value) {
      opts.push({ key: s.key, label: `${s.name}`, kind: 'code' })
    }
  }
  return opts
})

const METRIC_KEYS = ['总收益率', '夏普比率', '最大回撤'] as const
const metricKey = ref<(typeof METRIC_KEYS)[number]>('总收益率')
const metricLabel = (k: string) => t(`backtest.metric.${k}`)

async function loadStrategyOptions() {
  try {
    const [tpl, code] = await Promise.all([
      strategyApi.list().catch(() => []),
      libraryApi.list({}).then((d) => d.strategies).catch(() => []),
    ])
    templateStrategies.value = tpl.map((s: { name: string }) => ({ key: `template:${s.name}`, name: s.name }))
    codeStrategies.value = code.map((s) => ({ key: `code:${s.id}`, id: s.id, name: s.name, market: s.market }))
  } catch {
    /* 下拉选项加载失败不阻塞列表 */
  }
}

const queryParams = computed(() => {
  const params: Record<string, string | number> = { limit: pageSize, offset: (page.value - 1) * pageSize }
  if (kindFilter.value) params.strategy_kind = kindFilter.value
  if (marketFilter.value) params.market = marketFilter.value
  if (statusFilter.value) params.status = statusFilter.value
  const sf = strategyFilter.value
  if (sf.startsWith('code:')) {
    params.strategy_kind = 'code'
    params.strategy_id = Number(sf.slice(5))
  } else if (sf.startsWith('template:')) {
    params.strategy_name = sf.slice(9)
  }
  return params
})

async function load() {
  loading.value = true
  try {
    const data = await runsApi.list(queryParams.value as Parameters<typeof runsApi.list>[0])
    runs.value = data.runs
    total.value = data.runs.length < pageSize && page.value === 1 ? data.runs.length : (page.value - 1) * pageSize + data.runs.length
  } catch (e) {
    ElMessage.error((e as Error).message || t('runs.loadFailed'))
  } finally {
    loading.value = false
  }
}

function reload() {
  page.value = 1
  void load()
}

// ---- 详情弹窗 ----
const detailVisible = ref(false)
const detailRun = ref<BacktestRunDetail | null>(null)

async function openDetail(id: number) {
  try {
    detailRun.value = await runsApi.detail(id)
    detailVisible.value = true
  } catch (e) {
    ElMessage.error((e as Error).message)
  }
}

// ---- 展示助手 ----
function statusTag(s: string): string {
  const map: Record<string, string> = {
    queued: 'info', running: 'primary', succeeded: 'success', failed: 'danger', cancelled: 'warning',
  }
  return map[s] ?? 'info'
}
function fmtMetric(row: BacktestRunSummary): string {
  const v = row.metrics?.[metricKey.value]
  if (v === undefined || v === null) return '—'
  return metricKey.value === '夏普比率' ? Number(v).toFixed(2) : (v * 100).toFixed(2) + '%'
}
function sparkColor(row: BacktestRunSummary): string {
  const vals = row.equity_preview ?? []
  if (vals.length < 2) return 'var(--el-text-color-secondary)'
  const palette = chartPalette(row.market)
  return vals[vals.length - 1] >= vals[0] ? palette.up : palette.down
}
function fmtDuration(ms: number | null | undefined): string {
  if (!ms && ms !== 0) return '—'
  return ms >= 1000 ? (ms / 1000).toFixed(1) + 's' : ms + 'ms'
}

onMounted(() => {
  void loadStrategyOptions()
  void load()
})
</script>

<template>
  <div class="runs-page">
    <div class="page-head">
      <h2 class="page-title">{{ t('runs.title') }}</h2>
      <p class="page-subtitle">{{ t('runs.subtitle') }}</p>
    </div>

    <div class="toolbar">
      <el-select v-model="strategyFilter" clearable filterable :placeholder="t('runs.filters.strategyAll')" style="width: 220px" @change="reload">
        <el-option v-for="o in strategyOptions" :key="o.key" :value="o.key" :label="`${o.label}（${o.kind === 'code' ? t('runs.kindCode') : t('runs.kindTemplate')}）`" />
      </el-select>
      <el-select v-model="kindFilter" clearable :placeholder="t('runs.filters.kind')" style="width: 140px" @change="reload">
        <el-option value="template" :label="t('runs.filters.kindTemplate')" />
        <el-option value="code" :label="t('runs.filters.kindCode')" />
      </el-select>
      <el-select v-model="marketFilter" clearable :placeholder="t('runs.filters.market')" style="width: 120px" @change="reload">
        <el-option value="zh_a" label="A股" />
        <el-option value="us" label="US" />
      </el-select>
      <el-select v-model="statusFilter" clearable :placeholder="t('runs.filters.status')" style="width: 130px" @change="reload">
        <el-option v-for="s in ['queued', 'running', 'succeeded', 'failed', 'cancelled']" :key="s" :value="s" :label="t(`common.status.${s}`)" />
      </el-select>
      <el-radio-group v-model="metricKey" size="small" class="metric-switch">
        <el-radio-button v-for="k in METRIC_KEYS" :key="k" :value="k">{{ metricLabel(k) }}</el-radio-button>
      </el-radio-group>
      <el-button size="small" class="toolbar-refresh" @click="load">{{ t('common.refresh') }}</el-button>
    </div>

    <el-empty v-if="!loading && runs.length === 0" :description="t('runs.empty')" />
    <el-table v-else v-loading="loading" :data="runs" size="small" class="runs-table">
      <el-table-column prop="id" label="#" width="64" />
      <el-table-column :label="t('runs.col.strategy')" min-width="170">
        <template #default="{ row }">
          <el-tag v-if="row.strategy_kind === 'code'" size="small" type="success" class="kind-tag">{{ t('runs.kindCode') }}</el-tag>
          <el-tag v-else size="small" type="info" class="kind-tag">{{ t('runs.kindTemplate') }}</el-tag>
          <span>{{ row.strategy_name }}</span>
        </template>
      </el-table-column>
      <el-table-column :label="t('runs.col.stock')" width="120">
        <template #default="{ row }">
          <span>{{ row.stock_code }}</span>
          <el-tag size="small" :type="row.market === 'us' ? 'warning' : 'danger'" class="market-tag">{{ row.market === 'us' ? 'US' : 'A股' }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column :label="t('runs.col.range')" width="190">
        <template #default="{ row }">{{ row.start_date }} ~ {{ row.end_date }}</template>
      </el-table-column>
      <el-table-column :label="t('runs.col.status')" width="96">
        <template #default="{ row }">
          <el-tag size="small" :type="statusTag(row.status)">{{ t(`common.status.${row.status}`) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column :label="metricLabel(metricKey)" width="110">
        <template #default="{ row }">{{ fmtMetric(row) }}</template>
      </el-table-column>
      <el-table-column :label="t('runs.col.equity')" width="100">
        <template #default="{ row }">
          <MiniSparkline v-if="(row.equity_preview ?? []).length > 1" :values="row.equity_preview!" :color="sparkColor(row)" />
          <span v-else>—</span>
        </template>
      </el-table-column>
      <el-table-column :label="t('runs.col.duration')" width="86">
        <template #default="{ row }">{{ fmtDuration(row.duration_ms) }}</template>
      </el-table-column>
      <el-table-column prop="created_at" :label="t('runs.col.time')" width="165" />
      <el-table-column :label="t('runs.col.action')" width="84" fixed="right">
        <template #default="{ row }">
          <el-button text size="small" :disabled="row.status === 'queued' || row.status === 'running'" @click="openDetail(row.id)">
            {{ t('runs.col.detail') }}
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <div v-if="total > pageSize" class="pager">
      <el-pagination v-model:current-page="page" :page-size="pageSize" :total="total" layout="prev, pager, next" @current-change="load" />
    </div>

    <RunDetailDialog v-model:visible="detailVisible" :run="detailRun" />
  </div>
</template>


<style scoped>
.runs-page {
  padding: 4px 4px 24px;
}
.page-head {
  margin-bottom: 12px;
}
.page-title {
  margin: 6px 0 4px;
  font-size: 22px;
}
.page-subtitle {
  margin: 0;
  color: var(--el-text-color-secondary);
  font-size: 13px;
}
.toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
  margin-bottom: 12px;
}
.metric-switch {
  margin-left: auto;
}
.runs-table .kind-tag {
  margin-right: 6px;
}
.runs-table .market-tag {
  margin-left: 6px;
}
.pager {
  display: flex;
  justify-content: flex-end;
  margin-top: 12px;
}
</style>
