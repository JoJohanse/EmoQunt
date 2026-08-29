<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { sentimentApi } from '@/api'
import type { SentimentData } from '@/api/types'
import { sectorColor } from '@/lib/marketColors'

const data = ref<SentimentData | null>(null)
const loading = ref(false)
const analyzeCode = ref('')

async function load(refresh = false) {
  loading.value = true
  try {
    data.value = refresh ? await sentimentApi.refresh() : await sentimentApi.get()
  } catch (e: any) {
    ElMessage.error('加载失败：' + e.message)
  } finally {
    loading.value = false
  }
}
onMounted(() => load())
</script>

<template>
  <div v-loading.fullscreen="loading" element-loading-text="正在刷新舆情数据，请稍候...">
    <div class="page-hero">
      <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px">
        <div>
          <h1><el-icon><ChatDotRound /></el-icon> 舆情分析</h1>
          <p class="subtitle" v-if="data">更新时间：{{ data.update_time }} · 热门新闻 {{ data.news_count }} 条</p>
        </div>
        <el-button :loading="loading" @click="load(true)"><el-icon><Refresh /></el-icon> 刷新</el-button>
      </div>
    </div>

    <el-row :gutter="20">
      <el-col :xs="24" :lg="12">
        <div class="section-title"><el-icon><Notification /></el-icon> 热门新闻</div>
        <el-card v-for="(n, i) in data?.news_list || []" :key="i" class="news-card" shadow="never">
          <div class="news-source"><el-icon><Link /></el-icon> {{ n.source || '未知来源' }}</div>
          <a v-if="n.url" :href="n.url" target="_blank" class="news-title">{{ n.title }}</a>
          <div v-else class="news-title">{{ n.title }}</div>
        </el-card>
        <el-empty v-if="data && !data.news_list.length" description="暂无热门新闻" />
      </el-col>

      <el-col :xs="24" :lg="12">
        <div class="section-title"><el-icon><PieChart /></el-icon> 板块得分排行</div>
        <el-card v-for="(s, i) in data?.sectors || []" :key="i" class="sector-card" shadow="never"
          :style="{ borderLeft: `4px solid ${sectorColor(s.sentiment)}` }">
          <div style="display:flex;justify-content:space-between;align-items:center">
            <span class="sector-name"><el-icon><OfficeBuilding /></el-icon> {{ s.name }}</span>
            <span class="sector-score" :style="{ color: sectorColor(s.sentiment) }">{{ s.sentiment }}</span>
          </div>
          <el-progress
            :percentage="s.sentiment"
            :color="sectorColor(s.sentiment)"
            :stroke-width="8"
            :show-text="false"
            style="margin: 8px 0"
          />
          <div class="stock-tags" v-if="s.stocks && s.stocks.length">
            <el-tag v-for="st in s.stocks.slice(0, 5)" :key="st.code" size="small" type="info" effect="plain">
              {{ st.code }} {{ st.name }}
            </el-tag>
          </div>
        </el-card>
        <el-empty v-if="data && !data.sectors.length" description="暂无板块数据" />
      </el-col>
    </el-row>
  </div>
</template>

<style scoped>
.news-card {
  border-left: 4px solid var(--brand-start);
  border-radius: 8px;
  margin-bottom: 10px;
}
.news-source {
  font-size: 0.8rem;
  color: var(--text-muted);
  margin-bottom: 4px;
}
.news-title {
  font-weight: 500;
  color: var(--text);
}
.sector-card {
  border-radius: 8px;
  margin-bottom: 10px;
}
.sector-name {
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 6px;
}
.sector-score {
  font-size: 1.6rem;
  font-weight: 800;
}
.stock-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
</style>
