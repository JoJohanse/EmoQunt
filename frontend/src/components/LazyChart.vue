<script setup lang="ts">
/**
 * ECharts 懒加载包装（Round3）。
 *
 * echarts+vue-echarts 约 232KB gz，此前经 useECharts 的静态 re-export 随
 * 首页同载，是首屏 bundle 最大头。本组件把「注册副作用 + vue-echarts」整体
 * 放进 defineAsyncComponent 的独立 chunk——首屏不下载，首个 <LazyChart>
 * 渲染时才拉取。首屏视图（HomeView）用它；其余路由页本就是路由级分块，
 * 用原生 VChart 或本组件均可。
 *
 * 实例转发：vue-echarts 把 echarts 实例挂在组件实例的 `.chart` 上
 * （HomeView 的 resetZoom 走 dispatchAction 依赖它）——经 defineExpose
 * 的 getter 透传内层实例，外层模板 ref 语义与直用 VChart 一致。
 */
import { defineAsyncComponent, ref } from 'vue'

const VChart = defineAsyncComponent(() =>
  import('@/composables/useECharts').then((m) => m.VChart),
)

const inner = ref()
defineExpose({
  get chart() {
    return (inner.value as { chart?: unknown } | undefined)?.chart
  },
})
</script>

<template>
  <component :is="VChart" ref="inner" v-bind="$attrs">
    <slot />
  </component>
</template>
