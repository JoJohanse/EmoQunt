<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import type { Market, ToolCallEvent } from '@/api/types'
import { useWatchlistStore } from '@/stores/watchlist'
import { deltaTone, deltaDirection, scoreColor } from '@/lib/marketColors'
import { parseToolResult, TOOL_LABELS } from '@/components/chat/toolCards'

/**
 * AI 助手工具结果卡片（Generative UI 模式）：
 * 按工具名把 JSON 结果映射为结构化卡片，替代原始 <pre> 文本；
 * pending 渲染骨架，失败（取消/超时）渲染错误态。
 */
const props = defineProps<{ call: ToolCallEvent }>()

const router = useRouter()
const watchlistStore = useWatchlistStore()

const data = computed(() => parseToolResult(props.call))
const label = computed(() => TOOL_LABELS[props.call.name] ?? props.call.name)

// ===== 行情卡片（get_stock_quote / get_index_quote） =====
const quote = computed(() => {
  const d = data.value
  if (!d) return null
  const code = String(d.code ?? d.index ?? '')
  const market: 'zh_a' | 'us' = d.market === 'us' ? 'us' : 'zh_a'
  const kind = props.call.name === 'get_index_quote' ? ('index' as const) : undefined
  return {
    code,
    market,
    kind,
    name: String(d.name || code || '指数'),
    close: Number(d.close ?? 0),
    chgPct: Number(d.change_pct ?? 0),
    periodHigh: d.period_high != null ? Number(d.period_high) : null,
    periodLow: d.period_low != null ? Number(d.period_low) : null,
    lastDate: String(d.last_date ?? ''),
  }
})

/** A股红涨绿跌 / 美股绿涨红跌 的 Delta 徽章配色（方向→色调映射收拢在 lib/marketColors） */
function deltaStyle(market: Market, chgPct: number): Record<string, string> {
  const tone = deltaTone(market, deltaDirection(chgPct))
  if (tone === 'neutral') return { background: 'var(--neutral)', color: '#fff' }
  return tone === 'danger'
    ? { background: '#fef2f2', color: 'var(--danger)' }
    : { background: '#f0fdf4', color: 'var(--success)' }
}

/** 卡片内的"在首页打开主图"动作：协议收口在 watchlist.openChartOnHome，此处只补导航 */
function openInHome(code: string, market: 'zh_a' | 'us', name: string, kind?: 'index') {
  watchlistStore.openChartOnHome({ code, market, name, kind })
  router.push('/')
}

// ===== 舆情卡片（get_sentiment） =====
const sentiment = computed(() => {
  const d = data.value
  if (!d || !Array.isArray(d.top_sectors)) return null
  return {
    averageScore: d.average_score != null ? Number(d.average_score) : null,
    signal: String(d.signal ?? ''),
    newsCount: Number(d.news_count ?? 0),
    sectors: (d.top_sectors as any[]).slice(0, 5).map((s) => ({
      name: String(s.name ?? ''),
      score: Math.round(Number(s.sentiment ?? 0) * 100),
      stocks: (s.sample_stocks || []).map((st: any) => st.name).filter(Boolean),
    })),
  }
})

function signalTag(signal: string): { text: string; type: 'danger' | 'success' | 'info' } {
  // A股配色约定：买入=红、卖出=绿
  if (signal === 'buy') return { text: '买入信号', type: 'danger' }
  if (signal === 'sell') return { text: '卖出信号', type: 'success' }
  return { text: '观望', type: 'info' }
}

// 评分色（≥70 绿 / ≥60 紫 / ≥45 橙）收拢在 lib/marketColors，此处直接消费

// ===== 推荐卡片（get_daily_recommendations） =====
const recommends = computed(() => {
  const d = data.value
  if (!d || !Array.isArray(d.recommendations)) return null
  return (d.recommendations as any[]).slice(0, 5).map((r) => ({
    rank: Number(r.rank ?? 0),
    code: String(r.code ?? ''),
    name: String(r.name ?? r.code ?? ''),
    sector: String(r.sector ?? ''),
    score: Number(r.score ?? 0),
    reason: String(r.reason ?? ''),
  }))
})

