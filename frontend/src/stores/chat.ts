import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import type { ChatMessage, SseEvent } from '@/api/types'
import { chatStream } from '@/api/chat'
import { t } from '@/locales'

/** 会话的默认标题（中文原文，语言无关的标记；展示时经 chat.sessions.untitled 现算） */
export const DEFAULT_SESSION_TITLE = '新会话'

/** 每个会话保留的消息条数上限（本地持久化体积可控） */
const MAX_MESSAGES = 100

/** 总会话数上限（超出时丢弃最旧——列表插入序即创建序） */
const MAX_SESSIONS = 20

/** 会话标题自动生成：首条用户消息的前 18 个字符 */
const TITLE_MAX = 18

/** 一次对话会话（多会话工作台的基本单元） */
export interface ChatSession {
  id: string
  title: string
  createdAt: string
  /** 置顶：会话栏排序时排在最前 */
  pinned?: boolean
  messages: ChatMessage[]
}

/** 生成会话 id（浏览器环境走 crypto.randomUUID，缺失/非安全上下文时降级为随机串） */
function makeId(): string {
  const c = globalThis.crypto as Crypto | undefined
  if (c && typeof c.randomUUID === 'function') return c.randomUUID()
  return `s-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`
}

function makeSession(): ChatSession {
  return { id: makeId(), title: DEFAULT_SESSION_TITLE, createdAt: new Date().toISOString(), messages: [] }
}

/** 消息条数截断（保留最近 MAX_MESSAGES 条） */
function capMessages(messages: ChatMessage[]): ChatMessage[] {
  return messages.length > MAX_MESSAGES ? messages.slice(-MAX_MESSAGES) : messages
}

/** 标题是否仍是默认（新建后未发过消息；旧版本持久化可能留空标题） */
function isDefaultTitle(title: string): boolean {
  return !title || title === DEFAULT_SESSION_TITLE
}

/**
 * 助手消息若**紧跟**在用户消息之后，则为该提问的流式回复——纯静态欢迎语永远在 array 首位，
 * 因此这条判据不会误伤旧数据里的真实对话（形态与旧版的"greeting 存进 messages"约定兼容）。
 */
function isOrphanAssistant(msgs: ChatMessage[], i: number, msg: ChatMessage): boolean {
  return msg.role === 'assistant' && !msgs[i - 1]
}

/** 归一化单条消息：剥掉流式标记，只保留渲染需要的字段 */
function sanitizeMessage(msg: unknown): ChatMessage | null {
  if (!msg || typeof msg !== 'object') return null
  const m = msg as Record<string, any>
  if (m.role !== 'user' && m.role !== 'assistant' && m.role !== 'system') return null
  const clean: ChatMessage = { role: m.role, content: typeof m.content === 'string' ? m.content : '' }
  if (Array.isArray(m.toolCalls)) clean.toolCalls = m.toolCalls
  if (typeof m.error === 'string') clean.error = m.error
  return clean
}

/** 归一化单个会话：补默认标题/创建时间、清理消息（流式标记 + 条数上限 + 静态欢迎语） */
function sanitizeSession(raw: unknown): ChatSession | null {
  if (!raw || typeof raw !== 'object') return null
  const r = raw as Record<string, any>
  const rawMessages = Array.isArray(r.messages) ? r.messages : []
  const messages: ChatMessage[] = []
  rawMessages.forEach((item: unknown, i: number) => {
    const clean = sanitizeMessage(item)
    // 旧版把静态欢迎语存在 messages 首位，多会话下改由面板渲染空态：开头那条孤立助手消息丢弃
    if (!clean || isOrphanAssistant(rawMessages as ChatMessage[], i, clean)) return
    messages.push(clean)
  })
  return {
    id: typeof r.id === 'string' && r.id ? r.id : makeId(),
    title: typeof r.title === 'string' && r.title ? r.title : DEFAULT_SESSION_TITLE,
    createdAt: typeof r.createdAt === 'string' ? r.createdAt : new Date().toISOString(),
    ...(r.pinned === true ? { pinned: true } : {}),
    messages: capMessages(messages),
  }
}

