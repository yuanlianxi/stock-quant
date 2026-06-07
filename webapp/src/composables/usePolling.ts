import { ref, onUnmounted, type Ref } from 'vue'

export interface UsePollingOptions {
  intervalMs: number
  immediate?: boolean
  onError?: (e: Error) => void
}

export function usePolling<T>(
  fetcher: () => Promise<T>,
  opts: UsePollingOptions
): { data: Ref<T | null>; loading: Ref<boolean>; error: Ref<Error | null>; refresh: () => Promise<void> } {
  const data = ref<T | null>(null) as Ref<T | null>
  const loading = ref(false)
  const error = ref<Error | null>(null)
  let timer: ReturnType<typeof setInterval> | null = null

  const refresh = async () => {
    if (loading.value) return
    loading.value = true
    try {
      data.value = await fetcher()
      error.value = null
    } catch (e) {
      error.value = e instanceof Error ? e : new Error(String(e))
      opts.onError?.(error.value)
    } finally {
      loading.value = false
    }
  }

  if (opts.immediate !== false) refresh()
  timer = setInterval(refresh, opts.intervalMs)

  onUnmounted(() => { if (timer) clearInterval(timer) })

  return { data, loading, error, refresh }
}
