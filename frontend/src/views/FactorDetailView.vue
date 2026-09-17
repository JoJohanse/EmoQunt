<script setup lang="ts">
/**
 * FactorDetailView —— 因子库详情：因子代码 / 因子分析 / 历史版本。
 * 分析 Tab 复用 FactorAnalysisPanel（与旧因子分析页同一展示组件），
 * 数据面：POST /api/v2/factors/{id}/analyze（同步执行，HS300 分钟级）。
 */
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { factorLibApi } from '@/api'
import type { FactorAnalysisResult, FactorDetail, FactorVersion } from '@/api/types'
import { t } from '@/locales'
import CodeEditor from '@/components/CodeEditor.vue'
import FactorAnalysisPanel from '@/components/FactorAnalysisPanel.vue'

const route = useRoute()
const router = useRouter()
const factorId = computed(() => Number(route.params.id))

const loading = ref(false)
const detail = ref<FactorDetail | null>(null)
const activeTab = ref('code')

// ---- 因子代码 Tab ----
const codeText = ref('')
const codeDirty = ref(false)
const validating = ref(false)
const validateErrors = ref<string[]>([])
let validateTimer: ReturnType<typeof setTimeout> | null = null

const codeStatus = computed(() => {
  if (validating.value) return { type: 'info' as const, label: t('factorlib.detail.code.validating') }
  if (validateErrors.value.length) return { type: 'danger' as const, label: t('factorlib.detail.code.validateFail') }
  return { type: 'success' as const, label: t('factorlib.detail.code.validateOk') }
})

function scheduleValidate() {
  if (validateTimer) clearTimeout(validateTimer)
  validateTimer = setTimeout(() => void runValidate(), 800)
}

async function runValidate() {
  validating.value = true
  try {
    const result = await factorLibApi.validate(codeText.value)
    validateErrors.value = result.errors
  } catch (e) {
    validateErrors.value = [(e as Error).message]
  } finally {
    validating.value = false
  }
}

async function saveCode() {
  validating.value = true
  try {
    const result = await factorLibApi.validate(codeText.value)
    validateErrors.value = result.errors
    if (!result.ok) {
      ElMessage.warning(t('factorlib.detail.code.fixErrorsFirst'))
      return
    }
    await factorLibApi.update(factorId.value, {
      source: codeText.value,
      note: t('factorlib.detail.code.save'),
    })
    codeDirty.value = false
    ElMessage.success(t('factorlib.detail.code.saved'))
    await loadDetail(false)
    await loadVersions()
  } catch (e) {
    ElMessage.error((e as Error).message)
  } finally {
    validating.value = false
  }
}

// ---- 因子分析 Tab ----
const analysisForm = ref({
  start_date: '2024-01-01',
  end_date: '2024-12-31',
  n_quantiles: 5,
  forward_period: 5,
})
const analyzing = ref(false)
const analysisResult = ref<FactorAnalysisResult | null>(null)

async function runAnalysis() {
  analyzing.value = true
  analysisResult.value = null
  try {
    const res = await factorLibApi.analyze(factorId.value, {
      start_date: analysisForm.value.start_date,
      end_date: analysisForm.value.end_date,
      n_quantiles: analysisForm.value.n_quantiles,
      forward_period: analysisForm.value.forward_period,
    })
    if (res.error) {
      ElMessage.error(res.error)
    } else {
      analysisResult.value = res
      ElMessage.success(t('factorlib.detail.analysis.done'))
    }
  } catch (e) {
    ElMessage.error((e as Error).message || t('factorlib.detail.analysis.failed'))
  } finally {
    analyzing.value = false
  }
}

// ---- 历史版本 Tab ----
const versions = ref<FactorVersion[]>([])
const versionDialog = ref(false)
const versionSource = ref('')

async function loadVersions() {
  try {
    const data = await factorLibApi.versions(factorId.value)
    versions.value = data.versions
  } catch {
    versions.value = []
  }
}

async function viewVersion(v: FactorVersion) {
  const full = await factorLibApi.versionSource(v.id)
  versionSource.value = full.source
  versionDialog.value = true
}

async function restoreVersion(v: FactorVersion) {
  try {
    await ElMessageBox.confirm(t('factorlib.detail.versions.restoreConfirm'), t('factorlib.title'), {
      type: 'warning',
    })
  } catch {
    return
  }
  try {
    await factorLibApi.restoreVersion(factorId.value, v.id)
    ElMessage.success(t('factorlib.detail.versions.restored'))
    await loadDetail(false)
    await loadVersions()
    codeText.value = detail.value?.source ?? ''
    codeDirty.value = false
  } catch (e) {
    ElMessage.error((e as Error).message)
  }
}

// ---- 装配 ----
async function loadDetail(withCode = true) {
  loading.value = true
  try {
    const d = await factorLibApi.detail(factorId.value)
    detail.value = d
    if (withCode) {
      codeText.value = d.source
      codeDirty.value = false
    }
  } catch (e) {
    ElMessage.error((e as Error).message || t('factorlib.loadFailed'))
  } finally {
    loading.value = false
  }
}

watch(codeText, (v) => {
  if (detail.value && v !== detail.value.source) {
    codeDirty.value = true
    scheduleValidate()
  }
})

watch(activeTab, (tab) => {
  if (tab === 'versions') void loadVersions()
})

onMounted(async () => {
  await loadDetail()
  void runValidate()
})

onBeforeUnmount(() => {
  if (validateTimer) clearTimeout(validateTimer)
})
</script>

