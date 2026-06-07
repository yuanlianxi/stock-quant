import { defineStore } from 'pinia'
import { ref } from 'vue'

export interface OpenSession {
  session_id: string
  symbol: string
  direction: 'long' | 'short'
  status: string
  current_units: number
  total_units: number
  [k: string]: any
}

export const useSessionStore = defineStore('session', () => {
  const bySymbol = ref<Record<string, OpenSession[]>>({})

  function setBySymbol(map: Record<string, OpenSession[]>) { bySymbol.value = map }
  function add(s: OpenSession) {
    if (!bySymbol.value[s.symbol]) bySymbol.value[s.symbol] = []
    bySymbol.value[s.symbol].push(s)
  }
  function getCurrent(sym: string) {
    const arr = bySymbol.value[sym]
    return arr && arr.length > 0 ? arr[0] : null
  }

  return { bySymbol, setBySymbol, add, getCurrent }
})
