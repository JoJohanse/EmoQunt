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
}

/** 回测响应（JSON） */
export interface BacktestResult {
  strategy_name: string
  stock_code: string
  market: Market
  metrics: BacktestMetrics
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
