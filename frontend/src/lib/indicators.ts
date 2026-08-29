/**
 * 技术指标数学（纯函数，非 composable）——从 HomeView 原样迁入。
 *
 * 口径对齐国内主流行情软件，注释随迁：
 *   - MA：简单移动平均，窗口不足前置 null；
 *   - EMA：递推初值取首值；
 *   - BOLL(N=20,±2σ)：σ 为总体标准差（除以 N，对齐国内软件 STD 口径，非样本标准差）；
 *   - MACD(12,26,9)：hist=(DIF-DEA)*2，对齐国内软件红绿柱（×2 放大展示口径）；
 *   - KDJ(9,3,3)：SMA(RSV,3,1) 平滑，初值取首根 RSV（通达信口径）；
 *   - RSI(N)：Wilder 平滑（SMA(U,N,1)，国内软件口径）。
 */

/** 简单移动平均：窗口不足的位置补 null */
export function calcMA(closes: number[], period: number): (number | null)[] {
  const out: (number | null)[] = []
  for (let i = 0; i < closes.length; i++) {
    if (i < period - 1) { out.push(null); continue }
    let sum = 0
    for (let j = i - period + 1; j <= i; j++) sum += closes[j]!
    out.push(+(sum / period).toFixed(2))
  }
  return out
}

/** 指数移动平均：递推初值取首值（k = 2/(n+1)） */
export function calcEMA(src: number[], n: number): number[] {
  const k = 2 / (n + 1)
  let prev = src[0] ?? 0
  return src.map((v, i) => {
    prev = i === 0 ? v : v * k + prev * (1 - k)
    return prev
  })
}

/** 布林带 BOLL(N=20,±2σ)：σ 为总体标准差（对齐国内软件 STD 口径） */
export function calcBOLL(
  closes: number[],
  n = 20,
  mult = 2,
): { mid: (number | null)[]; up: (number | null)[]; low: (number | null)[] } {
  const mid = calcMA(closes, n)
  const up: (number | null)[] = []
  const low: (number | null)[] = []
  for (let i = 0; i < closes.length; i++) {
    if (i < n - 1 || mid[i] == null) { up.push(null); low.push(null); continue }
    let s = 0
    for (let j = i - n + 1; j <= i; j++) { const d = closes[j]! - mid[i]!; s += d * d }
    const sd = Math.sqrt(s / n)
    up.push(+(mid[i]! + mult * sd).toFixed(2))
    low.push(+(mid[i]! - mult * sd).toFixed(2))
  }
  return { mid, up, low }
}

/** MACD(12,26,9)：hist=(DIF-DEA)*2 对齐国内软件红绿柱 */
export function calcMACD(closes: number[]): { dif: number[]; dea: number[]; hist: number[] } {
  const ema12 = calcEMA(closes, 12)
  const ema26 = calcEMA(closes, 26)
  const dif = closes.map((_, i) => ema12[i]! - ema26[i]!)
  const dea = calcEMA(dif, 9)
  return {
    dif: dif.map((v) => +v.toFixed(3)),
    dea: dea.map((v) => +v.toFixed(3)),
    hist: dif.map((v, i) => +((v - dea[i]!) * 2).toFixed(3)),
  }
}

/**
 * KDJ(9,3,3)：SMA(RSV,3,1) 平滑，初值取首根 RSV（通达信口径）。
 *
 * 参数 ohlcv 的实际顺序是 [open, close, low, high]（与 /api/kline ohlcv 契约一致，
 * 不是 OHLC 习惯序）：本函数只消费 o[2]=low 与 o[3]=high 求区间极值，o[1]=close 求 RSV。
 */
export function calcKDJ(ohlcv: [number, number, number, number][]): { K: number[]; D: number[]; J: number[] } {
  const lows = ohlcv.map((o) => o[2])
  const highs = ohlcv.map((o) => o[3])
  const K: number[] = [], D: number[] = [], J: number[] = []
  let kv = 50, dv = 50
  for (let i = 0; i < ohlcv.length; i++) {
    const lo = Math.min(...lows.slice(Math.max(0, i - 8), i + 1))
    const hi = Math.max(...highs.slice(Math.max(0, i - 8), i + 1))
    const rsv = hi === lo ? 50 : ((ohlcv[i]![1] - lo) / (hi - lo)) * 100
    kv = i === 0 ? rsv : (2 * kv + rsv) / 3
    dv = i === 0 ? rsv : (2 * dv + kv) / 3
    K.push(+kv.toFixed(2)); D.push(+dv.toFixed(2)); J.push(+(3 * kv - 2 * dv).toFixed(2))
  }
  return { K, D, J }
}

/** RSI(N)：Wilder 平滑（SMA(U,N,1)，国内软件口径）；首根无前收，置 null */
export function calcRSI(closes: number[], n: number): (number | null)[] {
  const out: (number | null)[] = [null]
  let au = 0, ad = 0
  for (let i = 1; i < closes.length; i++) {
    const u = Math.max(closes[i]! - closes[i - 1]!, 0)
    const d = Math.max(closes[i - 1]! - closes[i]!, 0)
    au = (au * (n - 1) + u) / n
    ad = (ad * (n - 1) + d) / n
    out.push(au + ad === 0 ? 50 : +(100 * au / (au + ad)).toFixed(2))
  }
  return out
}
