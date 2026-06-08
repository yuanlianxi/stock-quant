<!--
  KLineChart.vue（v1.7+sq-0009-round-2 commit 1）
  lightweight-charts 4.1 封装：接收 KLineBar[] 渲染 K 线
-->
<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'
import { createChart, CandlestickData, UTCTimestamp } from 'lightweight-charts'

export interface KLineBar {
  datetime: string          // 'YYYY-MM-DD HH:MM:SS'
  open: number
  high: number
  low: number
  close: number
  volume: number
}

const props = withDefaults(defineProps<{
  data: KLineBar[]
  height?: number
}>(), {
  height: 400,
})

const chartContainer = ref<HTMLDivElement | null>(null)
// eslint-disable-next-line @typescript-eslint/no-explicit-any
let chart: any = null
// eslint-disable-next-line @typescript-eslint/no-explicit-any
let series: any = null

function initChart() {
  if (!chartContainer.value) return
  chart = createChart(chartContainer.value, {
    width: chartContainer.value.clientWidth,
    height: props.height,
    layout: {
      background: { color: 'transparent' },
      textColor: '#d1d5db',
    },
    grid: {
      vertLines: { color: 'rgba(70, 70, 70, 0.3)' },
      horzLines: { color: 'rgba(70, 70, 70, 0.3)' },
    },
    timeScale: {
      timeVisible: true,
      secondsVisible: false,
      borderColor: 'rgba(70, 70, 70, 0.5)',
    },
    rightPriceScale: {
      borderColor: 'rgba(70, 70, 70, 0.5)',
    },
    crosshair: {
      mode: 1,
    },
  })

  series = chart.addCandlestickSeries({
    upColor: '#22c55e',
    downColor: '#ef4444',
    borderUpColor: '#22c55e',
    borderDownColor: '#ef4444',
    wickUpColor: '#22c55e',
    wickDownColor: '#ef4444',
  })
}

function updateData() {
  if (!series) return
  const candles: CandlestickData[] = props.data.map(bar => ({
    time: toUTCTimestamp(bar.datetime) as UTCTimestamp,
    open: bar.open,
    high: bar.high,
    low: bar.low,
    close: bar.close,
  }))
  series.setData(candles)
  if (chart) chart.timeScale().fitContent()
}

/** 'YYYY-MM-DD HH:MM:SS' → UTC seconds */
function toUTCTimestamp(dt: string): number {
  const iso = dt.replace(' ', 'T')
  return Math.floor(new Date(iso).getTime() / 1000)
}

onMounted(async () => {
  await nextTick()
  initChart()
  updateData()
  // 响应式宽度
  if (chartContainer.value) {
    const ro = new ResizeObserver(entries => {
      if (chart && entries[0]) {
        chart.applyOptions({ width: entries[0].contentRect.width })
      }
    })
    ro.observe(chartContainer.value)
  }
})

watch(() => props.data, () => updateData(), { deep: true })

onBeforeUnmount(() => {
  if (chart) {
    chart.remove()
    chart = null
    series = null
  }
})
</script>

<template>
  <div ref="chartContainer" class="kline-chart" :style="{ height: height + 'px' }">
    <div v-if="data.length === 0" class="empty">暂无 K 线数据</div>
  </div>
</template>

<style scoped>
.kline-chart {
  position: relative;
  width: 100%;
  min-height: 200px;
  background: var(--card);
  border-radius: 4px;
  border: 1px solid var(--border);
}
.empty {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: var(--muted);
}
</style>
