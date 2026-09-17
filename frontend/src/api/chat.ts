/**
 * AI 助手对话 API（SSE 流式）。
 *
 * 使用 fetch + ReadableStream 解析 SSE，绕过 axios 的 JSON-only 限制。
 * 后端端点：POST /api/agent/chat（SSE），POST /api/agent/chat/sync（非流式）。
 */
import type { ChatMessage, SseEvent } from './types'
import { t } from '@/locales'

/**
 * 流式发送对话，通过回调逐事件返回。
 *
 * @param messages 历史消息（含本轮 user 输入）
 * @param onEvent 事件回调（token/tool/done/error）
 * @param signal AbortSignal，用于取消
 * @param strategyId 绑定的策略库代码策略 id（可选；非空时后端将其注入对话上下文）
 */
export async function chatStream(
  messages: ChatMessage[],
  onEvent: (evt: SseEvent) => void,
  signal?: AbortSignal,
  strategyId?: number | null,
): Promise<void> {
  const resp = await fetch('/api/agent/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      messages: messages.map((m) => ({ role: m.role, content: m.content })),
      // 绑定策略上下文：仅在用户显式选择时携带（null 不发，保持旧请求体形状）
      ...(strategyId != null ? { strategy_id: strategyId } : {}),
    }),
    signal,
  })

  if (!resp.ok || !resp.body) {
    const txt = await resp.text().catch(() => '')
    // 调用时取词：错误文案跟随当前界面语言
    throw new Error(`${t('chat.requestFailedStatus', { status: resp.status })} ${txt}`)
  }

  const reader = resp.body.getReader()
  const decoder = new TextDecoder('utf-8')
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    // SSE 以 \n\n 分隔事件
    let idx: number
    while ((idx = buffer.indexOf('\n\n')) >= 0) {
      const raw = buffer.slice(0, idx)
      buffer = buffer.slice(idx + 2)
      const line = raw.trim()
      if (!line.startsWith('data:')) continue
      const jsonStr = line.slice(5).trim()
      if (!jsonStr) continue
      try {
        const evt = JSON.parse(jsonStr) as SseEvent
        onEvent(evt)
      } catch {
        // 忽略无法解析的行
      }
    }
  }
}

/** 非流式对话（测试/兜底用） */
export async function chatSync(messages: ChatMessage[], strategyId?: number | null): Promise<string> {
  const resp = await fetch('/api/agent/chat/sync', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      messages: messages.map((m) => ({ role: m.role, content: m.content })),
      ...(strategyId != null ? { strategy_id: strategyId } : {}),
    }),
  })
  const data = await resp.json()
  if (!resp.ok) throw new Error(data.error || t('chat.requestFailed'))
  return data.reply as string
}
