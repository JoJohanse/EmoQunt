<script setup lang="ts">
/**
 * FactorLibraryView —— 因子库列表：Python 因子卡片 + 新建。
 * 契约：源码顶层 compute(df)->Series；市场本期限 zh_a（v2 方案 D5）。
 * 数据面：/api/v2/factors。
 */
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { factorLibApi } from '@/api'
import type { FactorSummary } from '@/api/types'
import { t } from '@/locales'

const router = useRouter()

const loading = ref(false)
const factors = ref<FactorSummary[]>([])
const keyword = ref('')

async function load() {
  loading.value = true
  try {
    const data = await factorLibApi.list()
    factors.value = data.factors
  } catch (e) {
    ElMessage.error((e as Error).message || t('factorlib.loadFailed'))
  } finally {
    loading.value = false
  }
}

function filtered(): FactorSummary[] {
  const kw = keyword.value.trim().toLowerCase()
  if (!kw) return factors.value
  return factors.value.filter(
    (f) => f.name.toLowerCase().includes(kw) || (f.description || '').toLowerCase().includes(kw)
      || (f.tags || '').toLowerCase().includes(kw),
  )
}

// ---- 新建对话框 ----
const EXAMPLE_MOMENTUM = `import pandas as pd

FACTOR_PARAMS = {"window": 20}  # 动量回看窗口（交易日）


def compute(df):
    """动量因子：过去 window 日收益率。"""
    window = int(FACTOR_PARAMS.get("window", 20))
    close = pd.to_numeric(df["收盘"], errors="coerce")
    return close.pct_change(window).dropna()
`

const EXAMPLE_BLANK = `import pandas as pd


def compute(df):
    """因子：输入单标的 OHLCV（中文列，日期索引），返回因子值 Series。"""
    close = pd.to_numeric(df["收盘"], errors="coerce")
    # TODO: 写你的因子逻辑
    return close.pct_change().dropna()
`

const createVisible = ref(false)
const creating = ref(false)
const form = ref({ name: '', description: '', example: 'momentum' })

function openCreate() {
  form.value = { name: '', description: '', example: 'momentum' }
  createVisible.value = true
}

async function submitCreate() {
  creating.value = true
  try {
    const source = form.value.example === 'momentum' ? EXAMPLE_MOMENTUM : EXAMPLE_BLANK
    const res = await factorLibApi.create({
      name: form.value.name,
      description: form.value.description,
      market: 'zh_a',
      source,
    })
    ElMessage.success(t('factorlib.create.submit'))
    createVisible.value = false
    await router.push(`/factor-library/${res.id}`)
  } catch (e) {
    ElMessage.error((e as Error).message)
  } finally {
    creating.value = false
  }
}

async function removeFactor(f: FactorSummary) {
  try {
    await ElMessageBox.confirm(t('factorlib.deleteConfirm', { name: f.name }), t('factorlib.title'), {
      type: 'warning',
    })
  } catch {
    return
  }
  try {
    await factorLibApi.remove(f.id)
    ElMessage.success(t('factorlib.deleted'))
    await load()
  } catch (e) {
    ElMessage.error((e as Error).message)
  }
}

onMounted(() => void load())
</script>

<template>
  <div v-loading="loading" class="factorlib-page">
    <div class="page-head">
      <div class="head-row">
        <div>
          <h2 class="page-title">{{ t('factorlib.title') }}</h2>
          <p class="page-subtitle">{{ t('factorlib.subtitle') }}</p>
        </div>
        <div class="head-actions">
          <el-input
            v-model="keyword"
            :placeholder="t('factorlib.searchPlaceholder')"
            clearable
            class="search-input"
          />
          <el-button type="primary" @click="openCreate">{{ t('factorlib.newFactor') }}</el-button>
        </div>
      </div>
    </div>

    <el-empty v-if="!loading && filtered().length === 0" :description="t('factorlib.empty')" />
    <el-row v-else :gutter="14">
      <el-col v-for="f in filtered()" :key="f.id" :xs="24" :sm="12" :md="8" :lg="6">
        <el-card shadow="hover" class="factor-card" @click="router.push(`/factor-library/${f.id}`)">
          <div class="card-title">
            <span class="card-name">{{ f.name }}</span>
            <el-tag size="small" type="danger">{{ t('factorlib.marketTag') }}</el-tag>
          </div>
          <p class="card-desc">{{ f.description || t('library.detail.noDescription') }}</p>
          <div class="card-foot">
            <span class="card-time">{{ f.updated_at }}</span>
            <el-button
              text
              size="small"
              type="danger"
              @click.stop="removeFactor(f)"
            >
              {{ t('factorlib.actions.delete') }}
            </el-button>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 新建对话框 -->
    <el-dialog v-model="createVisible" :title="t('factorlib.create.title')" width="560px">
      <el-form label-width="90px">
        <el-form-item :label="t('factorlib.create.name')" required>
          <el-input v-model="form.name" :placeholder="t('factorlib.create.namePlaceholder')" />
        </el-form-item>
        <el-form-item :label="t('factorlib.create.description')">
          <el-input v-model="form.description" type="textarea" :rows="2" :placeholder="t('factorlib.create.descriptionPlaceholder')" />
        </el-form-item>
        <el-form-item :label="t('factorlib.create.startFromExample')">
          <el-radio-group v-model="form.example">
            <el-radio value="momentum">{{ t('factorlib.create.exampleMomentum') }}</el-radio>
            <el-radio value="blank">{{ t('factorlib.create.exampleBlank') }}</el-radio>
          </el-radio-group>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createVisible = false">{{ t('common.cancel') }}</el-button>
        <el-button type="primary" :loading="creating" @click="submitCreate">{{ t('factorlib.create.submit') }}</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.factorlib-page {
  padding: 4px 4px 24px;
}
.head-row {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}
.page-title {
  margin: 6px 0 4px;
  font-size: 22px;
}
.page-subtitle {
  margin: 0;
  color: var(--el-text-color-secondary);
  font-size: 13px;
}
.head-actions {
  display: flex;
  gap: 10px;
}
.search-input {
  width: 240px;
}
.factor-card {
  margin-bottom: 14px;
  cursor: pointer;
}
.card-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
.card-name {
  font-weight: 600;
}
.card-desc {
  height: 40px;
  margin: 8px 0;
  overflow: hidden;
  color: var(--el-text-color-secondary);
  font-size: 13px;
}
.card-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.card-time {
  color: var(--el-text-color-secondary);
  font-size: 12px;
}
</style>
