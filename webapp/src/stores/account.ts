import { defineStore } from 'pinia'
import { ref } from 'vue'

export interface AccountSummary {
  balance?: number
  available?: number
  margin_used?: number
  position_value?: number
  unrealized_pnl?: number
  realized_pnl?: number
  open_sessions_count?: number
  open_units_count?: number
  recent_trades_count?: number
  [k: string]: any
}

export const useAccountStore = defineStore('account', () => {
  const current = ref<string>('sim_default')
  const summary = ref<AccountSummary | null>(null)

  function setCurrent(a: string) { current.value = a; summary.value = null }
  function setSummary(s: AccountSummary) { summary.value = s }

  return { current, summary, setCurrent, setSummary }
})
