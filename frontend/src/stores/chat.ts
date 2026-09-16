import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { ChatMessage, SseEvent } from '@/api/types'
import { chatStream } from '@/api/chat'
import { t } from '@/locales'

/**
 * 初始欢迎语（含 4 条示例问题）：只在没有本地持久化消息时显示，
 * 因此用 t() 在 store 初始化时按当前语言生成（切换语言后欢迎语保持原语言，视作历史消息）。
 */
function greeting(): ChatMessage {
  const samples = [
    t('chat.sampleQuote'),
    t('chat.sampleBacktest'),
    t('chat.sampleSentiment'),
    t('chat.sampleRecommend'),
  ]
  return {
    role: 'assistant',
    content: `${t('chat.greeting')}\n\n${samples.map((s) => `- ${s}`).join('\n')}`,
  }
}

export const useChatStore = defineStore(
  'chat',
  () => {
  const messages = ref<ChatMessage[]>([greeting()])
  const loading = ref(false)
  const drawerOpen = ref(false)
  let abortCtrl: AbortController | null = null

  function toggleDrawer() {
    drawerOpen.value = !drawerOpen.value
  }

  function openDrawer() {
    drawerOpen.value = true
  }

  /** 发送一条用户消息并流式接收回复 */
  async function send(text: string) {
    const trimmed = text.trim()
    if (!trimmed || loading.value) return

    // 追加用户消息
    messages.value.push({ role: 'user', content: trimmed })
    // 对话记录上限 100 条，超出时截掉最旧的消息（本地持久化体积可控）
    if (messages.value.length > 100) {
      messages.value = messages.value.slice(-100)
    }
    // 占位 assistant 消息（流式填充）
    const assistantMsg: ChatMessage = {
      role: 'assistant',
      content: '',
      toolCalls: [],
      streaming: true,
    }
    messages.value.push(assistantMsg)

    loading.value = true
    abortCtrl = new AbortController()
    try {
      await chatStream(
        messages.value.slice(0, -1), // 不含占位的空 assistant
        (evt: SseEvent) => {
          if (evt.type === 'token') {
            assistantMsg.content += evt.content
          } else if (evt.type === 'tool_start') {
            // 工具开始执行：先渲染"查询中"骨架卡片
            assistantMsg.toolCalls = assistantMsg.toolCalls || []
            assistantMsg.toolCalls.push({ name: evt.name, args: evt.args, result: '', pending: true })
          } else if (evt.type === 'tool') {
            assistantMsg.toolCalls = assistantMsg.toolCalls || []
            // 优先回填同名 pending 调用（tool_start → tool 的状态机）
            const pending = [...assistantMsg.toolCalls]
              .reverse()
              .find((c) => c.pending && c.name === evt.name)
            if (pending) {
              pending.args = evt.args || pending.args
              pending.result = evt.result
              pending.pending = false
            } else {
              assistantMsg.toolCalls.push({ name: evt.name, args: evt.args, result: evt.result })
            }
          } else if (evt.type === 'error') {
            assistantMsg.error = evt.content
          }
          // done: 结束 streaming
        },
        abortCtrl.signal,
      )
    } catch (e: any) {
      if (e.name === 'AbortError') {
        // 取消标记落在消息正文里（历史消息保持当时的语言，不随界面语言迁移）
        assistantMsg.content += `\n\n${t('chat.cancelled')}`
      } else {
        assistantMsg.error = e.message || t('chat.failed')
      }
    } finally {
      assistantMsg.streaming = false
      loading.value = false
      abortCtrl = null
      // 流结束后仍未回填结果的工具调用标记为失败（骨架卡片转错误态）
      for (const c of assistantMsg.toolCalls || []) {
        if (c.pending) {
          c.pending = false
          c.failed = true
        }
      }
    }
  }

  /** 取消当前流式请求 */
  function cancel() {
    if (abortCtrl) {
      abortCtrl.abort()
    }
  }

  /** 清空对话 */
  function clear() {
    messages.value = []
  }

  return { messages, loading, drawerOpen, toggleDrawer, openDrawer, send, cancel, clear }
}, {
  // 本地持久化：对话记录刷新后保留（只存消息；恢复时清理流式标记并截断上限）
  persist: {
    pick: ['messages'],
    revive: (state: Record<string, any>) => {
      const msgs = Array.isArray(state.messages) ? state.messages : []
      const trimmed = msgs.slice(-100)
      for (const m of trimmed) {
        m.streaming = false
      }
      return { messages: trimmed }
    },
  },
})