/**
 * 恢复持久化状态：兼容三种形态——旧版单会话（messages）/ 新版多会话（sessions）/ 无数据，
 * 产物恒为「≥1 个会话」并把 activeId 落在真实存在的会话上。
 */
function reviveState(state: Record<string, any>): Record<string, any> {
  // 无任何可识别的本地数据时不改动 state（首次访问 / 旧数据已被清掉）：
  // 此时保留初始化时创建的空会话，避免把 store 清成"零会话"异常态
  if (!Array.isArray(state.sessions) && !Array.isArray(state.messages)) {
    return { contextStrategyId: keepStrategyId(state) }
  }
  let sessions: ChatSession[] = []
  if (Array.isArray(state.sessions)) {
    // 新版：逐个归一化（含消息清理与标题兜底）
    sessions = state.sessions
      .map((item: unknown) => sanitizeSession(item))
      .filter((s: ChatSession | null): s is ChatSession => s !== null)
  } else if (Array.isArray(state.messages)) {
    // 旧版单会话数据 → 迁移为一个会话（标题按首条用户消息现算，与新建会话口径一致）
    const messages: ChatMessage[] = []
    state.messages.forEach((item: unknown, i: number) => {
      const clean = sanitizeMessage(item)
      if (!clean || isOrphanAssistant(state.messages as ChatMessage[], i, clean)) return
      messages.push(clean)
    })
    // 迁移后若只剩助手消息（旧库里的静态欢迎语），视作空会话、不带标题
    const hasUser = messages.some((m) => m.role === 'user')
    if (messages.length) sessions = [{ ...makeSession(), messages: capMessages(messages), ...(hasUser ? { title: deriveTitle(messages) } : {}) }]
  }
  // 总会话数上限：保留最近创建的 MAX_SESSIONS 个
  if (sessions.length > MAX_SESSIONS) sessions = sessions.slice(-MAX_SESSIONS)
  // 兜底：字段存在但全部不可用（损坏/被清空）时退回初始化时的空会话
  if (!sessions.length) sessions = [makeSession()]
  // activeId 失效（缺失/指向已删会话）时回落到第一个会话
  const activeId =
    typeof state.activeId === 'string' && sessions.some((s) => s.id === state.activeId)
      ? state.activeId
      : sessions[0].id
  return { sessions, activeId, contextStrategyId: keepStrategyId(state) }
}

/** 绑定策略 id：仅接受数字/空，其他形状一律回退 null（原行为） */
function keepStrategyId(state: Record<string, any>): number | null {
  return typeof state.contextStrategyId === 'number' ? state.contextStrategyId : null
}

/** 首条用户消息的前 18 字符作为会话标题（无用户消息时返回默认标题） */
function deriveTitle(messages: ChatMessage[]): string {
  const firstUser = messages.find((m) => m.role === 'user' && m.content)
  if (!firstUser) return DEFAULT_SESSION_TITLE
  return firstUser.content.slice(0, TITLE_MAX)
}

/**
 * 多会话对话 store。
 *
 * 对外契约：`messages` 是**当前活跃会话**消息数组的 computed——ChatPanel 的
 * `v-for="msg in messages"` 与发送逻辑无需关心会话层；`send` / `cancel` / `clear`
 * 一律作用于活跃会话。`contextStrategyId` 保持不变（全局绑定，不随会话走）。
 * 静态欢迎语与启动卡片由面板按 t() 现算（不入库，切语言即时变）。
 */
