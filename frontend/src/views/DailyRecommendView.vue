<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { recommendApi } from '@/api'
import type { DailyRecommendData, RecommendedStock } from '@/api/types'
import { recommendScoreColor } from '@/lib/marketColors'
import { t } from '@/locales'

const data = ref<DailyRecommendData | null>(null)
const loading = ref(false)

async function load(refresh = false) {
  loading.value = true
  try {
    data.value = refresh ? await recommendApi.refresh() : await recommendApi.get()
  } catch (e: any) {
    ElMessage.error(t('recommend.loadFailed', { msg: e.message }))
  } finally {
    loading.value = false
  }
}
onMounted(() => load())

function rankType(rank: number): string {
  if (rank === 1) return 'warning'
  if (rank === 2) return 'info'
  if (rank === 3) return 'danger'
  return 'info'
}
function scoreType(score: number): string {
  if (score >= 70) return 'success'
  if (score >= 60) return ''
  return 'warning'
}
</script>

<template>
  <div v-loading.fullscreen="loading" :element-loading-text="t('recommend.refreshing')">
    <div class="page-hero">
      <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px">
        <div>
          <h1><el-icon><Star /></el-icon> {{ t('layout.nav.recommend') }}</h1>
          <p class="subtitle" v-if="data">{{ t('recommend.subtitle', { date: data.date }) }}</p>
        </div>
        <el-button :loading="loading" @click="load(true)"><el-icon><Refresh /></el-icon> {{ t('recommend.refreshButton') }}</el-button>
      </div>
    </div>

    <div class="section-title" v-if="data?.top_sectors?.length"><el-icon><Sunrise /></el-icon> {{ t('recommend.topSectors') }}</div>
    <el-row :gutter="16" style="margin-bottom: 1.5rem">
      <el-col v-for="(s, i) in data?.top_sectors || []" :key="i" :xs="24" :md="8">
        <el-card shadow="hover" class="top-sector">
          <div class="ts-icon" :style="{ background: i === 0 ? 'linear-gradient(135deg,#f59e0b,#fbbf24)' : i === 1 ? 'linear-gradient(135deg,#0ea5e9,#38bdf8)' : 'linear-gradient(135deg,#28a745,#48c764)' }">
            <el-icon><OfficeBuilding /></el-icon>
          </div>
          <h4>{{ s.name }}</h4>
          <el-tag :type="s.sentiment >= 85 ? 'danger' : 'warning'">{{ t('recommend.heat', { score: s.sentiment }) }}</el-tag>
        </el-card>
      </el-col>
    </el-row>

    <div class="section-title"><el-icon><Rank /></el-icon> {{ t('recommend.list') }}</div>
    <el-table :data="data?.recommendations || []" stripe style="width: 100%">
      <el-table-column :label="t('recommend.colRank')" width="80">
        <template #default="{ row }">
          <el-tag :type="rankType(row.rank)" effect="dark" round>{{ row.rank }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="code" :label="t('recommend.colCode')" width="100">
        <template #default="{ row }"><code>{{ row.code }}</code></template>
      </el-table-column>
      <el-table-column prop="name" :label="t('recommend.colName')" width="120" />
      <el-table-column prop="sector" :label="t('recommend.colSector')" width="120">
        <template #default="{ row }"><el-tag size="small" type="info">{{ row.sector }}</el-tag></template>
      </el-table-column>
      <el-table-column :label="t('recommend.colScore')" width="180">
        <template #default="{ row }">
          <div style="display:flex;align-items:center;gap:8px">
            <el-progress :percentage="row.score" :color="recommendScoreColor(row.score)" :stroke-width="10" :show-text="false" style="flex:1" />
            <strong :style="{ color: recommendScoreColor(row.score) }">{{ row.score }}</strong>
          </div>
        </template>
      </el-table-column>
      <el-table-column prop="reason" :label="t('recommend.colReason')" />
    </el-table>
    <el-empty v-if="!loading && !data?.recommendations?.length" :description="t('recommend.empty')" />
  </div>
</template>

<style scoped>
.top-sector {
  text-align: center;
  border-radius: var(--radius);
}
.ts-icon {
  width: 48px;
  height: 48px;
  border-radius: 50%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: 1.2rem;
  margin-bottom: 8px;
}
.top-sector h4 {
  margin: 0 0 8px;
}
</style>
