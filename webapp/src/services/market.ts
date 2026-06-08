import { useApi } from '@/composables/useApi'
export const marketApi = {
  signalsAll:        ()   => useApi().get<any[]>('/signals/all'),
  signalsBySymbol:   (s: string) => useApi().get<any>(`/signals/${s}`),
  minute:            (s: string, p: any) => useApi().get<any>(`/minute/${s}`, p),
  daily:             (s: string, p: any) => useApi().get<any>(`/daily/${s}`, p),
  dailySync:        (symbol: string = 'all') => useApi().post<any>(`/daily/sync?symbol=${symbol}`),
  minuteSync:        (body: any) => useApi().post<any>('/minute/sync', body),
  cacheStatus:       ()   => useApi().get<any>('/cache/status'),
  turtleSignalsActive: () => useApi().get<any[]>('/turtle/signals/active'),
  turtleSignalsAlerts: (sinceMinutes = 30) => useApi().get<any[]>('/turtle/signals/alerts', { since_minutes: sinceMinutes }),
  turtleSignalsBySymbol: (s: string, days = 7) => useApi().get<any[]>(`/turtle/signals/${s}`, { days }),
  mainContract:      (s: string) => useApi().get<any>(`/main-contract/${s}`)
}
