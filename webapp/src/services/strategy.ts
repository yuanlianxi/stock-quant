import { useApi } from '@/composables/useApi'
export const strategyApi = {
  list: (includeInactive = false) => useApi().get<{ strategies: any[]; count: number }>('/strategies', { include_inactive: includeInactive }),
  get: (id: string) => useApi().get<any>(`/strategies/${id}`),
  paramHistory: (id: string, limit = 20) => useApi().get<any[]>(`/strategies/${id}/param-history`, { limit }),
  signals: (id: string, p: any) => useApi().get<any[]>(`/strategies/${id}/signals`, p),
  events: (id: string, p: any) => useApi().get<any[]>(`/strategies/${id}/events`, p)
}
