import { defineStore } from 'pinia'
import { ref } from 'vue'

export interface Strategy {
  strategy_id: string
  name?: string
  version?: string
  type?: string
  is_active?: boolean
  [k: string]: any
}

export const useStrategyStore = defineStore('strategy', () => {
  const list = ref<Strategy[]>([])
  const current = ref<Strategy | null>(null)

  function setList(l: Strategy[]) { list.value = l }
  function setCurrent(s: Strategy | null) { current.value = s }

  return { list, current, setList, setCurrent }
})
