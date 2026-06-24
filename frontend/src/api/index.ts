import axios from 'axios'
import type {
  BacktestRequest,
  BacktestResult,
  DailyRecommendData,
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

/** 舆情 API */
export const sentimentApi = {
  get(): Promise<SentimentData> {
    return http.get('/sentiment/data').then((r) => r.data)
  },
  refresh(): Promise<SentimentData> {
    return http.get('/sentiment/data').then((r) => r.data)
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

export default http
