/** 后端 API 返回的类型定义 */

/** 市场类型 */
export type Market = 'zh_a' | 'us'

/** 策略参数 */
export interface StrategyParam {
  name: string
  value?: string | number | boolean
  default?: string | number | boolean
  type: 'int' | 'float' | 'bool' | string
  label?: string
  min?: number
  max?: number
}

/** 策略详情 */
export interface StrategyDetail {
  name: string
  description: string
  parameters: StrategyParam[]
  template?: string
  template_name?: string
  is_user_strategy: boolean
}

/** 回测请求参数 */
export interface BacktestRequest {
  strategy_name: string
  stock_code: string
  start_date: string // YYYY-MM-DD
  end_date: string // YYYY-MM-DD
  initial_capital: number
  commission_rate: number
  market: Market
}

/** 回测绩效指标（数值） */
export interface BacktestMetrics {
  总收益率: number
  年化收益率: number
  夏普比率: number
  最大回撤: number
  胜率: number
  盈亏比: number
  Alpha?: number
  Beta?: number
  信息比率?: number
  // 完整绩效报告新增（可选）
  年化波动率?: number
  卡玛比率?: number
  下行标准差?: number
  'VaR (95%)'?: number
  'CVaR (95%)'?: number
  交易次数?: number
  盈利交易数?: number
  亏损交易数?: number
  平均盈利?: number
  平均亏损?: number
  最大回撤开始时间?: string
  最大回撤结束时间?: string
}

/** 风险分析报告（RiskManager 事后分析） */
export interface RiskReport {
  portfolio_value: number
  current_drawdown: number
  max_drawdown_limit: number
  volatility: number
  sharpe_ratio: number
  blacklist_count: number
  var_analysis: {
    historical_var: number
    parametric_var: number
    cvar: number
    confidence_level: number
  }
  stress_test: Record<string, number>
  risk_limits: Record<string, number>
}

/** 回测响应（JSON） */
export interface BacktestResult {
  strategy_name: string
  stock_code: string
  market: Market
  metrics: BacktestMetrics
  risk_report?: RiskReport
  // 时序数据，用于前端 ECharts 动态绘制
  dates: string[] // ISO 日期
  equity_curve: number[] // 策略净值
  benchmark_curve?: number[] // 基准净值（可选）
  drawdown: number[] // 回撤序列
  daily_returns: number[] // 日收益率
}

/** 板块情绪得分 */
export interface SectorScore {
  name: string
  sentiment: number
  stocks?: { code: string; name: string }[]
}

/** 舆情数据 */
export interface SentimentData {
  news_list: NewsItem[]
  sectors: SectorScore[]
  news_count: number
  update_time: string
}

/** 新闻条目 */
export interface NewsItem {
  title: string
  source?: string
  url?: string
  date?: string
}

/** 每日推荐股票 */
export interface RecommendedStock {
  rank: number
  code: string
  name: string
  sector: string
  score: number
  reason: string
}

/** 每日推荐数据 */
export interface DailyRecommendData {
  date: string
  top_sectors: SectorScore[]
  recommendations: RecommendedStock[]
}

/** K 线 OHLCV 数据（首页看板蜡烛图） */
export interface KlineData {
  code: string
  market: Market
  name: string
  dates: string[]
  /** ECharts 蜡烛图格式：[open, close, low, high] */
  ohlcv: [number, number, number, number][]
  volumes: number[]
}

/** 看板可选标的（预设） */
export interface WatchTarget {
  code: string
  market: Market
  name: string
}

// ===== 策略对比 =====

/** 对比请求 */
export interface CompareRequest {
  strategy_names: string[]
  stock_code: string
  start_date: string
  end_date: string
  market: Market
  initial_capital: number
  commission_rate: number
}

/** 单个策略的对比序列 */
export interface CompareSeries {
  name: string
  equity_curve: number[]
  metrics: {
    总收益率: number
    年化收益率: number
    夏普比率: number
    最大回撤: number
    胜率: number
    盈亏比: number
    Alpha?: number | null
    Beta?: number | null
  }
}

/** 对比结果 */
export interface CompareResult {
  dates: string[]
  common_start?: string | null
  common_end?: string | null
  series: CompareSeries[]
  errors?: { name: string; error: string }[]
  stock_code: string
  market: Market
  error?: string
}

// ===== 因子分析 =====

/** 因子类型 */
export type FactorType = 'momentum' | 'rsi' | 'volatility' | 'volume_ratio'

/** 因子分析请求 */
export interface FactorAnalysisRequest {
  factor_type: FactorType
  start_date: string
  end_date: string
  universe?: string
  n_quantiles?: number
  forward_period?: number
}

/** 因子分析结果 */
export interface FactorAnalysisResult {
  factor_type: string
  ic_stats: {
    ic_mean: number
    rank_ic_mean: number
    ic_ir: number
    rank_ic_ir: number
    ic_win_rate: number
    rank_ic_win_rate: number
    ic_positive_rate: number
  }
  ic_series: { date: string; ic: number; rank_ic: number }[]
  quantile_stats: {
    quantile: string
    mean_return: number
    sharpe_ratio: number
    win_rate: number
  }[]
  quantile_cumreturns: { date: string; values: number[] }[]
  monotonicity: {
    monotonic: boolean
    monotonicity_ratio: number
  }
  universe_size: number
  error?: string
}

// ===== AI 投资助手 =====

/** 对话消息 */
export interface ChatMessage {
  role: 'user' | 'assistant' | 'system'
  content: string
  /** 工具调用记录（仅 assistant 消息，可选） */
  toolCalls?: ToolCallEvent[]
  /** 是否正在流式输出 */
  streaming?: boolean
  /** 错误信息 */
  error?: string
}

/** 工具调用事件（SSE 推送） */
export interface ToolCallEvent {
  name: string
  args: string
  result: string
}

/** SSE 事件类型 */
export type SseEvent =
  | { type: 'token'; content: string }
  | { type: 'tool'; name: string; args: string; result: string }
  | { type: 'done' }
  | { type: 'error'; content: string }

