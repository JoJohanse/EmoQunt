<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { klineApi, sentimentApi, recommendApi } from '@/api'
import type { KlineData, SentimentData, DailyRecommendData, WatchTarget } from '@/api/types'
import { VChart } from '@/composables/useECharts'

// 预设可切换标的（A股大盘 + 美股龙头）
const targets = ref<WatchTarget[]>([
  { code: '000001', market: 'zh_a', name: '上证指数' },
  { code: '000300', market: 'zh_a', name: '沪深300' },
  { code: '399001', market: 'zh_a', name: '深证成指' },
  { code: 'AAPL', market: 'us', name: 'Apple' },
  { code: 'MSFT', market: 'us', name: 'Microsoft' },
  { code: 'TSLA', market: 'us', name: 'Tesla' },
])

const kline = ref<KlineData | null>(null)
const sentiment = ref<SentimentData | null>(null)
const recommend = ref<DailyRecommendData | null>(null)
const loadingKline = ref(false)

async function loadKline() {
  loadingKline.value = true
  try {
    kline.value = await klineApi.get(activeTarget.value.code, activeTarget.value.market, 180)
  } catch (e: any) {
    ElMessage.warning('K线数据加载失败：' + e.message)
    kline.value = null
  } finally {
    loadingKline.value = false
  }
}

async function loadAll() {
  // K线
  await loadKline()
  // 舆情
  sentimentApi.get().then((d) => (sentiment.value = d)).catch((e: any) => {
    // 舆情数据获取较慢或需联网，失败时静默降级
    console.warn('舆情数据加载失败', e.message)
  })
  // 推荐
  recommendApi.get().then((d) => (recommend.value = d)).catch((e: any) => {
    console.warn('推荐数据加载失败', e.message)
  })
}
onMounted(loadAll)

// 切换标的时重新加载K线（用 code+market 作为唯一键，避免对象引用比较问题）
const activeKey = ref('000001|zh_a')
const activeTarget = computed<WatchTarget>(
  () => targets.value.find((t) => `${t.code}|${t.market}` === activeKey.value) || targets.value[0],
)
watch(activeKey, () => loadKline())

// K线 ECharts 配置：蜡烛图 + 成交量
const klineOption = computed(() => {
  if (!kline.value || !kline.value.dates.length) return {}
  const k = kline.value
  return {
    title: {
      text: `${k.name || k.code} ${k.market === 'us' ? '(美股)' : '(A股)'}`,
      left: 'center',
      textStyle: { fontSize: 16, fontWeight: 600 },
    },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross' },
    },
    legend: { data: ['日K', '成交量'], top: 28, left: 'center' },
    grid: [
      { left: '6%', right: '3%', top: 60, height: '58%' },
      { left: '6%', right: '3%', top: '76%', height: '16%' },
    ],
    xAxis: [
      {
        type: 'category',
        data: k.dates,
        boundaryGap: true,
        axisLine: { onZero: false },
        splitLine: { show: false },
        min: 'dataMin',
        max: 'dataMax',
      },
      {
        type: 'category',
        gridIndex: 1,
        data: k.dates,
        boundaryGap: true,
        axisLabel: { show: false },
      },
    ],
    yAxis: [
      { scale: true, splitArea: { show: true } },
      { gridIndex: 1, splitNumber: 2, axisLabel: { show: false } },
    ],
    dataZoom: [
      { type: 'inside', xAxisIndex: [0, 1], start: 60, end: 100 },
      { type: 'slider', xAxisIndex: [0, 1], top: '94%', start: 60, end: 100 },
    ],
    series: [
      {
        name: '日K',
        type: 'candlestick',
        data: k.ohlcv,
        itemStyle: {
          color: '#ef232a',        // 阳线（A股红涨）
          color0: '#14b143',       // 阴线（A股绿跌）
          borderColor: '#ef232a',
          borderColor0: '#14b143',
        },
      },
      {
        name: '成交量',
        type: 'bar',
        xAxisIndex: 1,
        yAxisIndex: 1,
        data: k.volumes.map((v, i) => ({
          value: v,
          // 涨红跌绿，与K线一致
          itemStyle: { color: k.ohlcv[i] && k.ohlcv[i][1] >= k.ohlcv[i][0] ? '#ef232a' : '#14b143' },
        })),
      },
    ],
  }
})

function sectorColor(sentiment: number): string {
  if (sentiment >= 70) return '#28a745'
  if (sentiment <= 40) return '#dc3545'
  return '#6c757d'
}
function scoreColor(score: number): string {
  if (score >= 70) return '#28a745'
  if (score >= 60) return '#667eea'
  return '#f59e0b'
}
</script>

