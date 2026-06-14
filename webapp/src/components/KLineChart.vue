<!--
  KLineChart.vue（v1.7+sq-0009-round-2 commit 1）
  lightweight-charts 4.1 封装：接收 KLineBar[] 渲染 K 线
  v0.18.15 data-model Phase 2 hotfix：补 0005 原始需求 §1 — K 线图叠加信号 markers
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

export interface TurtleSignal {
  signal_type: string       // 'entry_long' | 'entry_short' | 'exit_long' | 'exit_short' | 'add_unit'
  trigger_price?: number
  reference_price?: number
  bar_time?: string         // 'YYYY-MM-DD HH:MM:SS'（与 KLineBar.datetime 对齐）
  basis_55d?: number
  reference_n?: number
  [k: string]: any
}

const props = withDefaults(defineProps<{
  data: KLineBar[]
  signals?: TurtleSignal[]
  height?: number
}>(), {
  height: 400,
  signals: () => [] as TurtleSignal[],
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
  // v0.18.12-hotfix2: 空数据守卫（fetch 还没返回时 props.data=[]）
  // setVisibleLogicalRange({ from: 0, to: -1 }) 会触发 lightweight-charts 断言
  if (chart && props.data.length > 0) {
    // 默认只显示最后 200 根（避免 candle 太密不可见）
    // 用户可拖动 / 滚轮缩放看更早数据
    const totalBars = props.data.length
    const showBars = Math.min(totalBars, 200)
    chart.timeScale().setVisibleLogicalRange({
      from: Math.max(0, totalBars - showBars),
      to: totalBars - 1,
    })
  }
}

/** 'YYYY-MM-DD HH:MM:SS' → UTC seconds */
function toUTCTimestamp(dt: string): number {
  const iso = dt.replace(' ', 'T')
  return Math.floor(new Date(iso).getTime() / 1000)
}

/** 信号 → lightweight-charts marker 颜色 / 形状 / 位置 映射（0005 §1 5 种信号） */
function markerStyleFor(signalType: string): {
  color: string
  shape: 'arrowUp' | 'arrowDown' | 'circle' | 'square'
  position: 'aboveBar' | 'belowBar' | 'inBar'
  text: string
} {
  switch (signalType) {
    case 'entry_long':  return { color: '#22c55e', shape: 'arrowUp',   position: 'belowBar', text: '做多' }
    case 'entry_short': return { color: '#ef4444', shape: 'arrowDown', position: 'aboveBar', text: '做空' }
    case 'exit_long':   return { color: '#f97316', shape: 'arrowDown', position: 'aboveBar', text: '平多' }
    case 'exit_short':  return { color: '#f97316', shape: 'arrowUp',   position: 'belowBar', text: '平空' }
    case 'add_unit':    return { color: '#3b82f6', shape: 'circle',    position: 'inBar',    text: '加' }
    default:            return { color: '#6b7280', shape: 'circle',    position: 'inBar',    text: '?' }
  }
}

/** 把 props.signals 转换成 lightweight-charts markers 并 setMarkers */
function updateMarkers() {
  if (!series) return
  if (!props.signals || props.signals.length === 0) {
    // 清空 markers
    series.setMarkers([])
    return
  }

  // 过滤有 bar_time 的 signal + 转 lightweight-charts 格式
  const markers = props.signals
    .filter(s => s.bar_time && s.signal_type)
    .map(s => {
      const style = markerStyleFor(s.signal_type)
      return {
        // lightweight-charts v4 接受 string 格式 'YYYY-MM-DD HH:MM:SS'，内部解析
        time: s.bar_time as any,
        position: style.position,
        color: style.color,
        shape: style.shape,
        text: style.text
      }
    })
    .sort((a, b) => {
      // 按时间排序（lightweight-charts 要求 markers 按时间升序）
      const ta = typeof a.time === 'string' ? new Date(a.time).getTime() : a.time
      const tb = typeof b.time === 'string' ? new Date(b.time).getTime() : b.time
      return ta - tb
    })

  try {
    series.setMarkers(markers as any)
  } catch (e) {
    console.warn('[KLineChart] setMarkers 失败（可能是 bar_time 与 K 线时间不匹配）:', e)
  }
}

onMounted(async () => {
  await nextTick()
  initChart()
  updateData()
  updateMarkers()  // v0.18.15: 初始加载信号 markers
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
watch(() => props.signals, () => updateMarkers(), { deep: true })

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
  <div v-if="data.length > 0" class="debug-info">
    {{ data.length }} bars | {{ data[0]?.datetime?.slice(0, 10) }} ~ {{ data[data.length-1]?.datetime?.slice(0, 10) }}
    <span class="hint-tip">｜ 💡 显示最近 200 根（拖动 / 滚轮缩放看更多）</span>
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
.debug-info {
  font-size: 10px;
  color: var(--muted);
  padding: 4px 6px;
  font-family: monospace;
}
</style>
