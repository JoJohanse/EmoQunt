import type { ToolCallEvent } from '@/api/types'

/** 支持卡片化渲染的工具类型（对标 Chat SDK Generative UI 的 tool → 组件映射） */
export type ToolCardKind = 'quote' | 'sentiment' | 'recommend' | 'backtest' | 'signal'

const KIND_BY_TOOL: Record<string, ToolCardKind> = {
  get_stock_quote: 'quote',
  get_index_quote: 'quote',
  get_sentiment: 'sentiment',
  get_daily_recommendations: 'recommend',
  run_backtest: 'backtest',
  get_stock_signal: 'signal',
}

/** 工具名 → 卡片内标题 */
export const TOOL_LABELS: Record<string, string> = {
  get_stock_quote: '行情查询',
  get_index_quote: '指数查询',
  get_sentiment: '舆情查询',
  get_daily_recommendations: '每日推荐',
  run_backtest: '策略回测',
  get_stock_signal: '个股信号',
  list_strategies: '策略列表',
}

/**
 * 判定一个工具调用是否可卡片化渲染。
 * pending 状态只要工具名已知就渲染骨架；结果异常（error JSON / 截断解析失败）回退原始折叠面板。
 */
export function toolCardKind(call: ToolCallEvent): ToolCardKind | null {
  const known = KIND_BY_TOOL[call.name] ?? null
  if (!known) return null
  if (call.pending || call.failed) return known
  return parseToolResult(call) ? known : null
}

/** 解析工具结果 JSON（后端返回 JSON 字符串；error 标记视为失败） */
export function parseToolResult(call: ToolCallEvent): Record<string, any> | null {
  try {
    const data = JSON.parse(call.result)
    if (data && typeof data === 'object' && !Array.isArray(data) && !data.error) {
      return data as Record<string, any>
    }
  } catch {
    // 结果可能被截断或非 JSON：回退原始渲染
  }
  return null
}
