import { useApi } from '@/composables/useApi'
export const backtestApi = {
  run: (body: any) => useApi().post<any>('/backtest/run', body),
  list: (limit = 20) => useApi().get<any>('/backtest/runs', { limit }),
  get: (runId: string) => useApi().get<any>(`/backtest/runs/${runId}`),
  trades: (runId: string) => useApi().get<any>(`/backtest/runs/${runId}/trades`)
}
