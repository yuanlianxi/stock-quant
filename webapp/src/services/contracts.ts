import { useApi } from '@/composables/useApi'
export const contractsApi = {
  list: (symbol: string) => useApi().get<any>(`/contracts/${symbol}`),
  quote: (contractCode: string) => useApi().get<any>(`/quotes/${encodeURIComponent(contractCode)}`)
}
