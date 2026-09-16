<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { strategyApi } from '@/api'
import type { StrategyDetail } from '@/api/types'
import { t } from '@/locales'

const strategies = ref<StrategyDetail[]>([])
const loading = ref(false)

async function load() {
  loading.value = true
  try {
    strategies.value = await strategyApi.list()
  } catch (e: any) {
    ElMessage.error(t('strategies.loadFailed', { msg: e.message }))
  } finally {
    loading.value = false
  }
}
onMounted(load)

async function remove(name: string) {
  try {
    await ElMessageBox.confirm(
      t('strategies.deleteConfirm', { name }),
      t('common.confirm'),
      { type: 'warning' },
    )
    await strategyApi.remove(name)
    ElMessage.success(t('strategies.deleted'))
    await load()
  } catch (e: any) {
    if (e !== 'cancel') ElMessage.error(t('strategies.deleteFailed', { msg: e.message || e }))
  }
}
</script>

<template>
  <div>
    <div class="page-hero">
      <h1><el-icon><List /></el-icon> {{ t('layout.nav.strategies') }}</h1>
      <p class="subtitle">{{ t('strategies.subtitle') }}</p>
    </div>

    <el-row v-loading="loading" :gutter="16">
      <el-col v-for="s in strategies" :key="s.name" :xs="24" :lg="12">
        <el-card class="strat-card" shadow="hover">
          <template #header>
            <div class="strat-header">
              <span class="strat-name">
                {{ s.name }}
                <el-tag :type="s.is_user_strategy ? 'primary' : 'info'" size="small" effect="plain">
                  {{ s.is_user_strategy ? t('strategies.badgeCustom') : t('strategies.badgeSystem') }}
                </el-tag>
              </span>
              <el-button-group v-if="s.is_user_strategy">
                <el-button size="small" type="danger" plain @click="remove(s.name)">
                  <el-icon><Delete /></el-icon> {{ t('strategies.delete') }}
                </el-button>
              </el-button-group>
            </div>
          </template>
          <p class="strat-desc">{{ s.description || t('strategies.noDesc') }}</p>
          <el-table v-if="s.parameters && s.parameters.length" :data="s.parameters" size="small" border>
            <el-table-column prop="name" :label="t('strategies.colParamName')" width="160">
              <template #default="{ row }"><code>{{ row.name }}</code></template>
            </el-table-column>
            <el-table-column :label="t('strategies.colValue')">
              <template #default="{ row }">{{ row.value ?? row.default }}</template>
            </el-table-column>
            <el-table-column prop="type" :label="t('strategies.colType')" width="80">
              <template #default="{ row }">
                <el-tag size="small" type="info">{{ row.type }}</el-tag>
              </template>
            </el-table-column>
          </el-table>
          <div class="strat-footer">
            <router-link :to="`/backtest?strategy=${s.name}`">
              <el-button size="small" type="success"><el-icon><VideoPlay /></el-icon> {{ t('strategies.backtest') }}</el-button>
            </router-link>
          </div>
        </el-card>
      </el-col>
    </el-row>
    <el-empty v-if="!loading && !strategies.length" :description="t('strategies.empty')" />
  </div>
</template>

<style scoped>
.strat-card {
  border-radius: var(--radius);
  margin-bottom: 16px;
}
.strat-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.strat-name {
  font-weight: 700;
  display: flex;
  align-items: center;
  gap: 8px;
}
.strat-desc {
  color: var(--text-muted);
  margin: 0 0 12px;
}
.strat-footer {
  margin-top: 12px;
}
</style>
