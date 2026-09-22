import type { Component } from 'vue'
import { Aim, DataAnalysis, Search, TrendCharts } from '@element-plus/icons-vue'

/**
 * 对话启动卡片（ChatPanel 空态）：分组 → 卡片的两级结构。
 *
 * 每张卡片只有两个字段：`q` 是**提问词表键**（chat 命名空间，zh/en 对称），点击时
 * 由面板现算 t(key) 后直接 send()——所以卡片文案随界面语言即时切换，且进对话后
 * 就变成真实的用户消息原文（历史消息保持当时的语言）。
 *
 * 新增卡片 = 这里加一行 + 词表中英各一条，不要在组件里硬编码提问文本。
 */
export interface StarterCard {
  /** chat 词表中的提问键（如 starter.cards.ma） */
  q: string
  /** 卡片图标（Element Plus 图标组件；卡片是静态列表，无需响应式） */
  icon: Component
}

export interface StarterGroup {
  /** chat 词表中的组标题键（如 starter.groups.strategy） */
  title: string
  cards: StarterCard[]
}

export const starterGroups: StarterGroup[] = [
  {
    title: 'chat.starter.groups.strategy',
    cards: [
      { q: 'chat.starter.cards.ma', icon: TrendCharts },
      { q: 'chat.starter.cards.tuning', icon: Aim },
    ],
  },
  {
    title: 'chat.starter.groups.factor',
    cards: [{ q: 'chat.starter.cards.factor', icon: DataAnalysis }],
  },
  {
    title: 'chat.starter.groups.data',
    cards: [
      { q: 'chat.starter.cards.quote', icon: Search },
      { q: 'chat.starter.cards.sentiment', icon: TrendCharts },
    ],
  },
]
