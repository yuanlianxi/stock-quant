/**
 * K 线数据 composable（sq-0009-p6 + 决策 7-C + sq-0009-round-5 commit 11/12）
 *
 * 策略：
 * - daily：直接调 /daily/{symbol} 端点
 * - 分时：调 /minute/{symbol}，缺时降级到 5min resample
 * - mixDaily：分时 + akshare 5min 窗口（~10 天）外用日线补齐
 *
 * 用法：
 *   const { data, loading, source } = await fetchKLineData('AG', '15min')
 *   // source: 'cache' | 'resample' | 'empty' | 'mix' | 'daily'
 */
import { ref } from 'vue'
import { useApi } from '@/composables/useApi'

export type KLineSource = 'cache' | 'resample' | 'empty' | 'mix' | 'daily'
export type KLinePeriod = '5min' | '15min' | '30min' | '60min' | 'daily'

interface KLineBar {
  datetime: string
  open: number
  high: number
  low: number
  close: number
  volume: number
  /** sq-0009-round-5 hotfix2: bar 类型标记（minute=分时/daily=日线补缺）*/
  bar_type?: 'minute' | 'daily'
}

export function useKLineData() {
  const data = ref<KLineBar[]>([])
  const source = ref<KLineSource>('empty')
  const loading = ref(false)
  const error = ref<string | null>(null)

  /**
   * 拉取 K 线（带降级 + 混合）
   * @param symbol 品种
   * @param period 目标周期（5min / 15min / 30min / 60min / daily）
   * @param days 拉多少天（默认 7）
   * @param mixDaily 是否混合日线（默认 true，period=分时且 days>10 时生效）
   */
  async function fetchKLineData(symbol: string, period: KLinePeriod, days = 7, mixDaily = true) {
    loading.value = true
    error.value = null
    data.value = []
    source.value = 'empty'

    try {
      const api = useApi()

      // 0. daily 周期：直接走 /daily/{symbol}
      if (period === 'daily') {
        const r = await api.get<any>(`/daily/${symbol}`, { days })
        if (r?.records?.length > 0) {
          data.value = normalizeBars(r.records)
          source.value = 'daily'
          return { data: data.value, source: source.value }
        }
        source.value = 'empty'
        return { data: [], source: 'empty' as KLineSource }
      }

      // 1. 先查目标分时周期
      const r1 = await api.get<any>(`/minute/${symbol}`, { period, days })
      if (r1?.records?.length > 0) {
        let bars = normalizeBars(r1.records)

        // 2. mixDaily：所有分时周期都支持（5/15/30/60min）+ days>10
        // 智能补缺：用 5min 实际最早日期动态算 daily 拉取范围
        // 例：5min 最早 5/29，days=180 → daily 拉 (now - 5/29) + buffer ≈ 6 个月
        const isMinute = (period === '5min' || period === '15min' || period === '30min' || period === '60min')
        if (mixDaily && isMinute && days > 10) {
          try {
            // 用 5min 实际最早日期算 daily 起点
            const earliestMinDt = bars[0].datetime  // 'YYYY-MM-DD HH:MM:SS'
            const earliestDate = earliestMinDt.slice(0, 10)  // 'YYYY-MM-DD'
            // daily 需要覆盖 (用户期望起点 ~ 5min 最早日期)
            // 但 /daily 端点 days=N 是相对 now 的，所以传 N 让 daily 覆盖到 N 天前
            // 算：从 now 到 5min 最早日期的天数 + buffer
            const earliestMs = new Date(earliestDate).getTime()
            const nowMs = Date.now()
            const daysNeeded = Math.ceil((nowMs - earliestMs) / 86400_000) + 10  // +10 buffer
            // 后端 daily 端点单次最多 3 年
            const dailyDays = Math.min(Math.max(daysNeeded, days), 1095)
            const dailyResp = await api.get<any>(`/daily/${symbol}`, { days: dailyDays })
            if (dailyResp?.records?.length > 0) {
              const dailyBars = normalizeDailyAs5min(dailyResp.records)
              bars = mergeBars(bars, dailyBars)
              source.value = 'mix'
              data.value = bars
              return { data: data.value, source: source.value }
            }
          } catch {
            // 拉日线失败时不影响分时数据
          }
        }

        data.value = bars
        source.value = 'cache'
        return { data: data.value, source: source.value }
      }

      // 3. 降级：resample 5min（period 不是 5min 时）
      if (period !== '5min') {
        const r2 = await api.get<any>(`/minute/${symbol}`, { period: '5min', days })
        if (r2?.records?.length > 0) {
          const bars5 = normalizeBars(r2.records)
          data.value = resampleBars(bars5, period)
          source.value = 'resample'
          return { data: data.value, source: source.value }
        }
      }

      // 4. 都无：拉日线作为最后兜底（如果 mixDaily）
      if (mixDaily && days > 10) {
        try {
          const dailyResp = await api.get<any>(`/daily/${symbol}`, { days })
          if (dailyResp?.records?.length > 0) {
            const dailyBars = normalizeDailyAs5min(dailyResp.records)
            data.value = dailyBars
            source.value = 'daily'
            return { data: data.value, source: source.value }
          }
        } catch {}
      }

      // 5. 都无
      source.value = 'empty'
      return { data: [], source: 'empty' as KLineSource }
    } catch (e: any) {
      error.value = String(e)
      return { data: [], source: 'empty' as KLineSource }
    } finally {
      loading.value = false
    }
  }

  return { data, source, loading, error, fetchKLineData }
}

