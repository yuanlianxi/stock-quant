/**
 * Cache Pinia Store（sq-0009-p6）
 */
import { defineStore } from 'pinia'
import { ref } from 'vue'
import { cacheApi, type CoverageResponse, type SyncLogItem, type ScheduleStateItem } from '@/services/cache'

export const useCacheStore = defineStore('cache', () => {
  // === 覆盖率 ===
  const coverage = ref<CoverageResponse | null>(null)
  const coverageLoading = ref(false)
  const coverageError = ref<string | null>(null)

  // === 拉取记录 ===
  const syncLogs = ref<SyncLogItem[]>([])
  const syncLogsTotal = ref(0)
  const syncLogsPage = ref(1)
  const syncLogsLoading = ref(false)
  const syncLogsError = ref<string | null>(null)
  const syncLogsFilter = ref<{ symbol?: string; sync_type?: string; status?: string }>({})

  // === 调度状态 ===
  const schedule = ref<ScheduleStateItem[]>([])
  const scheduleLoading = ref(false)
  const scheduleError = ref<string | null>(null)

  // === 手动拉取 ===
  const triggerLoading = ref(false)
  const lastTriggerResult = ref<any>(null)

  // ============ Actions ============

  async function fetchCoverage() {
    coverageLoading.value = true
    coverageError.value = null
    try {
      coverage.value = await cacheApi.coverage()
    } catch (e: any) {
      coverageError.value = String(e)
    } finally {
      coverageLoading.value = false
    }
  }

  async function fetchSyncLogs(page = 1) {
    syncLogsLoading.value = true
    syncLogsError.value = null
    syncLogsPage.value = page
    try {
      const r = await cacheApi.syncLogs({ ...syncLogsFilter.value, page, page_size: 20 })
      syncLogs.value = r.items
      syncLogsTotal.value = r.total
    } catch (e: any) {
      syncLogsError.value = String(e)
    } finally {
      syncLogsLoading.value = false
    }
  }

  function setSyncLogsFilter(f: { symbol?: string; sync_type?: string; status?: string }) {
    syncLogsFilter.value = f
  }

  async function fetchSchedule() {
    scheduleLoading.value = true
    scheduleError.value = null
    try {
      const r = await cacheApi.schedule()
      schedule.value = r.items
    } catch (e: any) {
      scheduleError.value = String(e)
    } finally {
      scheduleLoading.value = false
    }
  }

  async function toggleScheduleTask(taskName: string, enabled: boolean) {
    try {
      const r = await cacheApi.toggleSchedule(taskName, enabled)
      // 本地更新
      const item = schedule.value.find(s => s.task_name === taskName)
      if (item) item.enabled = enabled ? 1 : 0
      return r
    } catch (e: any) {
      scheduleError.value = String(e)
      throw e
    }
  }

  async function triggerSync(symbol: string, period: string) {
    triggerLoading.value = true
    try {
      const r = await cacheApi.backfill(symbol, period)
      lastTriggerResult.value = r
      // 触发后刷新记录
      await fetchSyncLogs(1)
      return r
    } catch (e: any) {
      lastTriggerResult.value = { error: String(e) }
      throw e
    } finally {
      triggerLoading.value = false
    }
  }

  return {
    // state
    coverage, coverageLoading, coverageError,
    syncLogs, syncLogsTotal, syncLogsPage, syncLogsLoading, syncLogsError, syncLogsFilter,
    schedule, scheduleLoading, scheduleError,
    triggerLoading, lastTriggerResult,
    // actions
    fetchCoverage,
    fetchSyncLogs, setSyncLogsFilter,
    fetchSchedule, toggleScheduleTask,
    triggerSync,
  }
})
