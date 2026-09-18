<script setup lang="ts">
/**
 * StrategyLibraryView —— 策略库：代码策略卡片网格 + 新建。
 * 数据面：/api/v2/strategies（列表不含源码全文）。
 */
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { libraryApi } from '@/api'
import type { CodeStrategySummary, Market } from '@/api/types'
import { t } from '@/locales'

const router = useRouter()

const loading = ref(false)
const strategies = ref<CodeStrategySummary[]>([])
const marketFilter = ref<'' | Market>('')
const keyword = ref('')

const filtered = computed(() =>
  strategies.value.filter((s) => {
    if (marketFilter.value && s.market !== marketFilter.value) return false
    const kw = keyword.value.trim().toLowerCase()
    if (!kw) return true
    return (
      s.name.toLowerCase().includes(kw) ||
      (s.description || '').toLowerCase().includes(kw) ||
      (s.tags || '').toLowerCase().includes(kw)
    )
  }),
)

async function load() {
  loading.value = true
  try {
    const data = await libraryApi.list()
    strategies.value = data.strategies
  } catch (e) {
    ElMessage.error((e as Error).message || t('library.loadFailed'))
  } finally {
    loading.value = false
  }
}

// ---- 新建对话框 ----
const createVisible = ref(false)
const creating = ref(false)
const form = ref({ name: '', market: 'zh_a' as Market, description: '', example: 'dual_ma' })
const formRef = ref()

function openCreate() {
  form.value = { name: '', market: 'zh_a' as Market, description: '', example: 'dual_ma' }
  createVisible.value = true
}

function pct(v: number | undefined | null): string {
  if (v === undefined || v === null) return '-'
  return (v * 100).toFixed(2) + '%'
}

async function submitCreate() {
  await formRef.value?.validate?.()
  creating.value = true
  try {
    const source = buildExampleSource(form.value.example, form.value.market)
    const created = await libraryApi.create({
      name: form.value.name,
      description: form.value.description,
      market: form.value.market,
      source,
    })
    createVisible.value = false
    router.push(`/strategy-library/${created.id}`)
  } catch (e) {
    ElMessage.error((e as Error).message)
  } finally {
    creating.value = false
  }
}

async function removeOne(s: CodeStrategySummary) {
  try {
    await ElMessageBox.confirm(t('library.deleteConfirm', { name: s.name }), t('library.title'), {
      type: 'warning',
    })
  } catch {
    return
  }
  try {
    await libraryApi.remove(s.id)
    ElMessage.success(t('library.deleted'))
    await load()
  } catch (e) {
    ElMessage.error((e as Error).message)
  }
}

/** 示例源码与 locales 同步维护：此处文案是代码模板而非界面文案（注释会被保存为策略的一部分） */
function buildExampleSource(example: string, market: Market): string {
  const comments = market === 'us' ? '' : ''
  if (example === 'blank') {
    return `STRATEGY_PARAMS = {
    "trade_percent": 0.5,  # 每次开仓使用的资产比例
}


def initialize(context):
    pass


def handle_data(context, data):
    pass
`
  }
  return `${comments}STRATEGY_PARAMS = {
    "short_window": 5,     # 短期均线窗口
    "long_window": 20,     # 长期均线窗口
    "trade_percent": 0.9,  # 每次开仓使用的资产比例
}


def initialize(context):
    df = eq_data.get_price(start=context.run_info.start_date, end=context.run_info.end_date)
    closes = df["close"]
    context.short_ma = closes.rolling(context.params["short_window"]).mean()
    context.long_ma = closes.rolling(context.params["long_window"]).mean()
    context.dates = [d.strftime("%Y-%m-%d") for d in df.index]


def handle_data(context, data):
    today = str(context.trade_date)
    if today not in context.dates:
        return
    i = context.dates.index(today)
    if i < context.params["long_window"]:
        return
    if context.short_ma.iloc[i] > context.long_ma.iloc[i] and get_position() == 0:
        buy(percent=context.params["trade_percent"])
    elif context.short_ma.iloc[i] < context.long_ma.iloc[i] and get_position() > 0:
        close_all()
`
}

onMounted(load)
</script>

