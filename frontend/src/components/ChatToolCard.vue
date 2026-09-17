<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import type { Market, ToolCallEvent } from '@/api/types'
import { useWatchlistStore } from '@/stores/watchlist'
import { deltaTone, deltaDirection, scoreColor } from '@/lib/marketColors'
import { parseToolResult, toolCardKind, TOOL_LABELS } from '@/components/chat/toolCards'
import CodeEditor from '@/components/CodeEditor.vue'
import { t } from '@/locales'

/**
 * AI 助手工具结果卡片（Generative UI 模式）：
 * 按工具名把 JSON 结果映射为结构化卡片，替代原始 <pre> 文本；
 * pending 渲染骨架，失败（取消/超时）渲染错误态。
 */
const props = defineProps<{ call: ToolCallEvent }>()

const router = useRouter()
const watchlistStore = useWatchlistStore()

const data = computed(() => parseToolResult(props.call))
// 卡片分发主键 = 工具名（toolCards.KIND_BY_TOOL；父组件只对登记过的工具渲染本卡片）。
// 历史教训：此前按 computed 真值分发，quote 对任何 JSON 对象都为真且排第一，
// 后续所有卡片（含 P4 五张新卡）全部不可达——分发必须看工具名，形状只做护栏。
const kind = computed(() => toolCardKind(props.call))
// 卡片标题：登记过的工具经 i18n 翻译，未知工具回退原始工具名（数据）
const label = computed(() => {
  const key = TOOL_LABELS[props.call.name]
  return key ? t(key) : props.call.name
})

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
    name: String(d.name || code || t('chat.indexName')),
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
  // A股配色约定：买入=红、卖出=绿；文案在渲染时取（语言切换即时生效）
  if (signal === 'buy') return { text: t('chat.signalBuy'), type: 'danger' }
  if (signal === 'sell') return { text: t('chat.signalSell'), type: 'success' }
  return { text: t('chat.signalHold'), type: 'info' }
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
      cell(t('chat.btTotalReturn'), Number(d.total_return_pct ?? 0), '%', d.total_return_pct > 0 ? true : d.total_return_pct < 0 ? false : null),
      cell(t('chat.btAnnualReturn'), Number(d.annual_return_pct ?? 0), '%', d.annual_return_pct > 0 ? true : d.annual_return_pct < 0 ? false : null),
      cell(t('chat.btMaxDrawdown'), Number(d.max_drawdown_pct ?? 0), '%', false),
      cell(t('chat.btSharpe'), Number(d.sharpe ?? 0), '', d.sharpe > 0 ? true : d.sharpe < 0 ? false : null),
      cell(t('chat.btWinRate'), Number(d.win_rate_pct ?? 0), '%', null),
      cell(t('chat.btProfitLossRatio'), Number(d.profit_loss_ratio ?? 0), '', d.profit_loss_ratio >= 1 ? true : d.profit_loss_ratio > 0 ? false : null),
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

// ===== 共用展示助手（与 RunHistoryView 的口径一致） =====
/** 异步任务状态 → tag 文案与类型（common.status.* 五态） */
function statusTag(status: string): { text: string; type: 'info' | 'primary' | 'success' | 'danger' | 'warning' } {
  if (status === 'running') return { text: t('common.status.running'), type: 'primary' }
  if (status === 'succeeded') return { text: t('common.status.succeeded'), type: 'success' }
  if (status === 'failed') return { text: t('common.status.failed'), type: 'danger' }
  if (status === 'cancelled') return { text: t('common.status.cancelled'), type: 'warning' }
  return { text: t('common.status.queued'), type: 'info' }
}
/** 后端中文指标键 → 展示名（backtest.metric.* 词表；未登记的键回退原始中文键，它是 API 契约） */
function metricLabel(key: string): string {
  const label = t(`backtest.metric.${key}`)
  return label.startsWith('backtest.metric.') ? key : label
}
function toNum(v: unknown): number | null {
  const n = Number(v)
  return Number.isFinite(n) ? n : null
}
/** 参数对象 → "k=v" chip 列表 */
function paramChips(params: unknown): { k: string; v: string }[] {
  if (!params || typeof params !== 'object') return []
  return Object.entries(params as Record<string, unknown>).map(([k, v]) => ({ k, v: String(v) }))
}
/** 从 call.args 解析短字段（args 截断到 500 字符，只可靠包含 factor_id 这类前置短键） */
function argField(name: string): unknown {
  try {
    return JSON.parse(props.call.args ?? '{}')?.[name]
  } catch {
    return undefined
  }
}

