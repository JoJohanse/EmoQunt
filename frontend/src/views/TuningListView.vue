<script setup lang="ts">
/**
 * TuningListView —— 调优任务独立页（/tunings）：全量参数调优任务的进度与最优组合一览。
 *
 * 数据面：GET /api/v2/tuning/tasks（新→旧，不含组合）。接口只支持
 * strategy_kind/strategy_id/limit/offset 过滤，故状态与关键词筛选在前端对已拉取窗口做。
 * 指标展示名复用 backtest.metric.<中文键>，状态复用 common.status.*，市场标签复用 common.market.*。
 */
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { tuningApi } from '@/api'
import type { TuningTask } from '@/api/types'
import { t } from '@/locales'

const router = useRouter()

const loading = ref(false)
const tasks = ref<TuningTask[]>([])
const statusFilter = ref('')
const keyword = ref('')

/** 调优任务状态（与后端 tuning_tasks.status 契约一致，无 cancelled） */
const STATUSES = ['queued', 'running', 'succeeded', 'failed'] as const
/** 单页拉取条数（后端上限 200；筛选为前端过滤，靠这一窗口） */
const PAGE_LIMIT = 50

async function load() {
  loading.value = true
  try {
    const data = await tuningApi.list({ limit: PAGE_LIMIT })
    tasks.value = data.tasks
  } catch (e) {
    ElMessage.error((e as Error).message || t('tuning.loadFailed'))
  } finally {
    loading.value = false
  }
}

/** 状态 + 关键词（策略名/标的代码）前端过滤 */
const filtered = computed(() => {
  const kw = keyword.value.trim().toLowerCase()
  return tasks.value.filter((task) => {
    if (statusFilter.value && task.status !== statusFilter.value) return false
    if (!kw) return true
    return (
      task.strategy_name.toLowerCase().includes(kw) || task.stock_code.toLowerCase().includes(kw)
    )
  })
})

function openDetail(row: TuningTask) {
  void router.push(`/tuning/${row.id}`)
}

// ---- 展示助手 ----
function statusTag(s: string): string {
  const map: Record<string, string> = {
    queued: 'info', running: 'primary', succeeded: 'success', failed: 'danger', cancelled: 'warning',
  }
  return map[s] ?? 'info'
}
function progressPct(row: TuningTask): number {
  if (!row.total_combos) return 0
  return Math.round((row.done_combos / row.total_combos) * 100)
}
function progressStatus(row: TuningTask): 'success' | 'exception' | undefined {
  if (row.status === 'succeeded') return 'success'
  if (row.status === 'failed') return 'exception'
  return undefined
}
function fmtDuration(ms: number | null | undefined): string {
  if (!ms && ms !== 0) return '—'
  return ms >= 1000 ? (ms / 1000).toFixed(1) + 's' : ms + 'ms'
}

onMounted(() => void load())
</script>

<template>
  <div class="tunings-page">
    <div class="page-head">
      <h2 class="page-title">{{ t('tuning.page.title') }}</h2>
      <p class="page-subtitle">{{ t('tuning.page.subtitle') }}</p>
    </div>

    <div class="toolbar">
      <el-select v-model="statusFilter" clearable :placeholder="t('tuning.page.filters.status')" style="width: 140px">
        <el-option v-for="s in STATUSES" :key="s" :value="s" :label="t(`common.status.${s}`)" />
      </el-select>
      <el-input
        v-model="keyword"
        clearable
        :placeholder="t('tuning.page.searchPlaceholder')"
        class="search-input"
      >
        <template #prefix><el-icon><Search /></el-icon></template>
      </el-input>
      <el-button size="small" class="toolbar-refresh" @click="load">{{ t('common.refresh') }}</el-button>
    </div>

    <el-empty v-if="!loading && filtered.length === 0" :description="t('tuning.page.empty')" />
    <el-table
      v-else
      v-loading="loading"
      :data="filtered"
      size="small"
      class="tunings-table"
      @row-click="openDetail"
    >
      <el-table-column prop="id" label="#" width="64" />
      <el-table-column :label="t('tuning.page.col.strategy')" min-width="180">
        <template #default="{ row }">
          <el-tag v-if="row.strategy_kind === 'code'" size="small" type="success" class="kind-tag">
            {{ t('tuning.page.kindCode') }}
          </el-tag>
          <el-tag v-else size="small" type="info" class="kind-tag">
            {{ t('tuning.page.kindTemplate') }}
          </el-tag>
          <span>{{ row.strategy_name }}</span>
        </template>
      </el-table-column>
      <el-table-column :label="t('tuning.page.col.stock')" width="130">
        <template #default="{ row }">
          <span>{{ row.stock_code }}</span>
          <el-tag size="small" :type="row.market === 'us' ? 'warning' : 'danger'" class="market-tag">
            {{ row.market === 'us' ? t('common.market.us') : t('common.market.zhA') }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column :label="t('tuning.page.col.range')" width="190">
        <template #default="{ row }">{{ row.start_date }} ~ {{ row.end_date }}</template>
      </el-table-column>
      <el-table-column :label="t('tuning.page.col.target')" width="112">
        <template #default="{ row }">{{ t(`backtest.metric.${row.target_metric}`) }}</template>
      </el-table-column>
      <el-table-column :label="t('tuning.page.col.progress')" width="196">
        <template #default="{ row }">
          <div class="progress-cell">
            <el-progress
              :percentage="progressPct(row)"
              :stroke-width="6"
              :status="progressStatus(row)"
              :show-text="false"
              class="progress-bar"
            />
            <span class="progress-text">{{ row.done_combos }}/{{ row.total_combos }}</span>
          </div>
        </template>
      </el-table-column>
      <el-table-column :label="t('tuning.page.col.best')" width="100">
        <template #default="{ row }">
          <el-tag v-if="row.best_combo_index !== null && row.best_combo_index !== undefined" size="small" type="success">
            #{{ row.best_combo_index }}
          </el-tag>
          <span v-else>—</span>
        </template>
      </el-table-column>
      <el-table-column :label="t('tuning.page.col.status')" width="96">
        <template #default="{ row }">
          <el-tooltip v-if="row.error" :content="row.error" placement="top">
            <el-tag size="small" :type="statusTag(row.status)">{{ t(`common.status.${row.status}`) }}</el-tag>
          </el-tooltip>
          <el-tag v-else size="small" :type="statusTag(row.status)">{{ t(`common.status.${row.status}`) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column :label="t('tuning.page.col.duration')" width="88">
        <template #default="{ row }">{{ fmtDuration(row.duration_ms) }}</template>
      </el-table-column>
      <el-table-column prop="created_at" :label="t('tuning.page.col.created')" width="165" />
      <el-table-column :label="t('tuning.page.col.action')" width="84" fixed="right">
        <template #default="{ row }">
          <el-button text size="small" type="primary" @click.stop="openDetail(row)">
            {{ t('tuning.page.col.detail') }}
          </el-button>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<style scoped>
.tunings-page {
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
.search-input {
  width: 240px;
}
.toolbar-refresh {
  margin-left: auto;
}
.tunings-table {
  cursor: pointer;
}
.tunings-table .kind-tag {
  margin-right: 6px;
}
.tunings-table .market-tag {
  margin-left: 6px;
}
.progress-cell {
  display: flex;
  align-items: center;
  gap: 8px;
}
.progress-bar {
  flex: 1;
  min-width: 90px;
}
.progress-text {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}
</style>
