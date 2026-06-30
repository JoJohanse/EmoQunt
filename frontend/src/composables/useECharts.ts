/**
 * ECharts 按需引入，减小打包体积。
 * 提供注册好的 echarts 实例供 vue-echarts 组件使用。
 */
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart, BarChart, HeatmapChart, CandlestickChart } from 'echarts/charts'
import {
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent,
  DataZoomComponent,
  ToolboxComponent,
  VisualMapComponent,
} from 'echarts/components'

// 只注册用到的组件
use([
  CanvasRenderer,
  LineChart,
  BarChart,
  HeatmapChart,
  CandlestickChart,
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent,
  DataZoomComponent,
  ToolboxComponent,
  VisualMapComponent,
])

export { default as VChart } from 'vue-echarts'
