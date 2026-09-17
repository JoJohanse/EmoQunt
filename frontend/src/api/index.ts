import axios from 'axios'
import { t } from '@/locales'
import type {
  BacktestRequest,
  BacktestResult,
  BacktestRunDetail,
  BacktestRunSummary,
  CodeStrategyDetail,
  CodeStrategySummary,
  CompareRequest,
  CompareResult,
  DailyRecommendData,
  FactorAnalysisRequest,
  FactorAnalysisResult,
  KlineData,
  LibraryValidateResult,
  Market,
  MarketBreadth,
  SectorBoardData,
  SourceHealthData,
  SentimentCalendarItem,
  SentimentData,
  StrategyDetail,
  FactorDetail,
  FactorSummary,
  FactorVersion,
  StrategyVersion,
  TuningTask,
} from './types'

const http = axios.create({
  // 开发环境经 Vite 代理转发到 FastAPI；生产环境 FastAPI 直接托管前端，同源
  baseURL: '/api',
  timeout: 300000, // 回测可能耗时较长
})

// 统一错误处理（兜底文案住在 chat.* 命名空间，与对话错误气泡同源；后端返回的 detail 原样透出）
http.interceptors.response.use(
  (resp) => resp,
  (error) => {
    const msg = error?.response?.data?.detail || error?.response?.data?.error || error.message
    return Promise.reject(new Error(typeof msg === 'string' ? msg : t('chat.requestFailed')))
  },
)

/** 策略相关 API */
export const strategyApi = {
  /** 获取策略列表（含参数） */
  list(): Promise<StrategyDetail[]> {
    return http.get('/strategies/list').then((r) => r.data)
  },
  /** 获取策略详情 */
  detail(name: string): Promise<StrategyDetail> {
    return http.get(`/strategies/detail/${name}`).then((r) => r.data)
  },
  /** 获取策略模板 */
  templates(): Promise<Record<string, any>> {
    return http.get('/strategies/templates').then((r) => r.data)
  },
  /** 创建策略 */
  create(payload: {
    name: string
    description?: string
    template: string
    parameters: any[]
  }): Promise<{ success: boolean; name: string }> {
    return http.post('/strategies/create_new', payload).then((r) => r.data)
  },
  /** 从模板创建 */
  createFromTemplate(payload: {
    name: string
    description?: string
    template: string
  }): Promise<{ success: boolean; name: string }> {
    return http.post('/strategies/create_from_template', payload).then((r) => r.data)
  },
  /** 更新策略 */
  update(name: string, payload: any): Promise<{ success: boolean }> {
    return http.put(`/strategies/${name}`, payload).then((r) => r.data)
  },
  /** 删除策略 */
  remove(name: string): Promise<{ success: boolean }> {
    return http.delete(`/strategies/${name}`).then((r) => r.data)
  },
}

/** 回测 API（JSON，返回时序数据供前端动态绘图） */
export const backtestApi = {
  run(params: BacktestRequest): Promise<BacktestResult> {
    return http.post('/backtest/run', params).then((r) => r.data)
  },
}

/** 策略对比 API */
export const compareApi = {
  run(params: CompareRequest): Promise<CompareResult> {
    return http.post('/strategies/compare', params).then((r) => r.data)
  },
}

/** 因子分析 API */
export const factorApi = {
  analyze(params: FactorAnalysisRequest): Promise<FactorAnalysisResult> {
    return http.post('/factor/analyze', params).then((r) => r.data)
  },
}

/** K 线 API（首页看板蜡烛图；period=day/week/month 服务端聚合，adjust=qfq/hfq/nfq，kind=index 走指数链；提供 range 时进入区间模式，供回测买卖点对齐历史区间） */
export const klineApi = {
  get(
    stock_code: string,
    market: 'zh_a' | 'us' = 'zh_a',
    days = 180,
    period: 'day' | 'week' | 'month' = 'day',
    adjust: 'qfq' | 'hfq' | 'nfq' | '' = '',
    kind: '' | 'index' = '',
    range?: { start: string; end: string },
  ): Promise<KlineData> {
    return http
      .get('/kline', {
        params: {
          stock_code, market, days, period, adjust, kind,
          ...(range ? { start_date: range.start, end_date: range.end } : {}),
        },
      })
      .then((r) => r.data)
  },
}

/** 舆情 API */
export const sentimentApi = {
  get(): Promise<SentimentData> {
    return http.get('/sentiment/data').then((r) => r.data)
  },
  refresh(): Promise<SentimentData> {
    return http.get('/sentiment/data').then((r) => r.data)
  },
  /** 情绪历史日历（按日期升序的单日情绪摘要） */
  calendar(): Promise<SentimentCalendarItem[]> {
    return http.get('/sentiment/calendar').then((r) => r.data)
  },
}

/** 每日推荐 API */
export const recommendApi = {
  get(): Promise<DailyRecommendData> {
    return http.get('/daily-recommend').then((r) => r.data)
  },
  refresh(): Promise<DailyRecommendData> {
    return http.get('/daily-recommend/refresh').then((r) => r.data)
  },
}

/** 市场宽度 / 板块行情 API（首页看板） */
export const marketApi = {
  breadth(): Promise<MarketBreadth> {
    return http.get('/market/breadth').then((r) => r.data)
  },
  sectors(): Promise<SectorBoardData> {
    return http.get('/market/sectors').then((r) => r.data)
  },
  /** 数据源健康心跳（进程内存态，未启用的源无记录） */
  sourceHealth(): Promise<SourceHealthData> {
    return http.get('/data/source-health').then((r) => r.data)
  },
}

