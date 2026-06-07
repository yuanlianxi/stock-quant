import { defineStore } from 'pinia'
import { ref } from 'vue'

export interface MarketData {
  symbol: string
  name?: string
  contract_code?: string
  current_price?: number
  change?: number
  change_pct?: number
  atr?: number
  high_55?: number
  low_55?: number
  date?: string
  direction?: 'long' | 'short' | ''
  [k: string]: any
}

export const useMarketStore = defineStore('market', () => {
  const curEx = ref<'ALL' | 'SHFE' | 'DCE' | 'CZCE' | 'CFFEX'>('ALL')
  const curSym = ref<string | null>(null)
  const marketData = ref<Record<string, MarketData>>({})
  const activeSignals = ref<Record<string, any>>({})
  const lastAlertTime = ref<number | null>(null)

  function setEx(ex: typeof curEx.value) { curEx.value = ex }
  function setSym(sym: string | null) { curSym.value = sym }
  function setMarketData(sym: string, data: Partial<MarketData>) {
    marketData.value[sym] = { ...marketData.value[sym], ...data } as MarketData
  }
  function setActiveSignals(sigs: Record<string, any>) { activeSignals.value = sigs }
  function setLastAlertTime(t: number) {
    if (!lastAlertTime.value || t > lastAlertTime.value) lastAlertTime.value = t
  }

  return { curEx, curSym, marketData, activeSignals, lastAlertTime, setEx, setSym, setMarketData, setActiveSignals, setLastAlertTime }
})
