import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { ChatMessage, SseEvent } from '@/api/types'
import { chatStream } from '@/api/chat'

export const useChatStore = defineStore(
  'chat',
  () => {
  const messages = ref<ChatMessage[]>([
    {
      role: 'assistant',
      content:
        '你好！我是 EmoQunt AI 投资助手。我可以帮你查询行情、运行回测、分析舆情与推荐个股。试试问：\n\n- 帮我看看 000001 最近行情\n- 运行 test 策略回测 000001\n- 今天哪些板块情绪最高？\n- 推荐几只股票',
    },
  ])
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
          } else if (evt.type === 'tool') {
            assistantMsg.toolCalls = assistantMsg.toolCalls || []
            assistantMsg.toolCalls.push({ name: evt.name, args: evt.args, result: evt.result })
          } else if (evt.type === 'error') {
            assistantMsg.error = evt.content
          }
          // done: 结束 streaming
        },
        abortCtrl.signal,
      )
    } catch (e: any) {
      if (e.name === 'AbortError') {
        assistantMsg.content += '\n\n_(已取消)_'
      } else {
        assistantMsg.error = e.message || '对话失败'
      }
    } finally {
      assistantMsg.streaming = false
      loading.value = false
      abortCtrl = null
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
