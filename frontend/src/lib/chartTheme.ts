/**
 * 图表暗色适配单点（Round3）。
 *
 * ECharts 的 tooltip 底色 / 轴文字 / 分隔线此前在 HomeView、MarketView 与
 * 各热力图 label 里硬编码白底，暗色主题下图内仍是白卡片。统一从这里按
 * uiStore.theme 派生（computed 响应式：切主题 → option 重算 → 图表重渲染）。
 * 新图表必须消费它，不要再写裸 hex（与 lib/marketColors 的涨跌色分工：
 * 那里管"涨跌语义色"，这里管"主题中性色"）。
 */
import { computed } from 'vue'
import { useUiStore } from '@/stores/ui'

export function chartTheme() {
  const ui = useUiStore()
  const dark = computed(() => ui.theme === 'dark')
  /** 轴/label 主文字色 */
  const text = computed(() => (dark.value ? '#e5e7eb' : '#1f2937'))
  /** 轴/次级文字色 */
  const subText = computed(() => (dark.value ? '#9ca3af' : '#6b7280'))
  /** 网格分隔线 */
  const splitLine = computed(() => (dark.value ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.08)'))
  /** tooltip 底色（原各视图硬编码 rgba(255,255,255,0.97) 的替代） */
  const tooltipBg = computed(() => (dark.value ? 'rgba(31, 41, 55, 0.96)' : 'rgba(255, 255, 255, 0.97)'))
  /** 热力图等的中性档位色（visualMap inRange 中点） */
  const neutral = computed(() => (dark.value ? '#4b5563' : '#f5f5f5'))
  return { dark, text, subText, splitLine, tooltipBg, neutral }
}
