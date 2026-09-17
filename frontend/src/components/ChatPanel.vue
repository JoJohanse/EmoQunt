<script setup lang="ts">
import { ref, computed, nextTick, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { useChatStore } from '@/stores/chat'
import { libraryApi } from '@/api'
import type { CodeStrategySummary } from '@/api/types'
import MarkdownIt from 'markdown-it'
import ChatToolCard from '@/components/ChatToolCard.vue'
import { toolCardKind } from '@/components/chat/toolCards'
import { t } from '@/locales'

const store = useChatStore()
const { messages, loading } = storeToRefs(store)

const inputText = ref('')
const messagesContainer = ref<HTMLElement | null>(null)

const md = new MarkdownIt({ html: false, linkify: true, breaks: true })

function render(content: string): string {
  try {
    return md.render(content || '')
  } catch {
    return content
  }
}

// ===== 绑定策略（发给后端注入对话上下文；持久化只存 id，名称留在内存） =====
const strategyOptions = ref<CodeStrategySummary[]>([])
const strategiesLoaded = ref(false)
const strategiesLoading = ref(false)

/** 惰性加载一次：面板首次打开或首次聚焦输入时触发；失败允许下次重试 */
async function loadStrategyOptions() {
  if (strategiesLoaded.value || strategiesLoading.value) return
  strategiesLoading.value = true
  try {
    const resp = await libraryApi.list()
    strategyOptions.value = resp.strategies
    strategiesLoaded.value = true
  } catch {
    // 静默降级：选择器留空，下次聚焦重试
  } finally {
    strategiesLoading.value = false
  }
}

// 抽屉首次打开即预取（ChatPanel 挂载在 el-drawer 内，首次打开才实例化——
// 此时 drawerOpen 已是 true，故 immediate 补上首开场景）
watch(
  () => store.drawerOpen,
  (open) => {
    if (open) void loadStrategyOptions()
  },
  { immediate: true },
)

/** 选中写 store（持久化 id）；clearable 清空（undefined/''）归一为 null */
const binding = computed<number | null>({
  get: () => store.contextStrategyId,
  set: (v) => {
    store.contextStrategyId = typeof v === 'number' ? v : null
  },
})
/** 绑定策略的展示名：优先取已加载列表中的名称，列表未就绪时回退 #id（不持久化） */
const boundName = computed(() => {
  const id = store.contextStrategyId
  if (id == null) return ''
  return strategyOptions.value.find((s) => s.id === id)?.name || `#${id}`
})

async function onSend() {
  const text = inputText.value
  if (!text.trim() || loading.value) return
  inputText.value = ''
  await store.send(text)
}

function onKeydown(e: KeyboardEvent) {
  // 回车发送，Shift+回车换行
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    onSend()
  }
}

// 消息更新时自动滚动到底部
watch(
  () => messages.value.map((m) => m.content).join(''),
  async () => {
    await nextTick()
    if (messagesContainer.value) {
      messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
    }
  },
)
</script>

