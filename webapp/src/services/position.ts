import { useApi } from '@/composables/useApi'
export const positionApi = {
  bySymbol: (s: string) => useApi().get<any>(`/position/${s}`),
  add: (s: string, body: any) => useApi().post<any>(`/position/${s}/add`, body)
}
