import type { PiniaPluginContext } from 'pinia'

// 扩展 Pinia store 选项类型，使 defineStore 的第三个参数支持 persist（本地持久化）
declare module 'pinia' {
  export interface DefineStoreOptionsBase<S, Store> {
    /** 本地持久化选项，见 createPersistedState */
    persist?: boolean | PersistOptions
  }
}

/**
 * 轻量 Pinia 持久化插件（对标 pinia-plugin-persistedstate，零依赖实现）。
 *
 * store 通过 defineStore 的第三个参数 opt-in：
 *   defineStore('id', () => {...}, { persist: true })
 *   defineStore('id', () => {...}, { persist: { pick: ['messages'], revive: (s) => s } })
 *
 * 恢复时机：store 初始化时从 localStorage 读取并 $patch；
 * 之后 store.$subscribe 监听任何变更，序列化（可按 pick 挑选字段）后写回。
 */
export interface PersistOptions {
  /** localStorage 键名，默认 `emoqunt:<store.$id>` */
  key?: string
  /** 只持久化 state 中的部分字段（顶层键） */
  pick?: string[]
  /** 反序列化后的修正钩子（如清理 streaming 标记、过期数据） */
  revive?: (state: Record<string, any>) => Record<string, any>
}

const PREFIX = 'emoqunt:'

function serialize(state: Record<string, any>, pick?: string[]): string {
  const picked: Record<string, any> = pick ? {} : state
  if (pick) {
    for (const k of pick) {
      if (k in state) picked[k] = state[k]
    }
  }
  return JSON.stringify(picked)
}

export function createPersistedState() {
  return (ctx: PiniaPluginContext) => {
    const opt = ctx.options.persist as boolean | PersistOptions | undefined
    if (!opt) return
    const config: PersistOptions = opt === true ? {} : opt
    const key = PREFIX + (config.key ?? ctx.store.$id)

    // 1) 恢复
    try {
      const raw = localStorage.getItem(key)
      if (raw) {
        let saved = JSON.parse(raw)
        if (config.revive) saved = config.revive(saved)
        ctx.store.$patch(saved)
      }
    } catch (e) {
      // 数据损坏或存储不可用时静默降级为内存态
      console.warn(`[persist] 恢复 ${key} 失败，忽略本地缓存`, e)
    }

    // 2) 订阅变更并写回
    ctx.store.$subscribe((_mutation, state) => {
      try {
        localStorage.setItem(key, serialize(state, config.pick))
      } catch (e) {
        // quota 溢出 / 隐私模式等，静默降级
        console.warn(`[persist] 写入 ${key} 失败`, e)
      }
    })
  }
}
