<script setup lang="ts">
import { computed, ref } from 'vue'
import type { SentimentCalendarItem } from '@/api/types'

/**
 * 情绪日历：用 el-calendar 展示历史情绪快照。
 * 有快照的日期显示最强板块情绪分（颜色规则与首页板块一致：>=70 绿、<=40 红、其余灰），
 * 无快照日期留白。点击有数据的日期时 emit select(date)。
 */
const props = defineProps<{
  /** 单日情绪摘要（按日期升序） */
  calendar: SentimentCalendarItem[]
}>()

const emit = defineEmits<{
  (e: 'select', date: string): void
}>()

/** date(YYYY-MM-DD) -> 当日情绪摘要 */
const byDate = computed(() => {
  const map = new Map<string, SentimentCalendarItem>()
  for (const item of props.calendar) {
    if (item?.date) map.set(item.date, item)
  }
  return map
})

/** 当前选中的日期（用于 el-calendar 定位月份，点选有快照日期时触发展开） */
const selected = ref<Date | null>(null)

/** 情绪颜色（与 HomeView 的 sectorColor 规则一致） */
function sentimentColor(sentiment: number): string {
  if (sentiment >= 70) return '#28a745'
  if (sentiment <= 40) return '#dc3545'
  return '#6c757d'
}

function handleSelect(date: string) {
  const item = byDate.value.get(date)
  if (item) emit('select', date)
}
</script>

<template>
  <div class="sentiment-calendar">
    <el-calendar v-model="selected">
      <template #header="{ date }">
        <div class="cal-header">
          <span class="cal-title">{{ date }}</span>
          <span class="cal-hint">有快照的日期显示当日最强板块情绪分</span>
        </div>
      </template>
      <template #date-cell="{ data }">
        <div class="cal-cell" :class="{ 'has-snapshot': byDate.has(data.day) }" @click="handleSelect(data.day)">
          <span class="cal-day">{{ data.day.split('-')[2] }}</span>
          <div v-if="byDate.has(data.day)" class="cal-dot-area">
            <span
              class="cal-dot"
              :style="{ background: sentimentColor(byDate.get(data.day)!.top_sentiment) }"
              :title="`${byDate.get(data.day)!.top_sector_name} · ${byDate.get(data.day)!.top_sentiment}`"
            />
          </div>
        </div>
      </template>
    </el-calendar>
  </div>
</template>

<style scoped>
.sentiment-calendar {
  width: 100%;
}
.cal-header {
  display: flex;
  align-items: baseline;
  gap: 12px;
  flex-wrap: wrap;
}
.cal-title {
  font-weight: 600;
}
.cal-hint {
  font-size: 0.75rem;
  color: var(--text-muted);
}
.cal-cell {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 3px;
  min-height: 44px;
}
.cal-cell.has-snapshot {
  cursor: pointer;
}
.cal-day {
  font-size: 0.85rem;
  line-height: 1;
}
.cal-dot-area {
  height: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
}
.cal-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  display: inline-block;
}
</style>
