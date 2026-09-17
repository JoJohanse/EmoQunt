<script setup lang="ts">
import { computed, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { factorApi } from '@/api'
import type { FactorAnalysisRequest, FactorAnalysisResult, FactorType } from '@/api/types'
import { t } from '@/locales'
import FactorAnalysisPanel from '@/components/FactorAnalysisPanel.vue'

const loading = ref(false)
const result = ref<FactorAnalysisResult | null>(null)

const form = ref<FactorAnalysisRequest>({
  factor_type: 'momentum',
  start_date: '2024-01-01',
  end_date: '2024-12-31',
  universe: 'hs300',
  n_quantiles: 5,
  forward_period: 5,
})

// 因子下拉项（computed 内读 t()，切换语言即重算）
const factorOptions = computed<{ label: string; value: FactorType; desc: string }[]>(() => [
  { label: t('factor.type.momentum'), value: 'momentum', desc: t('factor.type.momentumDesc') },
  { label: t('factor.type.rsi'), value: 'rsi', desc: t('factor.type.rsiDesc') },
  { label: t('factor.type.volatility'), value: 'volatility', desc: t('factor.type.volatilityDesc') },
  { label: t('factor.type.volumeRatio'), value: 'volume_ratio', desc: t('factor.type.volumeRatioDesc') },
])

async function runAnalysis() {
  loading.value = true
  result.value = null
  try {
    result.value = await factorApi.analyze(form.value)
    if (result.value.error) {
      ElMessage.error(result.value.error)
      result.value = null
    } else {
      ElMessage.success(t('factor.done'))
    }
  } catch (e: any) {
    ElMessage.error(t('factor.failed') + e.message)
  } finally {
    loading.value = false
  }
}

</script>

<template>
  <div class="page">
    <div class="page-hero">
      <h1><el-icon><DataAnalysis /></el-icon> {{ t('factor.title') }}</h1>
      <p class="subtitle">{{ t('factor.subtitle') }}</p>
    </div>

    <el-card shadow="never" class="form-card" v-loading="loading">
      <el-form :model="form" label-width="100px" label-position="right">
        <el-form-item :label="t('factor.form.factorType')">
          <el-select v-model="form.factor_type" style="width: 100%">
            <el-option
              v-for="f in factorOptions"
              :key="f.value"
              :label="f.label"
              :value="f.value"
            />
          </el-select>
        </el-form-item>
        <el-row :gutter="20">
          <el-col :xs="12" :md="6">
            <el-form-item :label="t('factor.form.startDate')">
              <el-input v-model="form.start_date" placeholder="2024-01-01" />
            </el-form-item>
          </el-col>
          <el-col :xs="12" :md="6">
            <el-form-item :label="t('factor.form.endDate')">
              <el-input v-model="form.end_date" placeholder="2024-12-31" />
            </el-form-item>
          </el-col>
          <el-col :xs="12" :md="6">
            <el-form-item :label="t('factor.form.quantiles')">
              <el-input-number v-model="form.n_quantiles" :min="2" :max="10" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :xs="12" :md="6">
            <el-form-item :label="t('factor.form.forwardPeriod')">
              <el-input-number v-model="form.forward_period" :min="1" :max="20" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item>
          <el-button type="primary" :loading="loading" @click="runAnalysis">
            <el-icon><DataAnalysis /></el-icon> {{ t('factor.run') }}
          </el-button>
          <span class="hint">{{ t('factor.form.hint') }}</span>
        </el-form-item>
      </el-form>
    </el-card>

    <FactorAnalysisPanel v-if="result" :result="result" />
    <el-empty v-else-if="!loading" :description="t('factor.empty')" />
  </div>
</template>

<style scoped>
.page {
  max-width: 1200px;
  margin: 0 auto;
}
.form-card {
  border-radius: var(--radius);
  margin-bottom: 1.25rem;
}
.hint {
  color: var(--text-muted);
  margin-left: 12px;
  font-size: 0.85rem;
}
</style>
