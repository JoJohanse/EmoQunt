import axios from 'axios'
import type {
  BacktestRequest,
  BacktestResult,
  CompareRequest,
  CompareResult,
  DailyRecommendData,
  FactorAnalysisRequest,
  FactorAnalysisResult,
  KlineData,
  MarketBreadth,
  SectorBoardData,
  SentimentCalendarItem,
  SentimentData,
  StrategyDetail,
} from './types'

const http = axios.create({
  // 开发环境经 Vite 代理转发到 FastAPI；生产环境 FastAPI 直接托管前端，同源
  baseURL: '/api',
  timeout: 300000, // 回测可能耗时较长
})

// 统一错误处理
http.interceptors.response.use(
  (resp) => resp,
  (error) => {
    const msg = error?.response?.data?.detail || error?.response?.data?.error || error.message
    return Promise.reject(new Error(typeof msg === 'string' ? msg : '请求失败'))
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

/** K 线 API（首页看板蜡烛图） */
export const klineApi = {
  get(stock_code: string, market: 'zh_a' | 'us' = 'zh_a', days = 180): Promise<KlineData> {
    return http
      .get('/kline', { params: { stock_code, market, days } })
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
}

export default http