// ===== 策略代码卡片（get_strategy / create_strategy / update_strategy） =====
const strategyCode = computed(() => {
  const d = data.value
  if (!d || d.id === undefined) return null
  return {
    id: Number(d.id),
    name: String(d.name ?? ''),
    market: d.market === 'us' ? ('us' as const) : ('zh_a' as const),
    description: String(d.description ?? ''),
    params: paramChips(d.params),
    // get_strategy 返回源码全文；create/update 只回 {id, name?, params?} / {id, updated}
    source: typeof d.source === 'string' && d.source ? d.source : '',
    updated: d.updated === true,
  }
})

// ===== 调优任务创建卡片（create_tuning_task） =====
const tuningTask = computed(() => {
  const d = data.value
  if (!d || d.id === undefined || d.total_combos === undefined) return null
  return {
    id: Number(d.id),
    status: String(d.status ?? 'queued'),
    total: Number(d.total_combos ?? 0),
    // note 是后端发射的数据文案（已按请求语言本地化），原样展示
    note: String(d.note ?? ''),
  }
})

// ===== 调优进度卡片（get_tuning_status） =====
const tuningStatus = computed(() => {
  const d = data.value
  if (!d || d.id === undefined || d.total_combos === undefined) return null
  const target = String(d.target_metric ?? '总收益率')
  // 目标方向与后端 TARGET_METRICS 一致：最大回撤越小越好，其余越大越好
  const desc = target !== '最大回撤'
  // 指标值格式化口径与 RunHistoryView.fmtMetric 一致：夏普原值两位小数，其余为小数→百分比
  const fmtMetric = (key: string, v: unknown): string => {
    const n = toNum(v)
    return n === null ? '—' : key === '夏普比率' ? n.toFixed(2) : `${(n * 100).toFixed(2)}%`
  }
  const combos = (Array.isArray(d.combos) ? d.combos : [])
    .filter((c: any) => c?.status === 'succeeded' && toNum(c[target]) !== null)
    .sort((a: any, b: any) => (desc ? toNum(b[target])! - toNum(a[target])! : toNum(a[target])! - toNum(b[target])!))
    .slice(0, 3)
    .map((c: any) => ({
      idx: Number(c.combo_index ?? 0),
      baseline: c.is_baseline === true || c.is_baseline === 1,
      params: paramChips(c.params).map((p) => `${p.k}=${p.v}`).join('  '),
      target: fmtMetric(target, c[target]),
      sharpe: fmtMetric('夏普比率', c['夏普比率']),
      drawdown: fmtMetric('最大回撤', c['最大回撤']),
    }))
  const best = d.best_combo
    ? {
        idx: Number(d.best_combo.combo_index ?? 0),
        params: paramChips(d.best_combo.params),
        value: fmtMetric(target, d.best_combo[target]),
      }
    : null
  return {
    id: Number(d.id),
    status: String(d.status ?? ''),
    done: Number(d.done_combos ?? 0),
    total: Number(d.total_combos ?? 0),
    targetLabel: metricLabel(target),
    best,
    combos,
  }
})