// ============================================================
// 工具函数
// ============================================================

function normalizeBars(records: any[]): KLineBar[] {
  /** 后端 records 格式 → KLineBar[]（标记为 minute）*/
  return records.map(r => ({
    datetime: r.datetime,
    open: Number(r.open),
    high: Number(r.high),
    low: Number(r.low),
    close: Number(r.close),
    volume: Number(r.volume ?? 0),
    bar_type: 'minute' as const,
  })).filter(b => !isNaN(b.open) && !isNaN(b.close))
}

/**
 * sq-0009-round-5 hotfix6：日线 → 30 根 5min 蜡烛
 *
 * 用户方案：1 条 daily 数据拆为 30 根 5min 蜡烛
 * - datetime 从当天 15:30:00 开始（5min 收盘后 30 分钟）每 5 分钟 1 根
 * - OHLC 全部用 daily 值（high=high, low=low, open=open, close=close）
 * - 30 根横向铺开 → 视觉上"占 1 天宽度"（30 × 5min = 2.5 小时 ≈ 当天 1 天）
 * - bar_type='daily' 标记
 *
 * 时间轴布局：
 * |---- 5min 5/8 09:30 ~ 15:00 (66 根) ----|--- daily 5/8 15:30 ~ 17:55 (30 根) ---|
 * |---------------- 5/8 视觉占 1 天宽度 ----------------|
 */
function normalizeDailyAs5min(dailyRecords: any[]): KLineBar[] {
  const result: KLineBar[] = []
  for (const r of dailyRecords) {
    // 后端 daily records 的 datetime 格式：'YYYY-MM-DD'
    const dateStr = (r.datetime || r.date || '').slice(0, 10)
    if (!dateStr || !/^\d{4}-\d{2}-\d{2}$/.test(dateStr)) continue
    const open = Number(r.open)
    const high = Number(r.high)
    const low = Number(r.low)
    const close = Number(r.close)
    if (isNaN(open) || isNaN(close)) continue

    // daily 拆 30 根 5min 蜡烛
    // datetime 从当天 15:30:00 开始，每 5 分钟 1 根，30 根共 2.5 小时
    // 不与 5min 序列冲突（5min 最晚 15:00）
    const baseTime = new Date(`${dateStr}T15:30:00`)
    const volumePerBar = (Number(r.volume ?? 0)) / 30
    for (let i = 0; i < 30; i++) {
      const barTime = new Date(baseTime.getTime() + i * 5 * 60_000)
      const dtStr = barTime.toISOString().slice(0, 19).replace('T', ' ')
      result.push({
        datetime: dtStr,
        open,
        high,
        low,
        close,
        volume: volumePerBar,
        bar_type: 'daily' as const,
      })
    }
  }
  return result
}

/**
 * 合并 5min + 日线补齐：按 datetime 升序去重
 * - 5min 数据保留 bar_type='minute'
 * - daily 数据保留 bar_type='daily'（前端用这个区分渲染）
 */
function mergeBars(bars5: KLineBar[], dailyBars: KLineBar[]): KLineBar[] {
  const seen = new Set<string>()
  const merged: KLineBar[] = []
  // 5min 优先（更密集）
  for (const b of [...bars5].sort((a, b) => a.datetime.localeCompare(b.datetime))) {
    if (!seen.has(b.datetime)) {
      seen.add(b.datetime)
      merged.push(b)
    }
  }
  // 日线补缺：datetime 不冲突时插入（23:55:00 不与 5min 冲突）
  for (const d of dailyBars) {
    if (!seen.has(d.datetime)) {
      seen.add(d.datetime)
      merged.push(d)
    }
  }
  return merged.sort((a, b) => a.datetime.localeCompare(b.datetime))
}

/**
 * 5min K 线 → 15min/30min/60min
 * 算法：
 * - 1 根 5min bar 的时间戳对齐到目标周期的开始
 * - open: 第一根
 * - close: 最后一根
 * - high: 最大
 * - low: 最小
 * - volume: 求和
 */
function resampleBars(bars5: KLineBar[], targetPeriod: KLinePeriod): KLineBar[] {
  const minutes = ({ '5min': 5, '15min': 15, '30min': 30, '60min': 60, 'daily': 1440 } as const)[targetPeriod]
  if (!minutes || bars5.length === 0) return []

  const groups = new Map<string, KLineBar[]>()

  for (const bar of bars5) {
    const dt = new Date(bar.datetime)
    // 对齐到目标周期的开始（取 floor）
    const alignedMs = Math.floor(dt.getTime() / (minutes * 60_000)) * (minutes * 60_000)
    const key = new Date(alignedMs).toISOString()
    if (!groups.has(key)) groups.set(key, [])
    groups.get(key)!.push(bar)
  }

  const result: KLineBar[] = []
  for (const [key, group] of Array.from(groups.entries()).sort()) {
    result.push({
      datetime: key.replace('T', ' ').slice(0, 19),
      open: group[0].open,
      high: Math.max(...group.map(b => b.high)),
      low: Math.min(...group.map(b => b.low)),
      close: group[group.length - 1].close,
      volume: group.reduce((s, b) => s + b.volume, 0),
    })
  }

  return result
}