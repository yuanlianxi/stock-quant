<script setup lang="ts">
import { computed } from 'vue'

interface PriceLines {
  entry?: number
  stop_loss?: number
  take_profit?: number
  warning?: number
}

const props = withDefaults(defineProps<{
  lines: PriceLines
  currentPrice?: number
}>(), {
  currentPrice: 0
})

interface Segment {
  key: 'stop_loss' | 'entry' | 'warning' | 'take_profit'
  label: string
  price: number
  color: string
  bgClass: string
}

const segments = computed<Segment[]>(() => {
  const out: Segment[] = []
  if (props.lines.stop_loss != null) {
    out.push({ key: 'stop_loss', label: '止损', price: props.lines.stop_loss, color: 'var(--sell)', bgClass: 'line-stop' })
  }
  if (props.lines.entry != null) {
    out.push({ key: 'entry', label: '入场', price: props.lines.entry, color: 'var(--accent)', bgClass: 'line-entry' })
  }
  if (props.lines.warning != null) {
    out.push({ key: 'warning', label: '预警', price: props.lines.warning, color: 'var(--warn)', bgClass: 'line-warn' })
  }
  if (props.lines.take_profit != null) {
    out.push({ key: 'take_profit', label: '止盈', price: props.lines.take_profit, color: 'var(--buy)', bgClass: 'line-tp' })
  }
  return out
})

// 计算每个 segment 在整个价格区间的左 % 位置
const minPrice = computed(() => {
  if (segments.value.length === 0) return 0
  return Math.min(...segments.value.map(s => s.price), props.currentPrice || Infinity)
})
const maxPrice = computed(() => {
  if (segments.value.length === 0) return 1
  return Math.max(...segments.value.map(s => s.price), props.currentPrice || -Infinity)
})
const range = computed(() => {
  const r = maxPrice.value - minPrice.value
  return r > 0 ? r : 1
})

function pct(price: number): number {
  return ((price - minPrice.value) / range.value) * 100
}

const currentPct = computed(() => {
  if (!props.currentPrice) return null
  return pct(props.currentPrice)
})

function fmt(n?: number): string {
  return n == null ? '--' : Number(n).toLocaleString(undefined, { maximumFractionDigits: 2 })
}
</script>

<template>
  <div v-if="segments.length > 0" class="price-line-bar">
    <h5 class="bar-title">价格线</h5>
    <div class="bar-track">
      <!-- segment 段 -->
      <div
        v-for="seg in segments"
        :key="seg.key"
        :class="['bar-seg', seg.bgClass]"
        :style="{
          left: pct(seg.price) + '%',
          background: seg.color
        }"
        :title="`${seg.label} ${fmt(seg.price)}`"
      >
        <div class="seg-label">{{ seg.label }}</div>
        <div class="seg-price">{{ fmt(seg.price) }}</div>
      </div>
      <!-- 当前价标记 -->
      <div
        v-if="currentPct != null"
        class="current-marker"
        :style="{ left: currentPct + '%' }"
      >
        <div class="marker-arrow">▼</div>
        <div class="marker-price">{{ fmt(currentPrice) }}</div>
      </div>
    </div>
    <!-- 标尺 -->
    <div class="bar-ruler">
      <span>{{ fmt(minPrice) }}</span>
      <span>{{ fmt(maxPrice) }}</span>
    </div>
  </div>
</template>

<style scoped>
.price-line-bar {
  margin-top: 12px; padding: 8px 0 0 0;
  border-top: 1px dashed var(--border);
}
.bar-title { font-size: 11px; color: var(--muted); margin: 0 0 6px 0; }

.bar-track {
  position: relative; height: 38px;
  background: var(--bg); border-radius: 4px;
  border: 1px solid var(--border);
}
.bar-seg {
  position: absolute; top: 4px; bottom: 4px;
  min-width: 28px; border-radius: 3px;
  transform: translateX(-50%);
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  color: #fff; font-size: 9px; padding: 2px 4px;
  white-space: nowrap;
  box-shadow: 0 1px 3px rgba(0,0,0,0.3);
}
.seg-label { font-weight: 600; }
.seg-price { font-size: 9px; opacity: 0.9; }

.line-stop { background: var(--sell) !important; }
.line-entry { background: var(--accent) !important; }
.line-warn { background: var(--warn) !important; }
.line-tp { background: var(--buy) !important; }

.current-marker {
  position: absolute; top: -2px; bottom: -2px;
  transform: translateX(-50%);
  display: flex; flex-direction: column; align-items: center;
  pointer-events: none;
}
.marker-arrow {
  color: var(--text); font-size: 12px; line-height: 1;
  text-shadow: 0 0 2px rgba(0,0,0,0.6);
}
.marker-price {
  background: var(--text); color: var(--bg);
  font-size: 9px; padding: 1px 4px; border-radius: 2px;
  margin-top: 2px; font-weight: 600;
  white-space: nowrap;
}

.bar-ruler {
  display: flex; justify-content: space-between;
  margin-top: 4px; font-size: 10px; color: var(--muted);
  font-family: -apple-system, 'SF Mono', monospace;
}
</style>