<template>
  <div class="library-page">
    <div class="page-head">
      <div>
        <h2 class="page-title">{{ t('library.title') }}</h2>
        <p class="page-subtitle">{{ t('library.subtitle') }}</p>
      </div>
      <el-button type="primary" @click="openCreate">{{ t('library.newStrategy') }}</el-button>
    </div>

    <div class="toolbar">
      <el-radio-group v-model="marketFilter">
        <el-radio-button value="">{{ t('library.marketAll') }}</el-radio-button>
        <el-radio-button value="zh_a">{{ t('common.market.zhA') }}</el-radio-button>
        <el-radio-button value="us">US</el-radio-button>
      </el-radio-group>
      <el-input
        v-model="keyword"
        class="search-input"
        :placeholder="t('library.searchPlaceholder')"
        clearable
        :prefix-icon="'Search'"
      />
    </div>

    <div v-loading="loading" class="cards">
      <el-empty v-if="!loading && filtered.length === 0" :description="t('library.empty')" class="empty" />
      <div class="card-grid">
        <el-card
          v-for="s in filtered"
          :key="s.id"
          class="strategy-card"
          shadow="hover"
          @click="router.push(`/strategy-library/${s.id}`)"
        >
          <div class="card-top">
            <span class="card-name">{{ s.name }}</span>
            <el-tag size="small" :type="s.market === 'us' ? 'warning' : 'danger'">
              {{ s.market === 'us' ? t('common.market.us') : t('common.market.zhA') }}
            </el-tag>
          </div>
          <p class="card-desc">{{ s.description || t('library.detail.noDescription') }}</p>
          <div v-if="s.last_run" class="card-run">
            <span>{{ t('library.detail.history.metricTotalReturn') }} {{ pct(s.last_run.metrics['总收益率']) }}</span>
            <span>· {{ t('library.detail.history.metricSharpe') }} {{ s.last_run.metrics['夏普比率'] ?? '-' }}</span>
          </div>
          <div class="card-foot">
            <span class="card-time">{{ s.updated_at }}</span>
            <el-button
              text
              size="small"
              type="danger"
              @click.stop="removeOne(s)"
            >
              <el-icon><Delete /></el-icon>
            </el-button>
          </div>
        </el-card>
      </div>
    </div>

    <el-dialog v-model="createVisible" :title="t('library.create.title')" width="520px">
      <el-form ref="formRef" :model="form" label-width="90px">
        <el-form-item :label="t('library.create.name')" required>
          <el-input v-model="form.name" :placeholder="t('library.create.namePlaceholder')" maxlength="50" />
        </el-form-item>
        <el-form-item :label="t('library.create.market')">
          <el-radio-group v-model="form.market">
            <el-radio-button value="zh_a">{{ t('common.market.zhA') }}</el-radio-button>
            <el-radio-button value="us">US</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item :label="t('library.create.description')">
          <el-input
            v-model="form.description"
            type="textarea"
            :rows="2"
            :placeholder="t('library.create.descriptionPlaceholder')"
          />
        </el-form-item>
        <el-form-item :label="t('library.create.startFromExample')">
          <el-radio-group v-model="form.example">
            <el-radio value="dual_ma">{{ t('library.create.exampleDualMa') }}</el-radio>
            <el-radio value="blank">{{ t('library.create.exampleBlank') }}</el-radio>
          </el-radio-group>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createVisible = false">{{ t('common.cancel') }}</el-button>
        <el-button type="primary" :loading="creating" @click="submitCreate">
          {{ t('library.create.submit') }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.library-page {
  padding: 4px 4px 24px;
}
.page-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 16px;
}
.page-title {
  margin: 0 0 4px;
  font-size: 22px;
}
.page-subtitle {
  margin: 0;
  color: var(--el-text-color-secondary);
  font-size: 13px;
}
.toolbar {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
}
.search-input {
  width: 280px;
}
.card-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 14px;
}
.strategy-card {
  cursor: pointer;
}
.card-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.card-name {
  font-weight: 600;
  font-size: 15px;
}
.card-desc {
  margin: 8px 0;
  color: var(--el-text-color-secondary);
  font-size: 13px;
  min-height: 34px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.card-run {
  font-size: 12px;
  color: var(--el-text-color-regular);
  margin-bottom: 8px;
}
.card-foot {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.card-time {
  font-size: 12px;
  color: var(--el-text-color-placeholder);
}
.empty {
  margin-top: 48px;
}
</style>
