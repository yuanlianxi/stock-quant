/**
 * Cache API 客户端（sq-0009-p6）
 * 对应后端 api/routers/cache.py 的 7 端点
 */
import { useApi } from '@/composables/useApi'

export interface CoverageCell {
  latest: string | null
  status: 'fresh' | 'stale' | 'missing'
}

export interface CoverageResponse {
  symbols: string[]
  periods: string[]
  matrix: Record<string, Record<string, CoverageCell>>
  summary: {
    total_symbols: number
    total_cells: number
    fresh_cells: number
    stale_cells: number
    missing_cells: number
  }
}

export interface SyncLogItem {
  id: number
  symbol: string
  period: string
  sync_type: 'manual' | 'backfill' | 'scheduled'
  status: 'running' | 'success' | 'failed' | 'partial'
  start_at: string
  end_at: string | null
  rows_existing: number
  rows_new: number
  rows_total: number
  error_message: string | null
  trigger_source: string | null
  created_at: string
}

export interface SyncLogListResponse {
  total: number
  page: number
  page_size: number
  items: SyncLogItem[]
}

export interface ScheduleStateItem {
  task_name: string
  last_run_at: string | null
  next_run_at: string | null
  last_status: string | null
  run_count: number
  fail_count: number
  enabled: number
  updated_at: string | null
}

export const cacheApi = {
  /** 33 品种 × 5 周期覆盖率矩阵 */
  coverage:           () => useApi().get<CoverageResponse>('/cache/coverage'),

  /** 拉取记录分页 */
  syncLogs:           (params?: { symbol?: string; sync_type?: string; status?: string; page?: number; page_size?: number }) =>
                        useApi().get<SyncLogListResponse>('/cache/sync/logs', params),

  /** 单条详情 */
  syncLogDetail:      (logId: number) => useApi().get<SyncLogItem>(`/cache/sync/logs/${logId}`),

  /** 调度状态列表 */
  schedule:           () => useApi().get<{ items: ScheduleStateItem[] }>('/cache/schedule'),

  /** 启停调度任务 */
  toggleSchedule:     (taskName: string, enabled: boolean) =>
                        useApi().post<{ task_name: string; enabled: boolean; updated: boolean }>(
                          `/cache/schedule/${taskName}/toggle?enabled=${enabled}`
                        ),

  /** 回填历史 */
  backfill:           (symbol: string, period: string, years?: number, days?: number) => {
                        const params = new URLSearchParams({ symbol, period })
                        if (years != null) params.set('years', String(years))
                        if (days != null) params.set('days', String(days))
                        return useApi().post<any>(`/cache/backfill?${params.toString()}`)
                      },

  /** sq-0008 旧端点 */
  status:             () => useApi().get<any>('/cache/status'),
}