// ===== 运行记录卡片（get_run） =====
const runRecord = computed(() => {
  const d = data.value
  if (!d || d.id === undefined || d.metrics === undefined || d.metrics === null) return null
  const m = d.metrics as Record<string, unknown>
  const market: Market = d.market === 'us' ? 'us' : 'zh_a'
  // 与既有回测卡同款 cell：正负号 → A股红涨绿跌/美股绿涨红跌 的渲染类
  const cell = (key: string, value: number | null, unit: string, positive: boolean | null) => ({
    label: metricLabel(key),
    value: value === null ? '—' : `${value.toFixed(2)}${unit}`,
    cls: positive === null ? '' : deltaTone(market, positive ? 'up' : 'down') === 'danger' ? 'up' : 'down',
  })
  const sign = (n: number | null) => (n === null || n === 0 ? null : n > 0)
  // metrics 是 _format_metrics_json 契约：比率类为小数（0.12 → 12%），夏普/盈亏比为原值
  const pctCell = (key: string, positive: boolean | null) => cell(key, toNum(m[key]), '%', positive)
  const ret = toNum(m['总收益率'])
  const annual = toNum(m['年化收益率'])
  const sharpe = toNum(m['夏普比率'])
  const plr = toNum(m['盈亏比'])
  return {
    id: Number(d.id),
    status: String(d.status ?? ''),
    strategy: String(d.strategy_name ?? ''),
    stock: String(d.stock_code ?? ''),
    market,
    dateRange: [d.start_date, d.end_date].filter(Boolean).join(' ~ '),
    tradeCount: toNum(d.trade_count),
    cells: [
      pctCell('总收益率', sign(ret)),
      pctCell('年化收益率', sign(annual)),
      cell('夏普比率', sharpe, '', sign(sharpe)),
      // 回撤恒为负向指标（绿），与既有回测卡口径一致
      cell('最大回撤', toNum(m['最大回撤']), '%', false),
      pctCell('胜率', null),
      cell('盈亏比', plr, '', plr === null ? null : plr >= 1 ? true : plr > 0 ? false : null),
    ],
  }
})

// ===== 因子分析卡片（analyze_factor；IC 标签/分层表头复用 factor.* 词表） =====
const factorAnalysis = computed(() => {
  const d = data.value
  if (!d || d.ic_stats === undefined) return null
  const s = d.ic_stats as Record<string, unknown>
  const fmt = (v: unknown, nd = 4): string => {
    const n = toNum(v)
    return n === null ? '—' : n.toFixed(nd)
  }
  const fmtPct = (v: unknown): string => {
    const n = toNum(v)
    return n === null ? '—' : `${(n * 100).toFixed(2)}%`
  }
  const cards = [
    { label: t('factor.cards.icMean'), value: fmt(s.ic_mean) },
    { label: t('factor.cards.rankIcMean'), value: fmt(s.rank_ic_mean) },
    { label: t('factor.cards.icir'), value: fmt(s.ic_ir) },
    { label: t('factor.cards.rankIcir'), value: fmt(s.rank_ic_ir) },
    { label: t('factor.cards.icWinRate'), value: fmt(s.ic_win_rate) },
    { label: t('factor.cards.icPositiveRate'), value: fmt(s.ic_positive_rate) },
  ]
  const quantiles = (Array.isArray(d.quantile_stats) ? d.quantile_stats : []).map((q: any) => ({
    quantile: String(q?.quantile ?? ''),
    meanReturn: fmtPct(q?.mean_return),
    sharpe: fmt(q?.sharpe_ratio, 2),
    winRate: fmtPct(q?.win_rate),
  }))
  // 因子 id 只能从 call.args 取（结果体里没有）
  const factorId = toNum(argField('factor_id'))
  const mono = (d.monotonicity ?? {}) as Record<string, unknown>
  return {
    name: String(d.factor ?? ''),
    cards,
    universe: toNum(d.universe_size),
    monotonic: mono.monotonic === true,
    ratio: toNum(mono.monotonicity_ratio),
    quantiles,
    factorId,
  }
})
</script>

