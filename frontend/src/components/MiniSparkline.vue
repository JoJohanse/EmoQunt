<script setup lang="ts">
import { computed } from 'vue'

/**
 * 纯 SVG 迷你走势线（零依赖 sparkline）。
 * 列表规模与刷新频率上量后再评估 uPlot（约 50KB）。
 */
const props = withDefaults(
  defineProps<{
    values: number[]
    width?: number
    height?: number
    color?: string
  }>(),
  { width: 72, height: 22, color: '#667eea' },
)

const points = computed(() => {
  const vals = props.values.filter((v) => Number.isFinite(v))
  if (vals.length < 2) return ''
  const min = Math.min(...vals)
  const max = Math.max(...vals)
  const span = max - min || 1
  const w = props.width - 2
  const h = props.height - 4
  return vals
    .map((v, i) => `${(1 + (i / (vals.length - 1)) * w).toFixed(1)},${(2 + (1 - (v - min) / span) * h).toFixed(1)}`)
    .join(' ')
})
</script>

<template>
  <svg :width="width" :height="height" class="mini-sparkline" aria-hidden="true">
    <polyline
      v-if="points"
      :points="points"
      fill="none"
      :stroke="color"
      stroke-width="1.4"
      stroke-linejoin="round"
      stroke-linecap="round"
    />
  </svg>
</template>

<style scoped>
.mini-sparkline {
  display: block;
  flex-shrink: 0;
}
</style>