export const useChatStore = defineStore(
  'chat',
  () => {
    // 初次访问（无本地持久化）也要有一个可用的空会话——revive 只在有存档时被调用，
    // 因此首个会话在初始化时就建好，删除全部会话时同样由 removeSession 兜底补一个
    const initial = makeSession()
    const sessions = ref<ChatSession[]>([initial])
    // 活跃会话 id（名称沿用：内部标识为 id，对外暴露为 activeId）
    const activeId = ref<string>(initial.id)
    const loading = ref(false)
    const drawerOpen = ref(false)
    // 绑定的策略库代码策略 id（发给后端注入对话上下文；持久化 id 本身，名称不落盘）
    const contextStrategyId = ref<number | null>(null)
    let abortCtrl: AbortController | null = null

    /** 会话栏展示顺序：置顶在前，其余按创建时间倒序（同刻创建则按列表位置兜底） */
    const orderedSessions = computed(() =>
      [...sessions.value].sort((a, b) => {
        if (!!a.pinned !== !!b.pinned) return a.pinned ? -1 : 1
        const diff = Date.parse(b.createdAt) - Date.parse(a.createdAt)
        if (!Number.isNaN(diff) && diff !== 0) return diff
        return sessions.value.indexOf(b) - sessions.value.indexOf(a)
      }),
    )

    const activeSession = computed(() => sessions.value.find((s) => s.id === activeId.value) ?? null)

    /** 当前活跃会话的消息（无活跃会话时为空数组） */
    const messages = computed<ChatMessage[]>(() => activeSession.value?.messages ?? [])

    function toggleDrawer() {
      drawerOpen.value = !drawerOpen.value
    }

    function openDrawer() {
      drawerOpen.value = true
    }

    /** 新建空会话并激活（标题走默认标记，首条用户消息到达时自动生成） */
    function newSession(): string {
      const created = makeSession()
      sessions.value.push(created)
      activeId.value = created.id
      return created.id
    }

    /** 切换活跃会话（id 不存在时静默忽略） */
    function switchTo(id: string) {
      if (sessions.value.some((s) => s.id === id)) activeId.value = id
    }

    function sessionById(id: string): ChatSession | null {
      return sessions.value.find((s) => s.id === id) ?? null
    }

    /** 置顶/取消置顶（排序由 orderedSessions 现算） */
    function togglePin(id: string) {
      const target = sessionById(id)
      if (target) target.pinned = !target.pinned
    }

    /** 重命名会话（空标题忽略；不提供删除所以不会写空） */
    function renameSession(id: string, title: string) {
      const target = sessionById(id)
      const trimmed = title.trim()
      if (target && trimmed) target.title = trimmed
    }

    /** 删除会话：删的是活跃会话时切到最近一个；全删光则自动补一个空会话 */
    function removeSession(id: string) {
      const before = sessions.value.length
      sessions.value = sessions.value.filter((s) => s.id !== id)
      if (sessions.value.length !== before && !sessions.value.some((s) => s.id === activeId.value)) {
        const next = orderedSessions.value[0]
        if (next) activeId.value = next.id
        else newSession()
      }
    }

    /** 发送一条用户消息并流式接收回复（作用于当前活跃会话） */
    async function send(text: string) {
      const trimmed = text.trim()
      if (!trimmed || loading.value) return
      let session = activeSession.value
      if (!session) {
        // 兜底：会话列表为空时先建一个（revive 已保证非空，此处防御异常态）
        newSession()
        session = activeSession.value
      }
      if (!session) return

      // 追加用户消息；首条用户消息顺手产出会话标题
      session.messages.push({ role: 'user', content: trimmed })
      if (isDefaultTitle(session.title)) session.title = deriveTitle(session.messages)
      session.messages = capMessages(session.messages)

      // 占位 assistant 消息（流式填充）
      const assistantMsg: ChatMessage = {
        role: 'assistant',
        content: '',
        toolCalls: [],
        streaming: true,
      }
      session.messages.push(assistantMsg)

      loading.value = true
      abortCtrl = new AbortController()
      try {
        await chatStream(
          session.messages.slice(0, -1), // 不含占位的空 assistant
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
          // 绑定的代码策略 id（null 时请求体不带 strategy_id）
          contextStrategyId.value,
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

    /** 清空**当前会话**的对话（新建会话请用 newSession——QUBE 语义） */
    function clear() {
      const session = activeSession.value
      if (session) session.messages = []
    }

    return {
      sessions,
      activeId,
      orderedSessions,
      activeSession,
      messages,
      loading,
      drawerOpen,
      contextStrategyId,
      toggleDrawer,
      openDrawer,
      newSession,
      switchTo,
      togglePin,
      renameSession,
      removeSession,
      send,
      cancel,
      clear,
    }
  },
  {
    // 本地持久化：多会话数组 + 活跃会话 id + 绑定策略 id（只存 id 不存名称）
    persist: {
      pick: ['sessions', 'activeId', 'contextStrategyId'],
      revive: reviveState,
    },
  },
)
