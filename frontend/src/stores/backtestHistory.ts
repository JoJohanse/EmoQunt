import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { BacktestRequest, BacktestResult, Market } from '@/api/types'

/** 一条回测历史记录（只保留摘要，不存时序大数组） */
export interface BacktestHistoryRecord {
  id: string
  /** 完成时间（ISO 字符串） */
  ts: string
  strategyName: string
  stockCode: string
  market: Market
  totalReturn: number
  annualReturn: number
  maxDrawdown: number
  sharpe: number
  winRate: number
  /** 完整请求参数，用于"一键重跑" */
  params: BacktestRequest
}

const MAX_RECORDS = 20

/**
 * 回测历史 + 上次表单填写值，持久化到 localStorage。
 * 后端目前不保存回测结果（仅 PNG），历史由浏览器本地记录（对标 FreqUI 的交易历史面板）。
 */
export const useBacktestHistoryStore = defineStore(
  'backtestHistory',
  () => {
    const records = ref<BacktestHistoryRecord[]>([])
    const lastForm = ref<BacktestRequest | null>(null)

    /** 回测成功后记录摘要，并记忆表单参数 */
    function add(params: BacktestRequest, result: BacktestResult) {
      const m = result.metrics
      records.value.unshift({
        id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
        ts: new Date().toISOString(),
        strategyName: params.strategy_name,
        stockCode: params.stock_code,
        market: params.market,
        totalReturn: m.总收益率,
        annualReturn: m.年化收益率,
        maxDrawdown: m.最大回撤,
        sharpe: m.夏普比率,
        winRate: m.胜率,
        params: { ...params },
      })
      if (records.value.length > MAX_RECORDS) {
        records.value = records.value.slice(0, MAX_RECORDS)
      }
      lastForm.value = { ...params }
    }

    /** 仅记忆表单（未运行成功时也可保存草稿） */
    function saveForm(params: BacktestRequest) {
      lastForm.value = { ...params }
    }

    function remove(id: string) {
      records.value = records.value.filter((r) => r.id !== id)
    }

    function clear() {
      records.value = []
    }

    return { records, lastForm, add, saveForm, remove, clear }
  },
  { persist: true },
)