<template>
  <div class="chat-panel">
    <div ref="messagesContainer" class="messages">
      <div
        v-for="(msg, i) in messages"
        :key="i"
        class="msg-row"
        :class="msg.role"
      >
        <div class="avatar">
          <el-icon v-if="msg.role === 'user'"><User /></el-icon>
          <el-icon v-else><ChatDotRound /></el-icon>
        </div>
        <div class="bubble-wrap">
          <!-- 工具调用：已知工具渲染结果卡片，其余折叠展示原始参数/结果 -->
          <div v-if="msg.toolCalls && msg.toolCalls.length" class="tool-calls">
            <template v-for="(tc, j) in msg.toolCalls" :key="j">
              <ChatToolCard v-if="toolCardKind(tc)" :call="tc" />
              <el-collapse v-else>
                <el-collapse-item
                  :title="`🔧 ${tc.name}`"
                  :name="j"
                >
                  <div class="tool-detail">
                    <div class="tool-section"><strong>{{ t('chat.args') }}</strong><code>{{ tc.args }}</code></div>
                    <div class="tool-section"><strong>{{ t('chat.result') }}</strong><pre>{{ tc.result }}</pre></div>
                  </div>
                </el-collapse-item>
              </el-collapse>
            </template>
          </div>
          <!-- 消息内容（Markdown 渲染） -->
          <div class="bubble" :class="msg.role">
            <div v-if="msg.content" class="markdown-body" v-html="render(msg.content)"></div>
            <span v-if="msg.streaming" class="cursor">▋</span>
            <div v-if="msg.error" class="error-text">
              <el-icon><WarningFilled /></el-icon> {{ msg.error }}
            </div>
          </div>
        </div>
      </div>
    </div>

    <div class="input-area">
      <!-- 绑定策略栏：选择后随对话请求携带 strategy_id，徽章显示策略名（不持久化） -->
      <div class="bind-bar">
        <span class="bind-label">{{ t('chat.bindStrategy') }}</span>
        <el-select
          v-model="binding"
          class="bind-select"
          size="small"
          filterable
          clearable
          :placeholder="t('chat.bindStrategyPlaceholder')"
          :loading="strategiesLoading"
          @focus="loadStrategyOptions"
        >
          <el-option v-for="s in strategyOptions" :key="s.id" :value="s.id" :label="s.name" />
        </el-select>
        <el-tag v-if="store.contextStrategyId != null" size="small" effect="plain" class="bind-badge">
          {{ boundName }}
        </el-tag>
      </div>
      <el-input
        v-model="inputText"
        type="textarea"
        :rows="2"
        resize="none"
        :placeholder="t('chat.placeholder')"
        :disabled="loading"
        @focus="loadStrategyOptions"
        @keydown="onKeydown"
      />
      <div class="input-actions">
        <el-button text size="small" @click="store.clear" :disabled="loading">{{ t('chat.clear') }}</el-button>
        <el-button v-if="loading" type="danger" plain size="small" @click="store.cancel">
          <el-icon><VideoPause /></el-icon> {{ t('chat.stop') }}
        </el-button>
        <el-button type="primary" size="small" :loading="loading" @click="onSend">
          <el-icon><Promotion /></el-icon> {{ t('chat.send') }}
        </el-button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.chat-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
}
.messages {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.msg-row {
  display: flex;
  gap: 10px;
  align-items: flex-start;
}
.msg-row.user {
  flex-direction: row-reverse;
}
.avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  font-size: 16px;
  color: #fff;
}
.msg-row.user .avatar {
  background: var(--brand-start);
}
.msg-row.assistant .avatar {
  background: var(--brand-grad);
}
.bubble-wrap {
  max-width: 82%;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.msg-row.user .bubble-wrap {
  align-items: flex-end;
}
.bubble {
  padding: 10px 14px;
  border-radius: 12px;
  font-size: 0.92rem;
  line-height: 1.6;
  word-break: break-word;
}
.bubble.assistant {
  background: #f4f5f7;
  color: var(--text);
  border-top-left-radius: 4px;
}
.bubble.user {
  background: var(--brand-grad);
  color: #fff;
  border-top-right-radius: 4px;
}
.cursor {
  display: inline-block;
  animation: blink 1s infinite;
  color: var(--brand-start);
}
@keyframes blink {
  0%, 50% { opacity: 1; }
  51%, 100% { opacity: 0; }
}
.error-text {
  color: var(--danger);
  font-size: 0.85rem;
  margin-top: 6px;
  display: flex;
  align-items: center;
  gap: 4px;
}
.tool-calls {
  font-size: 0.8rem;
}
.tool-calls :deep(.el-collapse-item__header) {
  font-size: 0.8rem;
  height: 28px;
  line-height: 28px;
}
.tool-detail {
  font-size: 0.75rem;
  color: var(--text-muted);
}
.tool-section {
  margin-bottom: 6px;
}
.tool-section pre {
  margin: 4px 0;
  padding: 6px;
  background: #f0f2f5;
  border-radius: 4px;
  max-height: 120px;
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-all;
}
.tool-section code {
  background: #f0f2f5;
  padding: 2px 4px;
  border-radius: 3px;
}
/* Markdown 内容样式 */
.markdown-body :deep(table) {
  border-collapse: collapse;
  width: 100%;
  margin: 8px 0;
  font-size: 0.85rem;
}
.markdown-body :deep(th),
.markdown-body :deep(td) {
  border: 1px solid #d0d3d8;
  padding: 4px 8px;
  text-align: left;
}
.markdown-body :deep(th) {
  background: #e8eaef;
}
.markdown-body :deep(code) {
  background: rgba(0,0,0,0.06);
  padding: 1px 4px;
  border-radius: 3px;
  font-size: 0.88em;
}
.markdown-body :deep(pre) {
  background: rgba(0,0,0,0.06);
  padding: 8px;
  border-radius: 6px;
  overflow-x: auto;
}
.markdown-body :deep(pre code) {
  background: none;
  padding: 0;
}
.markdown-body :deep(ul),
.markdown-body :deep(ol) {
  padding-left: 20px;
  margin: 6px 0;
}
.markdown-body :deep(a) {
  color: var(--brand-start);
}
.input-area {
  border-top: 1px solid var(--border);
  padding: 10px 12px;
  background: var(--surface);
}
/* 绑定策略栏（输入区上方纤细一条） */
.bind-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}
.bind-label {
  font-size: 0.75rem;
  color: var(--text-muted);
  flex-shrink: 0;
}
.bind-select {
  flex: 1;
  max-width: 220px;
}
.bind-badge {
  flex-shrink: 0;
  max-width: 140px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.input-actions {
  display: flex;
  justify-content: flex-end;
  align-items: center;
  gap: 8px;
  margin-top: 6px;
}
</style>