<template>
  <div v-loading="loading" class="detail-page">
    <div class="page-head">
      <div class="head-left">
        <el-button text @click="router.push('/factor-library')">
          <el-icon><Back /></el-icon> {{ t('factorlib.detail.backToList') }}
        </el-button>
        <h2 v-if="detail" class="page-title">
          {{ detail.name }}
          <el-tag size="small" type="danger" class="market-tag">{{ t('factorlib.marketTag') }}</el-tag>
        </h2>
        <p v-if="detail" class="page-subtitle">
          {{ detail.description || t('factorlib.detail.noDescription') }} ·
          {{ t('factorlib.detail.updatedAt') }} {{ detail.updated_at }}
        </p>
      </div>
    </div>

    <el-tabs v-if="detail" v-model="activeTab">
      <!-- ===================== 因子代码 ===================== -->
      <el-tab-pane :label="t('factorlib.detail.tabs.code')" name="code">
        <div class="code-toolbar">
          <el-tag :type="codeStatus.type" size="small">{{ codeStatus.label }}</el-tag>
          <span v-if="codeDirty" class="dirty-hint">{{ t('factorlib.detail.code.unsaved') }}</span>
          <div class="toolbar-right">
            <el-button :loading="validating" @click="runValidate">{{ t('factorlib.detail.code.validate') }}</el-button>
            <el-button type="primary" :loading="validating" @click="saveCode">{{ t('factorlib.detail.code.save') }}</el-button>
          </div>
        </div>
        <CodeEditor v-model="codeText" height="480px" />
        <el-alert
          v-if="validateErrors.length"
          type="error"
          class="code-errors"
          :closable="false"
          :title="t('factorlib.detail.code.validateFail')"
        >
          <div v-for="(err, i) in validateErrors" :key="i" class="code-error-line">{{ err }}</div>
        </el-alert>
      </el-tab-pane>

      <!-- ===================== 因子分析 ===================== -->
      <el-tab-pane :label="t('factorlib.detail.tabs.analysis')" name="analysis" lazy>
        <el-card shadow="never" class="analysis-form" v-loading="analyzing">
          <div class="universe-line">
            <el-tag size="small" type="info">{{ t('factorlib.detail.analysis.universe') }}</el-tag>
            <span class="hint">{{ t('factorlib.detail.analysis.hint') }}</span>
          </div>
          <el-form label-width="90px">
          <el-row :gutter="16">
            <el-col :span="6">
              <el-form-item :label="t('factorlib.detail.analysis.startDate')">
                <el-date-picker v-model="analysisForm.start_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
              </el-form-item>
            </el-col>
            <el-col :span="6">
              <el-form-item :label="t('factorlib.detail.analysis.endDate')">
                <el-date-picker v-model="analysisForm.end_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
              </el-form-item>
            </el-col>
            <el-col :span="6">
              <el-form-item :label="t('factorlib.detail.analysis.quantiles')">
                <el-input-number v-model="analysisForm.n_quantiles" :min="2" :max="10" style="width: 100%" />
              </el-form-item>
            </el-col>
            <el-col :span="6">
              <el-form-item :label="t('factorlib.detail.analysis.forwardPeriod')">
                <el-input-number v-model="analysisForm.forward_period" :min="1" :max="20" style="width: 100%" />
              </el-form-item>
            </el-col>
          </el-row>
          </el-form>
          <el-button type="primary" :loading="analyzing" @click="runAnalysis">
            {{ analyzing ? t('factorlib.detail.analysis.running') : t('factorlib.detail.analysis.run') }}
          </el-button>
        </el-card>
        <FactorAnalysisPanel v-if="analysisResult" :result="analysisResult" class="analysis-panel" />
        <el-empty v-else :description="t('factorlib.detail.analysis.empty')" />
      </el-tab-pane>

      <!-- ===================== 历史版本 ===================== -->
      <el-tab-pane :label="t('factorlib.detail.tabs.versions')" name="versions">
        <el-empty v-if="versions.length === 0" :description="t('factorlib.detail.versions.empty')" />
        <el-table v-else :data="versions" size="small">
          <el-table-column prop="id" label="#" width="70" />
          <el-table-column prop="created_at" :label="t('factorlib.detail.versions.time')" width="180" />
          <el-table-column prop="note" :label="t('factorlib.detail.versions.note')" min-width="200" />
          <el-table-column width="180">
            <template #default="{ row }">
              <el-button text size="small" @click="viewVersion(row)">{{ t('factorlib.detail.versions.view') }}</el-button>
              <el-button text size="small" type="warning" @click="restoreVersion(row)">
                {{ t('factorlib.detail.versions.restore') }}
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>
    </el-tabs>

    <!-- 版本全文对话框 -->
    <el-dialog v-model="versionDialog" :title="t('factorlib.detail.tabs.versions')" width="780px">
      <CodeEditor v-model="versionSource" readonly height="420px" />
    </el-dialog>
  </div>
</template>

<style scoped>
.detail-page {
  padding: 4px 4px 24px;
}
.page-head {
  margin-bottom: 12px;
}
.page-title {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 6px 0 4px;
  font-size: 22px;
}
.market-tag {
  transform: translateY(-2px);
}
.page-subtitle {
  margin: 0;
  color: var(--el-text-color-secondary);
  font-size: 13px;
}
.code-toolbar {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
}
.dirty-hint {
  color: var(--el-color-warning);
  font-size: 12px;
}
.toolbar-right {
  margin-left: auto;
  display: flex;
  gap: 8px;
}
.code-errors {
  margin-top: 10px;
}
.code-error-line {
  font-family: monospace;
  font-size: 12px;
}
.analysis-form {
  margin-bottom: 6px;
}
.universe-line {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
}
.universe-line .hint {
  color: var(--el-text-color-secondary);
  font-size: 12px;
}
.analysis-panel {
  margin-top: 8px;
}
</style>
