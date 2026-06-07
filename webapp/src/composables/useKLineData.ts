/**
 * K 线数据 composable（sq-0009-p6 + 决策 7-C）
 *
 * 策略：库里有就查库，没有就 resample 5min 缓存降级
 *
 * 用法：
 *   const { data, loading, source } = await fetchKLineData('AG', '15min')
 *   // source: 'cache' | 'resample' | 'empty'
 */
import { ref } from 'vue'
import { useApi } from '@/composables/useApi'

export type KLineSource = 'cache' | 'resample' | 'empty'
export type KLinePeriod = '5min' | '15min' | '30min' | '60min'

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
   * 拉取 K 线（带降级）
   * @param symbol 品种
   * @param period 目标周期
   * @param days 拉多少天（默认 7）
   */
  async function fetchKLineData(symbol: string, period: KLinePeriod, days = 7) {
    loading.value = true
    error.value = null
    data.value = []
    source.value = 'empty'

    try {
      // 1. 先查目标周期
      const api = useApi()
      const r1 = await api.get<any>(`/minute/${symbol}`, { period, days })
      if (r1?.records?.length > 0) {
        data.value = normalizeBars(r1.records)
        source.value = 'cache'
        return { data: data.value, source: source.value }
      }

      // 2. 降级：resample 5min
      if (period !== '5min') {
        const r2 = await api.get<any>(`/minute/${symbol}`, { period: '5min', days })
        if (r2?.records?.length > 0) {
          const bars5 = normalizeBars(r2.records)
          data.value = resampleBars(bars5, period)
          source.value = 'resample'
          return { data: data.value, source: source.value }
        }
      }

      // 3. 都无
      source.value = 'empty'
      return { data: [], source: 'empty' }
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
  const minutes = ({ '5min': 5, '15min': 15, '30min': 30, '60min': 60 } as const)[targetPeriod]
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
