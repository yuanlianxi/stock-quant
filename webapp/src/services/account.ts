import { useApi } from '@/composables/useApi'
export const accountApi = {
  overview: (accountId: string, days = 30) => useApi().get<any>('/account/overview', { account_id: accountId, days }),
  positions: (accountId: string) => useApi().get<any>(`/account/${accountId}/positions`),
  units: (accountId: string) => useApi().get<any>(`/account/${accountId}/units`),
  sessions: (accountId: string, limit = 50) => useApi().get<any>(`/account/${accountId}/sessions`, { limit }),
  trades: (accountId: string, p: any) => useApi().get<any>(`/account/${accountId}/trades`, p)
}
