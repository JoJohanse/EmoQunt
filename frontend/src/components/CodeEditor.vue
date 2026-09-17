<script setup lang="ts">
/**
 * CodeEditor —— Python 代码编辑器（CodeMirror 6 懒加载）。
 *
 * CodeMirror 相关包约 300KB，仅在本组件挂载时动态 import，随路由 chunk
 * 拆分（策略库/详情页独有，不进首屏包）。v-model 双向绑定源码文本。
 */
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'

const props = withDefaults(
  defineProps<{
    modelValue: string
    readonly?: boolean
    height?: string
  }>(),
  { readonly: false, height: '420px' },
)

const emit = defineEmits<{ (e: 'update:modelValue', v: string): void }>()

const host = ref<HTMLDivElement | null>(null)

type EditorViewLike = {
  destroy: () => void
  update: (spec: { changes: { from: number; to: number; insert: string } }) => void
}

let view: EditorViewLike | null = null
let applyingExternal = false

onMounted(async () => {
  if (!host.value) return
  // 动态引入：CodeMirror 6 全家桶进入本组件的异步 chunk
  const [{ EditorView, basicSetup }, { python }, { oneDark }] = await Promise.all([
    import('codemirror'),
    import('@codemirror/lang-python'),
    import('@codemirror/theme-one-dark'),
  ])
  const created = new EditorView({
    doc: props.modelValue,
    extensions: [
      basicSetup,
      python(),
      oneDark,
      EditorView.editable.of(!props.readonly),
      EditorView.updateListener.of((u: { docChanged: boolean; state: { doc: { toString: () => string } } }) => {
        if (u.docChanged && !applyingExternal) {
          emit('update:modelValue', u.state.doc.toString())
        }
      }),
    ],
    parent: host.value,
  })
  view = created as unknown as EditorViewLike
})

// 外部值变化（如载入版本快照）时整体替换文档
watch(
  () => props.modelValue,
  (next) => {
    if (!view) return
    const current = (view as unknown as { state: { doc: { toString: () => string } } }).state.doc.toString()
    if (current === next) return
    applyingExternal = true
    view.update({ changes: { from: 0, to: current.length, insert: next } })
    applyingExternal = false
  },
)

onBeforeUnmount(() => {
  view?.destroy()
  view = null
})
</script>

<template>
  <div ref="host" class="code-editor" :style="{ height: props.height }"></div>
</template>

<style scoped>
.code-editor {
  width: 100%;
  border-radius: 8px;
  overflow: hidden;
  border: 1px solid var(--el-border-color-light);
}
.code-editor :deep(.cm-editor) {
  height: 100%;
  font-size: 13px;
}
.code-editor :deep(.cm-scroller) {
  overflow: auto;
}
</style>
