<script setup lang="ts">
/**
 * RunDetailDialog —— 单次回测运行详情弹窗（运行历史页与策略详情页共用）。
 * 只负责展示：指标四格 + 净值曲线 + 阶段耗时 + 失败原因；数据由调用方传入
 * （runsApi.detail 的结果）。文案住 runs.runDetail.*；状态走 common.status.*，
 * 指标名走 backtest.metric.<中文键>。
 */
import { computed } from 'vue'
import type { BacktestRunDetail } from '@/api/types'
import { chartPalette } from '@/lib/marketColors'
import { t } from '@/locales'
import { VChart } from '@/composables/useECharts'

const props = defineProps<{
  run: BacktestRunDetail | null
  visible: boolean
}>()

const emit = defineEmits<{ (e: 'update:visible', v: boolean): void }>()

const dialogVisible = computed({
  get: () => props.visible,
  set: (v: boolean) => emit('update:visible', v),
})

const equityOption = computed(() => {
  const run = props.run
  if (!run || !run.equity_curve.length) return {}
  const color = chartPalette(run.market).up
  return {
    tooltip: { trigger: 'axis' },
    grid: { left: 60, right: 24, top: 24, bottom: 52 },
    xAxis: { type: 'category', data: run.dates },
    yAxis: { type: 'value', scale: true },
    dataZoom: [{ type: 'inside' }],
    series: [{ type: 'line', data: run.equity_curve, showSymbol: false, lineStyle: { color, width: 1.6 } }],
  }
})

function statusTag(s: string): string {
  const map: Record<string, string> = {
    queued: 'info', running: 'primary', succeeded: 'success', failed: 'danger', cancelled: 'warning',
  }
  return map[s] ?? 'info'
}

function stageLabel(stage: string): string {
  const map: Record<string, string> = {
    fetch_data: 'stagesFetchData', load_strategy: 'stagesLoadStrategy', backtest: 'stagesBacktest',
    metrics: 'stagesMetrics', benchmark: 'stagesBenchmark', enrich: 'stagesEnrich',
  }
  const key = map[stage]
  return key ? t(`runs.runDetail.${key}`) : stage
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
</script>

<template>
  <el-dialog v-model="dialogVisible" :title="t('runs.runDetail.title')" width="860px">
    <template v-if="run">
      <el-alert
        v-if="run.status === 'failed'"
        type="error"
        :title="t('runs.runDetail.errorLabel')"
        :description="run.error || ''"
        :closable="false"
        class="detail-alert"
      />
      <div class="info-line">
        <span>#{{ run.id }}</span>
        <el-tag size="small" :type="statusTag(run.status)">{{ t(`common.status.${run.status}`) }}</el-tag>
        <el-tag size="small" type="info">{{ run.strategy_kind === 'code' ? t('runs.kindCode') : t('runs.kindTemplate') }}</el-tag>
        <span>{{ run.strategy_name }}</span>
        <span class="info-muted">{{ run.stock_code }} · {{ run.market === 'us' ? t('common.market.us') : t('common.market.zhA') }}</span>
        <span class="info-muted">{{ run.start_date }} ~ {{ run.end_date }}</span>
        <span class="info-muted">{{ t('runs.runDetail.duration') }} {{ fmtDuration(run.duration_ms) }}</span>
      </div>
      <template v-if="run.metrics">
        <div class="metric-grid">
          <div class="metric-item">
            <span class="metric-label">{{ t('backtest.metric.总收益率') }}</span>
            <span class="metric-value">{{ fmtPct(run.metrics['总收益率']) }}</span>
          </div>
          <div class="metric-item">
            <span class="metric-label">{{ t('backtest.metric.夏普比率') }}</span>
            <span class="metric-value">{{ fmtNum(run.metrics['夏普比率']) }}</span>
          </div>
          <div class="metric-item">
            <span class="metric-label">{{ t('backtest.metric.最大回撤') }}</span>
            <span class="metric-value">{{ fmtPct(run.metrics['最大回撤']) }}</span>
          </div>
          <div class="metric-item">
            <span class="metric-label">{{ t('runs.runDetail.tradesCount') }}</span>
            <span class="metric-value">{{ run.trades?.length ?? run.metrics['交易次数'] ?? '—' }}</span>
          </div>
        </div>
        <v-chart v-if="run.equity_curve.length" class="run-chart" :option="equityOption" autoresize />
        <div v-if="run.stages.length" class="stage-row">
          <span class="stage-title">{{ t('runs.runDetail.stages') }}：</span>
          <el-tag v-for="st in run.stages" :key="st.stage" size="small" type="info" class="stage-tag">
            {{ stageLabel(st.stage) }} {{ st.ms }}ms
          </el-tag>
        </div>
      </template>
    </template>
  </el-dialog>
</template>

<style scoped>
.detail-alert {
  margin-bottom: 10px;
}
.info-line {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
  margin-bottom: 12px;
  font-size: 13px;
}
.info-muted {
  color: var(--el-text-color-secondary);
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
</style>
