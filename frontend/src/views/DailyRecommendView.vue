<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { recommendApi } from '@/api'
import type { DailyRecommendData, RecommendedStock } from '@/api/types'
import { recommendScoreColor } from '@/lib/marketColors'

const data = ref<DailyRecommendData | null>(null)
const loading = ref(false)

async function load(refresh = false) {
  loading.value = true
  try {
    data.value = refresh ? await recommendApi.refresh() : await recommendApi.get()
  } catch (e: any) {
    ElMessage.error('加载失败：' + e.message)
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
  <div v-loading.fullscreen="loading" element-loading-text="正在刷新推荐，请稍候...">
    <div class="page-hero">
      <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px">
        <div>
          <h1><el-icon><Star /></el-icon> 每日推荐</h1>
          <p class="subtitle" v-if="data">推荐日期：{{ data.date }}</p>
        </div>
        <el-button :loading="loading" @click="load(true)"><el-icon><Refresh /></el-icon> 刷新推荐</el-button>
      </div>
    </div>

    <div class="section-title" v-if="data?.top_sectors?.length"><el-icon><Sunrise /></el-icon> 热门板块 TOP 3</div>
    <el-row :gutter="16" style="margin-bottom: 1.5rem">
      <el-col v-for="(s, i) in data?.top_sectors || []" :key="i" :xs="24" :md="8">
        <el-card shadow="hover" class="top-sector">
          <div class="ts-icon" :style="{ background: i === 0 ? 'linear-gradient(135deg,#f59e0b,#fbbf24)' : i === 1 ? 'linear-gradient(135deg,#0ea5e9,#38bdf8)' : 'linear-gradient(135deg,#28a745,#48c764)' }">
            <el-icon><OfficeBuilding /></el-icon>
          </div>
          <h4>{{ s.name }}</h4>
          <el-tag :type="s.sentiment >= 85 ? 'danger' : 'warning'">热度：{{ s.sentiment }}</el-tag>
        </el-card>
      </el-col>
    </el-row>

    <div class="section-title"><el-icon><Rank /></el-icon> 推荐股票列表</div>
    <el-table :data="data?.recommendations || []" stripe style="width: 100%">
      <el-table-column label="排名" width="80">
        <template #default="{ row }">
          <el-tag :type="rankType(row.rank)" effect="dark" round>{{ row.rank }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="code" label="代码" width="100">
        <template #default="{ row }"><code>{{ row.code }}</code></template>
      </el-table-column>
      <el-table-column prop="name" label="名称" width="120" />
      <el-table-column prop="sector" label="板块" width="120">
        <template #default="{ row }"><el-tag size="small" type="info">{{ row.sector }}</el-tag></template>
      </el-table-column>
      <el-table-column label="综合评分" width="180">
        <template #default="{ row }">
          <div style="display:flex;align-items:center;gap:8px">
            <el-progress :percentage="row.score" :color="recommendScoreColor(row.score)" :stroke-width="10" :show-text="false" style="flex:1" />
            <strong :style="{ color: recommendScoreColor(row.score) }">{{ row.score }}</strong>
          </div>
        </template>
      </el-table-column>
      <el-table-column prop="reason" label="推荐理由" />
    </el-table>
    <el-empty v-if="!loading && !data?.recommendations?.length" description="暂无推荐" />
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
