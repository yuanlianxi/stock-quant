import { useApi } from '@/composables/useApi'
export const sessionApi = {
  list: (p: any) => useApi().get<any>('/sessions', p),
  open: (body: any) => useApi().post<any>('/session', body),
  lines: (sid: string) => useApi().get<any>(`/session/${sid}/lines`),
  events: (sid: string, p: any) => useApi().get<any>(`/session/${sid}/events`, p),
  tradeProcess: (sid: string, p: any) => useApi().get<any>(`/session/${sid}/trade-process`, p),
  addOrder: (sid: string, body: any) => useApi().post<any>(`/session/${sid}/orders`, body),
  reduceOrder: (sid: string, body: any) => useApi().post<any>(`/session/${sid}/orders/reduce`, body),
  close: (sid: string, body: any) => useApi().post<any>(`/session/${sid}/close`, body),
  setLine: (sid: string, lineType: string, body: any) => useApi().put<any>(`/session/${sid}/line/${lineType}`, body)
}