// ===== 回测卡片（run_backtest） =====
const backtest = computed(() => {
  const d = data.value
  if (d == null || d.total_return_pct === undefined) return null
  const market: Market = d.market === 'us' ? 'us' : 'zh_a'
  const cell = (label: string, value: number, unit: string, positive: boolean | null) => ({
    label,
    value: `${value.toFixed(2)}${unit}`,
    // cls 的 up/down 为「红/绿」渲染类：A股涨=红(up)、美股涨=绿(down)，方向→色调映射走 lib/marketColors
    cls: positive === null ? '' : deltaTone(market, positive ? 'up' : 'down') === 'danger' ? 'up' : 'down',
  })
  return {
    strategy: String(d.strategy ?? ''),
    stock: String(d.stock ?? ''),
    cells: [
      cell('总收益率', Number(d.total_return_pct ?? 0), '%', d.total_return_pct > 0 ? true : d.total_return_pct < 0 ? false : null),
      cell('年化收益', Number(d.annual_return_pct ?? 0), '%', d.annual_return_pct > 0 ? true : d.annual_return_pct < 0 ? false : null),
      cell('最大回撤', Number(d.max_drawdown_pct ?? 0), '%', false),
      cell('夏普比率', Number(d.sharpe ?? 0), '', d.sharpe > 0 ? true : d.sharpe < 0 ? false : null),
      cell('胜率', Number(d.win_rate_pct ?? 0), '%', null),
      cell('盈亏比', Number(d.profit_loss_ratio ?? 0), '', d.profit_loss_ratio >= 1 ? true : d.profit_loss_ratio > 0 ? false : null),
    ],
  }
})

// ===== 个股信号卡片（get_stock_signal） =====
const signal = computed(() => {
  const d = data.value
  if (!d || d.code === undefined) return null
  return {
    code: String(d.code),
    sector: String(d.sector ?? ''),
    score: d.latest_sentiment != null ? Math.round(Number(d.latest_sentiment) * 100) : null,
    date: String(d.latest_date ?? ''),
    signal: String(d.signal ?? 'hold'),
  }
})
</script>

<template>
  <div class="tool-card">
    <div class="tool-card-head">
      <span class="tool-kind"><el-icon><Histogram /></el-icon> {{ label }}</span>
      <el-tag v-if="call.failed" type="danger" size="small" effect="plain">未完成</el-tag>
    </div>

    <!-- 执行中：骨架占位（tool_start → tool 状态机的 input-available 态） -->
    <div v-if="call.pending" class="tool-card-body">
      <el-skeleton animated :rows="2" />
    </div>

    <div v-else-if="call.failed" class="tool-card-body">
      <div class="tool-fail">该工具调用未返回结果（已取消或服务异常）</div>
    </div>

    <!-- 行情 / 指数 -->
    <div v-else-if="quote" class="tool-card-body">
      <div class="quote-row">
        <span class="quote-name">{{ quote.name }}</span>
        <code class="quote-code">{{ quote.code }}</code>
        <span class="quote-market">{{ quote.market === 'us' ? '美股' : 'A股' }}</span>
      </div>
      <div class="quote-row">
        <span class="quote-close">{{ quote.close.toFixed(2) }}</span>
        <span class="delta-badge" :style="deltaStyle(quote.market, quote.chgPct)">
          {{ quote.chgPct >= 0 ? '+' : '' }}{{ quote.chgPct.toFixed(2) }}%
        </span>
      </div>
      <div class="quote-meta">
        <span v-if="quote.periodHigh != null">期间最高 <strong>{{ quote.periodHigh.toFixed(2) }}</strong></span>
        <span v-if="quote.periodLow != null">期间最低 <strong>{{ quote.periodLow.toFixed(2) }}</strong></span>
        <span v-if="quote.lastDate">{{ quote.lastDate }}</span>
      </div>
      <el-button size="small" type="primary" plain class="tool-action" @click="openInHome(quote.code, quote.market, quote.name, quote.kind)">
        <el-icon><CandlestickChart /></el-icon> 在首页查看主图
      </el-button>
    </div>

    <!-- 舆情 -->
    <div v-else-if="sentiment" class="tool-card-body">
      <div class="quote-row">
        <span class="delta-badge" style="background: var(--brand-start); color: #fff">
          平均情绪 {{ sentiment.averageScore != null ? sentiment.averageScore.toFixed(2) : '—' }}
        </span>
        <el-tag :type="signalTag(sentiment.signal).type" size="small" effect="dark">
          {{ signalTag(sentiment.signal).text }}
        </el-tag>
        <span class="tool-muted">新闻 {{ sentiment.newsCount }} 条</span>
      </div>
      <div v-for="s in sentiment.sectors" :key="s.name" class="sentiment-row">
        <div class="sentiment-head">
          <span class="sentiment-name">{{ s.name }}</span>
          <span class="sentiment-score" :style="{ color: scoreColor(s.score) }">{{ s.score }}</span>
        </div>
        <el-progress :percentage="Math.min(100, s.score)" :color="scoreColor(s.score)" :stroke-width="5" :show-text="false" />
        <small v-if="s.stocks.length" class="tool-muted">{{ s.stocks.join(' / ') }}</small>
      </div>
      <el-button size="small" type="primary" plain class="tool-action" @click="router.push('/sentiment')">
        <el-icon><ChatDotRound /></el-icon> 查看舆情分析
      </el-button>
    </div>

    <!-- 每日推荐 -->
    <div v-else-if="recommends" class="tool-card-body">
      <div
        v-for="r in recommends"
        :key="r.code"
        class="rec-row"
        title="点击在首页主图查看"
        @click="openInHome(r.code, 'zh_a', r.name)"
      >
        <el-tag size="small" effect="dark" round>{{ r.rank }}</el-tag>
        <span class="rec-name">{{ r.name }}</span>
        <code class="quote-code">{{ r.code }}</code>
        <span class="rec-score" :style="{ color: scoreColor(r.score) }">{{ r.score }}</span>
      </div>
      <el-button size="small" type="primary" plain class="tool-action" @click="router.push('/daily-recommend')">
        <el-icon><Star /></el-icon> 查看每日推荐
      </el-button>
    </div>

    <!-- 回测摘要 -->
    <div v-else-if="backtest" class="tool-card-body">
      <div class="quote-row">
        <span class="quote-name">{{ backtest.strategy }}</span>
        <code class="quote-code">{{ backtest.stock }}</code>
      </div>
      <div class="bt-grid">
        <div v-for="c in backtest.cells" :key="c.label" class="bt-cell">
          <span class="bt-label">{{ c.label }}</span>
          <span class="bt-value" :class="c.cls">{{ c.value }}</span>
        </div>
      </div>
      <el-button size="small" type="primary" plain class="tool-action" @click="router.push('/backtest')">
        <el-icon><Histogram /></el-icon> 去运行回测
      </el-button>
    </div>

    <!-- 个股信号 -->
    <div v-else-if="signal" class="tool-card-body">
      <div class="quote-row">
        <span class="quote-name">{{ signal.sector || '个股信号' }}</span>
        <code class="quote-code">{{ signal.code }}</code>
        <el-tag :type="signalTag(signal.signal).type" size="small" effect="dark">
          {{ signalTag(signal.signal).text }}
        </el-tag>
      </div>
      <div class="quote-meta">
        <span v-if="signal.score != null">行业情绪 <strong :style="{ color: scoreColor(signal.score) }">{{ signal.score }}</strong></span>
        <span v-if="signal.date">{{ signal.date }}</span>
      </div>
      <el-button size="small" type="primary" plain class="tool-action" @click="openInHome(signal.code, 'zh_a', signal.code)">
        <el-icon><CandlestickChart /></el-icon> 在首页查看主图
      </el-button>
    </div>
  </div>
