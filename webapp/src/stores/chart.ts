import { defineStore } from 'pinia'
import { ref } from 'vue'

export type Period = '5min' | '15min' | '30min' | '60min'

export const useChartStore = defineStore('chart', () => {
  const curPeriod = ref<Period>('15min')
  const curDate = ref<string>('')
  const curDays = ref<number>(0)
  const curIsDaily = ref<boolean>(false)

  function setPeriod(p: Period) { curPeriod.value = p }
  function setDate(d: string) { curDate.value = d }
  function setDays(d: number, isDaily = false) {
    curDays.value = d
    curIsDaily.value = isDaily
  }

  return { curPeriod, curDate, curDays, curIsDaily, setPeriod, setDate, setDays }
})
