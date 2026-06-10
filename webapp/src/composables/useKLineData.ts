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

        // 2. mixDaily：当 period='5min' + days>10，额外拉日线补 5min 窗口外缺失区间
        // 关键：daily days 必须是用户选范围的 2x（akshare 5min 窗口 ~10 天，5min 缓存可能少于此）
        // 比如 5min 缓存 5/18 起，days=180 时需要 daily 覆盖 5/18 之前 → 至少 180+ 天
        if (mixDaily && period === '5min' && days > 10) {
          try {
            const dailyDays = Math.max(days * 2, days + 30)
            const dailyResp = await api.get<any>(`/daily/${symbol}`, { days: dailyDays })
            if (dailyResp?.records?.length > 0) {
              const dailyBars = normalizeDailyAs5min(dailyResp.records)
              bars = mergeBars(bars, dailyBars)
              source.value = 'mix'
              data.value = bars
              return { data: data.value, source: source.value }
            }
          } catch {
            // 拉日线失败时不影响 5min 数据
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
  /** 后端 records 格式 → KLineBar[] */
  return records.map(r => ({
    datetime: r.datetime,
    open: Number(r.open),
    high: Number(r.high),
    low: Number(r.low),
    close: Number(r.close),
    volume: Number(r.volume ?? 0),
  })).filter(b => !isNaN(b.open) && !isNaN(b.close))
}

/**
 * sq-0009-round-5 commit 12：日线 → 5min 时间占位
 *
 * 日线 datetime 用当天最后 5min 时段（23:55:00），让 chart 在时间轴上
 * 自然占更宽时长（1 天 ≈ 288 × 5min 宽度）
 */
function normalizeDailyAs5min(dailyRecords: any[]): KLineBar[] {
  return dailyRecords
    .map(r => {
      // 后端 daily records 的 datetime 格式：'YYYY-MM-DD'
      const dateStr = (r.datetime || r.date || '').slice(0, 10)
      if (!dateStr || !/^\d{4}-\d{2}-\d{2}$/.test(dateStr)) return null
      return {
        datetime: `${dateStr} 23:55:00`,
        open: Number(r.open),
        high: Number(r.high),
        low: Number(r.low),
        close: Number(r.close),
        volume: Number(r.volume ?? 0),
      }
    })
    .filter((b): b is KLineBar => b !== null && !isNaN(b.open) && !isNaN(b.close))
}

/**
 * 合并 5min + 日线补齐：按 datetime 升序去重
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