</template>

<style scoped>
.tool-card {
  border: 1px solid var(--border);
  border-radius: 10px;
  background: var(--surface);
  overflow: hidden;
  margin-bottom: 6px;
}
.tool-card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 10px;
  background: var(--bg);
  font-size: 0.75rem;
  color: var(--text-muted);
}
.tool-kind {
  display: flex;
  align-items: center;
  gap: 4px;
  font-weight: 600;
}
.tool-card-body {
  padding: 8px 10px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.tool-fail {
  color: var(--text-muted);
  font-size: 0.78rem;
}
.tool-muted {
  color: var(--text-muted);
  font-size: 0.72rem;
}
.tool-action {
  align-self: flex-start;
}
.quote-row {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.quote-name {
  font-weight: 600;
  font-size: 0.92rem;
}
.quote-code {
  font-size: 0.72rem;
  color: var(--text-muted);
}
.quote-market {
  font-size: 0.72rem;
  color: var(--text-muted);
  border: 1px solid var(--border);
  border-radius: 4px;
  padding: 0 4px;
}
.quote-close {
  font-size: 1.25rem;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}
.quote-meta {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  font-size: 0.75rem;
  color: var(--text-muted);
}
.delta-badge {
  font-size: 0.78rem;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  padding: 1px 8px;
  border-radius: 999px;
}
.sentiment-row {
  margin-bottom: 2px;
}
.sentiment-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.sentiment-name {
  font-size: 0.82rem;
  font-weight: 600;
}
.sentiment-score {
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}
.rec-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 3px 4px;
  border-radius: 6px;
  cursor: pointer;
}
.rec-row:hover {
  background: var(--bg);
}
.rec-name {
  font-weight: 600;
  font-size: 0.85rem;
}
.rec-score {
  margin-left: auto;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}
.bt-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 6px;
}
.bt-cell {
  background: var(--bg);
  border-radius: 6px;
  padding: 5px 6px;
  text-align: center;
}
.bt-label {
  display: block;
  font-size: 0.68rem;
  color: var(--text-muted);
}
.bt-value {
  font-weight: 700;
  font-size: 0.88rem;
  font-variant-numeric: tabular-nums;
}
.bt-value.up { color: var(--danger); }
.bt-value.down { color: var(--success); }
</style>
