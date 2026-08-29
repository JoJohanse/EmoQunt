<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'

/**
 * 数值滚动组件：值变化时以 rAF 补间过渡（行情软件式数字滚动微交互）。
 * 自研 ~30 行 rAF tween，替代为单个 useTransition 引入 @vueuse 整包。
 */
const props = withDefaults(
  defineProps<{
    value: number
    duration?: number
    decimals?: number
  }>(),
  { duration: 500, decimals: 2 },
)

const display = ref(props.value)
let raf = 0

watch(
  () => props.value,
  (to, from) => {
    cancelAnimationFrame(raf)
    const start = performance.now()
    const step = (now: number) => {
      const t = Math.min(1, (now - start) / props.duration)
      const eased = 1 - Math.pow(1 - t, 3)
      display.value = from + (to - from) * eased
      if (t < 1) raf = requestAnimationFrame(step)
    }
    raf = requestAnimationFrame(step)
  },
)

onBeforeUnmount(() => cancelAnimationFrame(raf))

const text = computed(() =>
  display.value.toLocaleString('zh-CN', {
    minimumFractionDigits: props.decimals,
    maximumFractionDigits: props.decimals,
  }),
)
</script>

<template>
  <span class="anim-number">{{ text }}</span>
</template>

<style scoped>
.anim-number {
  font-variant-numeric: tabular-nums;
}
</style>