<template>
  <div class="dashboard">
    <!-- 顶部：K线图（主体） -->
    <el-card shadow="never" class="kline-card">
      <template #header>
        <div class="kline-header">
          <span class="section-title" style="margin: 0; border: none; padding: 0">
            <el-icon><CandlestickChart /></el-icon> 行情看板
          </span>
          <el-select
            v-model="activeKey"
            placeholder="选择标的"
            style="width: 200px"
          >
            <el-option
              v-for="t in targets"
              :key="t.code + t.market"
              :label="`${t.name} (${t.code})`"
              :value="`${t.code}|${t.market}`"
            />
          </el-select>
        </div>
      </template>
      <div v-loading="loadingKline" class="kline-body">
        <v-chart v-if="kline && kline.dates.length" class="kline-chart" :option="klineOption" autoresize />
        <el-empty v-else-if="!loadingKline" description="暂无K线数据" />
      </div>
    </el-card>

    <!-- 下部三栏：热门板块 / 热门舆情 / 个股推荐 -->
    <el-row :gutter="16" class="info-row">
      <!-- 热门板块 -->
      <el-col :xs="24" :md="8">
        <el-card shadow="never" class="info-card">
          <template #header>
            <span class="section-title" style="margin: 0; border: none; padding: 0">
              <el-icon><Sunrise /></el-icon> 热门板块 TOP
            </span>
          </template>
          <div class="info-body">
            <div
              v-for="s in (recommend?.top_sectors || sentiment?.sectors || []).slice(0, 6)"
              :key="s.name"
              class="sector-row"
            >
              <div class="sector-row-head">
                <span class="sector-name">{{ s.name }}</span>
                <span class="sector-score" :style="{ color: sectorColor(s.sentiment) }">{{ s.sentiment }}</span>
              </div>
              <el-progress
                :percentage="s.sentiment"
                :color="sectorColor(s.sentiment)"
                :stroke-width="6"
                :show-text="false"
              />
            </div>
            <el-empty v-if="!(recommend?.top_sectors?.length || sentiment?.sectors?.length)" :image-size="60" description="暂无板块数据" />
          </div>
        </el-card>
      </el-col>

      <!-- 热门舆情 -->
      <el-col :xs="24" :md="8">
        <el-card shadow="never" class="info-card">
          <template #header>
            <span class="section-title" style="margin: 0; border: none; padding: 0">
              <el-icon><ChatDotRound /></el-icon> 当日舆情
            </span>
          </template>
          <div class="info-body news-body">
            <div v-for="(n, i) in (sentiment?.news_list || []).slice(0, 6)" :key="i" class="news-item">
              <div class="news-source">
                <el-icon><Link /></el-icon> {{ n.source || '未知来源' }}
                <span v-if="n.date" class="news-date">{{ n.date }}</span>
              </div>
              <a v-if="n.url" :href="n.url" target="_blank" class="news-title">{{ n.title }}</a>
              <div v-else class="news-title">{{ n.title }}</div>
            </div>
            <el-empty v-if="!sentiment?.news_list?.length" :image-size="60" description="暂无舆情数据" />
          </div>
        </el-card>
      </el-col>

      <!-- 个股推荐 -->
      <el-col :xs="24" :md="8">
        <el-card shadow="never" class="info-card">
          <template #header>
            <span class="section-title" style="margin: 0; border: none; padding: 0">
              <el-icon><Star /></el-icon> 个股推荐
            </span>
          </template>
          <div class="info-body">
            <div v-for="r in (recommend?.recommendations || []).slice(0, 6)" :key="r.code" class="rec-item">
              <el-tag :type="r.rank <= 3 ? (r.rank === 1 ? 'warning' : r.rank === 2 ? 'info' : 'danger') : 'info'" effect="dark" round size="small">{{ r.rank }}</el-tag>
              <div class="rec-main">
                <div class="rec-head">
                  <span class="rec-name">{{ r.name }}</span>
                  <code class="rec-code">{{ r.code }}</code>
                  <span class="rec-score" :style="{ color: scoreColor(r.score) }">{{ r.score }}</span>
                </div>
                <small class="rec-reason">{{ r.reason }}</small>
              </div>
            </div>
            <el-empty v-if="!recommend?.recommendations?.length" :image-size="60" description="暂无推荐数据" />
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<style scoped>
.dashboard {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.kline-card {
  border-radius: var(--radius);
}
.kline-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.kline-body {
  min-height: 460px;
}
.kline-chart {
  height: 460px;
  width: 100%;
}
.info-row {
  margin-top: 0 !important;
}
.info-card {
  border-radius: var(--radius);
  height: 100%;
}
.info-body {
  min-height: 280px;
  max-height: 380px;
  overflow-y: auto;
}

/* 板块行 */
.sector-row {
  margin-bottom: 14px;
}
.sector-row-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}
.sector-name {
  font-weight: 600;
}
.sector-score {
  font-weight: 700;
  font-size: 1.1rem;
}

/* 舆情 */
.news-body {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.news-item {
  border-left: 3px solid var(--brand-start);
  padding-left: 10px;
}
.news-source {
  font-size: 0.78rem;
  color: var(--text-muted);
  margin-bottom: 3px;
  display: flex;
  align-items: center;
  gap: 4px;
}
.news-date {
  margin-left: auto;
}
.news-title {
  font-size: 0.92rem;
  color: var(--text);
  line-height: 1.4;
  font-weight: 500;
}

/* 推荐 */
.rec-item {
  display: flex;
  gap: 10px;
  margin-bottom: 12px;
  align-items: flex-start;
}
.rec-main {
  flex: 1;
  min-width: 0;
}
.rec-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 2px;
}
.rec-name {
  font-weight: 600;
}
.rec-code {
  font-size: 0.78rem;
  color: var(--text-muted);
}
.rec-score {
  margin-left: auto;
  font-weight: 700;
  font-size: 1.05rem;
}
.rec-reason {
  color: var(--text-muted);
  display: block;
  line-height: 1.4;
}
</style>