<template>
  <div class="tool-card">
    <div class="tool-card-head">
      <span class="tool-kind"><el-icon><Histogram /></el-icon> {{ label }}</span>
      <el-tag v-if="call.failed" type="danger" size="small" effect="plain">{{ t('chat.incomplete') }}</el-tag>
    </div>

    <!-- 执行中：骨架占位（tool_start → tool 状态机的 input-available 态） -->
    <div v-if="call.pending" class="tool-card-body">
      <el-skeleton animated :rows="2" />
    </div>

    <div v-else-if="call.failed" class="tool-card-body">
      <div class="tool-fail">{{ t('chat.toolNoResult') }}</div>
    </div>

    <!-- 行情 / 指数 -->
    <div v-else-if="kind === 'quote' && quote" class="tool-card-body">
      <div class="quote-row">
        <span class="quote-name">{{ quote.name }}</span>
        <code class="quote-code">{{ quote.code }}</code>
        <span class="quote-market">{{ quote.market === 'us' ? t('chat.marketUs') : t('chat.marketCn') }}</span>
      </div>
      <div class="quote-row">
        <span class="quote-close">{{ quote.close.toFixed(2) }}</span>
        <span class="delta-badge" :style="deltaStyle(quote.market, quote.chgPct)">
          {{ quote.chgPct >= 0 ? '+' : '' }}{{ quote.chgPct.toFixed(2) }}%
        </span>
      </div>
      <div class="quote-meta">
        <span v-if="quote.periodHigh != null">{{ t('chat.periodHigh') }} <strong>{{ quote.periodHigh.toFixed(2) }}</strong></span>
        <span v-if="quote.periodLow != null">{{ t('chat.periodLow') }} <strong>{{ quote.periodLow.toFixed(2) }}</strong></span>
        <span v-if="quote.lastDate">{{ quote.lastDate }}</span>
      </div>
      <el-button size="small" type="primary" plain class="tool-action" @click="openInHome(quote.code, quote.market, quote.name, quote.kind)">
        <el-icon><CandlestickChart /></el-icon> {{ t('chat.viewOnHome') }}
      </el-button>
    </div>

    <!-- 舆情 -->
    <div v-else-if="kind === 'sentiment' && sentiment" class="tool-card-body">
      <div class="quote-row">
        <span class="delta-badge" style="background: var(--brand-start); color: #fff">
          {{ t('chat.avgSentiment') }} {{ sentiment.averageScore != null ? sentiment.averageScore.toFixed(2) : '—' }}
        </span>
        <el-tag :type="signalTag(sentiment.signal).type" size="small" effect="dark">
          {{ signalTag(sentiment.signal).text }}
        </el-tag>
        <span class="tool-muted">{{ t('chat.newsCount', { n: sentiment.newsCount }) }}</span>
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
        <el-icon><ChatDotRound /></el-icon> {{ t('chat.viewSentiment') }}
      </el-button>
    </div>

    <!-- 每日推荐 -->
    <div v-else-if="kind === 'recommend' && recommends" class="tool-card-body">
      <div
        v-for="r in recommends"
        :key="r.code"
        class="rec-row"
        :title="t('chat.clickToViewOnHome')"
        @click="openInHome(r.code, 'zh_a', r.name)"
      >
        <el-tag size="small" effect="dark" round>{{ r.rank }}</el-tag>
        <span class="rec-name">{{ r.name }}</span>
        <code class="quote-code">{{ r.code }}</code>
        <span class="rec-score" :style="{ color: scoreColor(r.score) }">{{ r.score }}</span>
      </div>
      <el-button size="small" type="primary" plain class="tool-action" @click="router.push('/daily-recommend')">
        <el-icon><Star /></el-icon> {{ t('chat.viewRecommend') }}
      </el-button>
    </div>

    <!-- 回测摘要 -->
    <div v-else-if="kind === 'backtest' && backtest" class="tool-card-body">
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
        <el-icon><Histogram /></el-icon> {{ t('chat.runBacktest') }}
      </el-button>
    </div>

    <!-- 个股信号 -->
    <div v-else-if="kind === 'signal' && signal" class="tool-card-body">
      <div class="quote-row">
        <span class="quote-name">{{ signal.sector || t('chat.stockSignal') }}</span>
        <code class="quote-code">{{ signal.code }}</code>
        <el-tag :type="signalTag(signal.signal).type" size="small" effect="dark">
          {{ signalTag(signal.signal).text }}
        </el-tag>
      </div>
      <div class="quote-meta">
        <span v-if="signal.score != null">{{ t('chat.sectorSentiment') }} <strong :style="{ color: scoreColor(signal.score) }">{{ signal.score }}</strong></span>
        <span v-if="signal.date">{{ signal.date }}</span>
      </div>
      <el-button size="small" type="primary" plain class="tool-action" @click="openInHome(signal.code, 'zh_a', signal.code)">
        <el-icon><CandlestickChart /></el-icon> {{ t('chat.viewOnHome') }}
      </el-button>
    </div>

    <!-- 策略代码（get_strategy 全量 / create_strategy / update_strategy 仅回 id+updated） -->
    <div v-else-if="kind === 'strategyCode' && strategyCode" class="tool-card-body">
      <div class="quote-row">
        <span v-if="strategyCode.name" class="quote-name">{{ strategyCode.name }}</span>
        <code class="quote-code">#{{ strategyCode.id }}</code>
        <span class="quote-market">{{ strategyCode.market === 'us' ? t('chat.marketUs') : t('chat.marketCn') }}</span>
        <el-tag v-if="strategyCode.updated" type="success" size="small" effect="plain">
          {{ t('chat.strategyVersionSaved') }}
        </el-tag>
      </div>
      <div v-if="strategyCode.description" class="tool-muted">{{ strategyCode.description }}</div>
      <div v-if="strategyCode.params.length" class="param-chips">
        <span class="chip-label">{{ t('chat.strategyParams') }}</span>
        <code v-for="p in strategyCode.params" :key="p.k" class="param-chip">{{ p.k }}={{ p.v }}</code>
      </div>
      <!-- 源码只读预览：复用策略库详情页的 CodeEditor（CodeMirror 懒加载 chunk），限高 200px -->
      <CodeEditor v-if="strategyCode.source" :model-value="strategyCode.source" readonly height="200px" />
      <el-button size="small" type="primary" plain class="tool-action" @click="router.push(`/strategy-library/${strategyCode.id}`)">
        <el-icon><FolderOpened /></el-icon> {{ t('chat.strategyOpen') }}
      </el-button>
    </div>

    <!-- 调优任务创建回执（create_tuning_task） -->
    <div v-else-if="kind === 'tuningTask' && tuningTask" class="tool-card-body">
      <div class="quote-row">
        <el-tag :type="statusTag(tuningTask.status).type" size="small" effect="dark">
          {{ statusTag(tuningTask.status).text }}
        </el-tag>
        <span class="tool-muted">{{ t('chat.tuneTotalCombos') }} <strong>{{ tuningTask.total }}</strong></span>
        <code class="quote-code">#{{ tuningTask.id }}</code>
      </div>
      <div v-if="tuningTask.note" class="tool-muted">{{ tuningTask.note }}</div>
      <el-button size="small" type="primary" plain class="tool-action" @click="router.push(`/tuning/${tuningTask.id}`)">
        <el-icon><DataLine /></el-icon> {{ t('chat.tuneViewDetail') }}
      </el-button>
    </div>

    <!-- 调优进度（get_tuning_status） -->
    <div v-else-if="kind === 'tuningStatus' && tuningStatus" class="tool-card-body">
      <div class="quote-row">
        <el-tag :type="statusTag(tuningStatus.status).type" size="small" effect="dark">
          {{ statusTag(tuningStatus.status).text }}
        </el-tag>
        <span class="tool-muted">{{ t('chat.tuneProgress', { done: tuningStatus.done, total: tuningStatus.total }) }}</span>
        <code class="quote-code">#{{ tuningStatus.id }}</code>
      </div>
      <el-progress
        :percentage="tuningStatus.total ? Math.min(100, Math.round((tuningStatus.done / tuningStatus.total) * 100)) : 0"
        :stroke-width="6"
      />
      <!-- 最优组合：参数 chips + 目标指标值 -->
      <div v-if="tuningStatus.best" class="best-combo">
        <div class="quote-row">
          <el-tag type="danger" size="small" effect="dark">{{ t('chat.tuneBest', { n: tuningStatus.best.idx }) }}</el-tag>
          <strong class="best-value">{{ tuningStatus.best.value }}</strong>
        </div>
        <div v-if="tuningStatus.best.params.length" class="param-chips">
          <code v-for="p in tuningStatus.best.params" :key="p.k" class="param-chip">{{ p.k }}={{ p.v }}</code>
        </div>
      </div>
      <!-- 组合排行（按目标指标排序的前 3 个已完成组合） -->
      <div v-if="tuningStatus.combos.length" class="mini-table">
        <div class="mini-row mini-head">
          <span>#</span>
          <span>{{ t('chat.tuneColParams') }}</span>
          <span class="num">{{ tuningStatus.targetLabel }}</span>
          <span class="num">{{ metricLabel('夏普比率') }}</span>
          <span class="num">{{ metricLabel('最大回撤') }}</span>
        </div>
        <div v-for="c in tuningStatus.combos" :key="c.idx" class="mini-row">
          <span>
            {{ c.idx }}
            <el-tag v-if="c.baseline" type="info" size="small" effect="plain">{{ t('chat.tuneBaseline') }}</el-tag>
          </span>
          <span class="mini-params" :title="c.params">{{ c.params || '—' }}</span>
          <span class="num">{{ c.target }}</span>
          <span class="num">{{ c.sharpe }}</span>
          <span class="num">{{ c.drawdown }}</span>
        </div>
      </div>
      <el-button size="small" type="primary" plain class="tool-action" @click="router.push(`/tuning/${tuningStatus.id}`)">
        <el-icon><DataLine /></el-icon> {{ t('chat.tuneViewDetail') }}
      </el-button>
    </div>

    <!-- 运行记录（get_run；指标为 _format_metrics_json 契约的小数形态，展示时 ×100） -->
    <div v-else-if="kind === 'runRecord' && runRecord" class="tool-card-body">
      <div class="quote-row">
        <span v-if="runRecord.strategy" class="quote-name">{{ runRecord.strategy }}</span>
        <code class="quote-code">{{ runRecord.stock }} · #{{ runRecord.id }}</code>
        <el-tag :type="statusTag(runRecord.status).type" size="small" effect="dark">
          {{ statusTag(runRecord.status).text }}
        </el-tag>
      </div>
      <div class="quote-meta">
        <span v-if="runRecord.dateRange">{{ runRecord.dateRange }}</span>
        <span v-if="runRecord.tradeCount != null">{{ t('chat.runTradeCount', { n: runRecord.tradeCount }) }}</span>
      </div>
      <div class="bt-grid">
        <div v-for="c in runRecord.cells" :key="c.label" class="bt-cell">
          <span class="bt-label">{{ c.label }}</span>
          <span class="bt-value" :class="c.cls">{{ c.value }}</span>
        </div>
      </div>
      <el-button size="small" type="primary" plain class="tool-action" @click="router.push('/runs')">
        <el-icon><Clock /></el-icon> {{ t('chat.runViewHistory') }}
      </el-button>
    </div>

    <!-- 因子分析（analyze_factor；IC 标签复用 factor.cards.*，分层表头复用 factor.table.*） -->
    <div v-else-if="kind === 'factorAnalysis' && factorAnalysis" class="tool-card-body">
      <div class="quote-row">
        <span class="quote-name">{{ factorAnalysis.name }}</span>
      </div>
      <div class="bt-grid">
        <div v-for="c in factorAnalysis.cards" :key="c.label" class="bt-cell">
          <span class="bt-label">{{ c.label }}</span>
          <span class="bt-value">{{ c.value }}</span>
        </div>
      </div>
      <div class="quote-meta">
        <span v-if="factorAnalysis.universe != null">{{ t('factor.meta.universe', { n: factorAnalysis.universe }) }}</span>
        <span>
          {{ t('factor.meta.monotonicity') }}
          <el-tag :type="factorAnalysis.monotonic ? 'success' : 'info'" size="small">
            {{ factorAnalysis.monotonic ? t('factor.meta.monotonic') : t('factor.meta.notMonotonic') }}
          </el-tag>
          <span v-if="factorAnalysis.ratio != null">{{ t('factor.meta.ratio', { ratio: factorAnalysis.ratio }) }}</span>
        </span>
      </div>
      <!-- 分层统计（quantile 行键以 services/factor.py 为准：quantile/mean_return/sharpe_ratio/win_rate） -->
      <div v-if="factorAnalysis.quantiles.length" class="mini-table four">
        <div class="mini-row mini-head">
          <span>{{ t('factor.table.quantile') }}</span>
          <span class="num">{{ t('factor.table.meanReturn') }}</span>
          <span class="num">{{ t('factor.table.sharpe') }}</span>
          <span class="num">{{ t('factor.table.winRate') }}</span>
        </div>
        <div v-for="q in factorAnalysis.quantiles" :key="q.quantile" class="mini-row">
          <span>{{ q.quantile }}</span>
          <span class="num">{{ q.meanReturn }}</span>
          <span class="num">{{ q.sharpe }}</span>
          <span class="num">{{ q.winRate }}</span>
        </div>
      </div>
      <div v-if="typeof data?.note === 'string' && data.note" class="tool-muted">{{ data.note }}</div>
      <el-button
        v-if="factorAnalysis.factorId != null"
        size="small"
        type="primary"
        plain
        class="tool-action"
        @click="router.push(`/factor-library/${factorAnalysis.factorId}`)"
      >
        <el-icon><DataAnalysis /></el-icon> {{ t('chat.factorOpenDetail') }}
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
/* 策略代码卡片：生效参数 chips */
.param-chips {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-wrap: wrap;
}
.chip-label {
  font-size: 0.72rem;
  color: var(--text-muted);
}
.param-chip {
  font-size: 0.7rem;
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 999px;
  padding: 0 6px;
  color: var(--text-muted);
}
/* 调优进度卡片：最优组合高亮块 */
.best-combo {
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 5px 6px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.best-value {
  font-weight: 700;
  font-size: 0.88rem;
  font-variant-numeric: tabular-nums;
  color: var(--danger);
}
/* 调优排行 / 分层统计小表 */
.mini-table {
  font-size: 0.72rem;
  color: var(--text-muted);
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.mini-row {
  display: grid;
  align-items: center;
  gap: 6px;
  padding: 2px 4px;
  border-radius: 4px;
  grid-template-columns: auto 1fr 56px 52px 56px;
}
/* 因子分层表无参数列：等分四列（调优排行是 #/参数/目标/夏普/回撤 五列） */
.mini-table.four .mini-row {
  grid-template-columns: 1fr 1fr 1fr 1fr;
}
.mini-head {
  font-weight: 600;
  border-bottom: 1px solid var(--border);
  border-radius: 0;
}
.mini-row .num {
  text-align: right;
  font-variant-numeric: tabular-nums;
}
.mini-params {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
