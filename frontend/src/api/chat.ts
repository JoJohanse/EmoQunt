/**
 * AI 助手对话 API（SSE 流式）。
 *
 * 使用 fetch + ReadableStream 解析 SSE，绕过 axios 的 JSON-only 限制。
 * 后端端点：POST /api/agent/chat（SSE），POST /api/agent/chat/sync（非流式）。
 */
import type { ChatMessage, SseEvent } from './types'

/**
 * 流式发送对话，通过回调逐事件返回。
 *
 * @param messages 历史消息（含本轮 user 输入）
 * @param onEvent 事件回调（token/tool/done/error）
 * @param signal AbortSignal，用于取消
 */
export async function chatStream(
  messages: ChatMessage[],
  onEvent: (evt: SseEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const resp = await fetch('/api/agent/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      messages: messages.map((m) => ({ role: m.role, content: m.content })),
    }),
    signal,
  })

  if (!resp.ok || !resp.body) {
    const txt = await resp.text().catch(() => '')
    throw new Error(`请求失败 (${resp.status}) ${txt}`)
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
export async function chatSync(messages: ChatMessage[]): Promise<string> {
  const resp = await fetch('/api/agent/chat/sync', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      messages: messages.map((m) => ({ role: m.role, content: m.content })),
    }),
  })
  const data = await resp.json()
  if (!resp.ok) throw new Error(data.error || '请求失败')
  return data.reply as string
}