/** 策略库 v2（代码策略）API */
export const libraryApi = {
  list(params: { market?: string; q?: string } = {}): Promise<{ strategies: CodeStrategySummary[] }> {
    return http.get('/v2/strategies', { params }).then((r) => r.data)
  },
  detail(id: number): Promise<CodeStrategyDetail> {
    return http.get(`/v2/strategies/${id}`).then((r) => r.data)
  },
  create(payload: { name: string; description?: string; market: Market; source: string; params?: Record<string, any>; tags?: string }): Promise<{ id: number; name: string }> {
    return http.post('/v2/strategies', payload).then((r) => r.data)
  },
  update(id: number, payload: { source?: string; description?: string; params?: Record<string, any>; tags?: string; note?: string }): Promise<{ id: number; updated: boolean }> {
    return http.put(`/v2/strategies/${id}`, payload).then((r) => r.data)
  },
  remove(id: number): Promise<{ id: number; deleted: boolean }> {
    return http.delete(`/v2/strategies/${id}`).then((r) => r.data)
  },
  validate(source: string): Promise<LibraryValidateResult> {
    return http.post('/v2/strategies/validate', { source }).then((r) => r.data)
  },
  versions(id: number): Promise<{ versions: StrategyVersion[] }> {
    return http.get(`/v2/strategies/${id}/versions`).then((r) => r.data)
  },
  versionSource(versionId: number): Promise<StrategyVersion & { source: string; params: Record<string, any> }> {
    return http.get(`/v2/strategies/versions/${versionId}`).then((r) => r.data)
  },
  restoreVersion(id: number, versionId: number): Promise<{ id: number; restored_from: number }> {
    return http.post(`/v2/strategies/${id}/versions/${versionId}/restore`).then((r) => r.data)
  },
}

/** 运行历史 API（异步回测） */
export const runsApi = {
  submit(params: BacktestRequest & { strategy_kind: 'template' | 'code'; strategy_id?: number }): Promise<{ id: number; status: string }> {
    return http.post('/v2/backtest/runs', params).then((r) => r.data)
  },
  list(params: { strategy_kind?: string; strategy_id?: number; market?: string; status?: string; limit?: number; offset?: number } = {}): Promise<{ runs: BacktestRunSummary[] }> {
    return http.get('/v2/backtest/runs', { params }).then((r) => r.data)
  },
  detail(id: number): Promise<BacktestRunDetail> {
    return http.get(`/v2/backtest/runs/${id}`).then((r) => r.data)
  },
}

/** 因子库 API（Python 因子 CRUD + 横截面分析；zh_a 限定） */
export const factorLibApi = {
  list(params: { market?: string; q?: string } = {}): Promise<{ factors: FactorSummary[] }> {
    return http.get('/v2/factors', { params }).then((r) => r.data)
  },
  detail(id: number): Promise<FactorDetail> {
    return http.get(`/v2/factors/${id}`).then((r) => r.data)
  },
  create(payload: { name: string; description?: string; market?: string; source: string; tags?: string }): Promise<{ id: number; name: string }> {
    return http.post('/v2/factors', payload).then((r) => r.data)
  },
  update(id: number, payload: { source?: string; description?: string; tags?: string; note?: string }): Promise<{ id: number; updated: boolean }> {
    return http.put(`/v2/factors/${id}`, payload).then((r) => r.data)
  },
  remove(id: number): Promise<{ id: number; deleted: boolean }> {
    return http.delete(`/v2/factors/${id}`).then((r) => r.data)
  },
  validate(source: string): Promise<{ ok: boolean; errors: string[] }> {
    return http.post('/v2/factors/validate', { source }).then((r) => r.data)
  },
  versions(id: number): Promise<{ versions: FactorVersion[] }> {
    return http.get(`/v2/factors/${id}/versions`).then((r) => r.data)
  },
  versionSource(versionId: number): Promise<FactorVersion & { source: string }> {
    return http.get(`/v2/factors/versions/${versionId}`).then((r) => r.data)
  },
  restoreVersion(id: number, versionId: number): Promise<{ id: number; restored_from: number }> {
    return http.post(`/v2/factors/${id}/versions/${versionId}/restore`).then((r) => r.data)
  },
  analyze(id: number, payload: { start_date: string; end_date: string; n_quantiles?: number; forward_period?: number }): Promise<FactorAnalysisResult> {
    return http.post(`/v2/factors/${id}/analyze`, payload).then((r) => r.data)
  },
}

/** 参数调优 API（网格笛卡尔积 ≤63 组 + 基准；apply 只写策略参数） */
export const tuningApi = {
  create(payload: {
    strategy_kind: 'template' | 'code'
    strategy_id?: number
    strategy_name?: string
    stock_code: string
    market: Market
    start_date: string
    end_date: string
    initial_capital?: number
    commission_rate?: number
    param_grid: Record<string, (number | boolean)[]>
    target_metric?: string
  }): Promise<{ id: number; status: string; total_combos: number }> {
    return http.post('/v2/tuning/tasks', payload).then((r) => r.data)
  },
  list(params: { strategy_kind?: string; strategy_id?: number; limit?: number; offset?: number } = {}): Promise<{ tasks: TuningTask[] }> {
    return http.get('/v2/tuning/tasks', { params }).then((r) => r.data)
  },
  detail(id: number): Promise<TuningTask> {
    return http.get(`/v2/tuning/tasks/${id}`).then((r) => r.data)
  },
  apply(id: number, comboIndex: number): Promise<{ id: number; combo_index: number; applied_params: Record<string, number | boolean> }> {
    return http.post(`/v2/tuning/tasks/${id}/apply`, { combo_index: comboIndex }).then((r) => r.data)
  },
}

export default http
