import { onBeforeUnmount, onMounted } from 'vue'

export interface PollingOptions {
  /** 基础间隔（毫秒）。默认 60s —— 日线级数据无需求高频 */
  intervalMs?: number
  /** 连续失败时的最大退避倍数：实际间隔 = intervalMs * 2^min(fails, maxBackoff) */
  maxBackoff?: number
}

/**
 * SWR 式轮询（语义对标 stale-while-revalidate：先保留旧数据，后台取新、到货后替换）。
 * - 页面不可见（document.hidden）时暂停轮询，恢复可见立即补一轮；
 * - 失败指数退避（防抖动数据源被打爆），成功后复位；
 * - 调用方需保证 fn 内部"失败静默降级、保留上帧数据"。
 */
export function usePolling(fn: () => Promise<void> | void, options: PollingOptions = {}) {
  const intervalMs = options.intervalMs ?? 60_000
  const maxBackoff = options.maxBackoff ?? 5
  let timer: ReturnType<typeof setTimeout> | undefined
  let fails = 0
  let running = false

  function schedule() {
    clearTimeout(timer)
    const delay = Math.min(intervalMs * 2 ** Math.min(fails, maxBackoff), intervalMs * 2 ** maxBackoff)
    timer = setTimeout(tick, delay)
  }

  async function tick() {
    if (running || document.hidden) return
    running = true
    try {
      await fn()
      fails = 0
    } catch {
      fails += 1
    } finally {
      running = false
    }
    schedule()
  }

  function onVisibility() {
    if (!document.hidden) {
      clearTimeout(timer)
      tick()
    }
  }

  onMounted(() => {
    document.addEventListener('visibilitychange', onVisibility)
    schedule()
  })

  onBeforeUnmount(() => {
    clearTimeout(timer)
    document.removeEventListener('visibilitychange', onVisibility)
  })
}
