<script setup lang="ts">
import { computed } from 'vue'

interface TurtleSignal {
  signal_type: string
  trigger_price?: number
  reference_price?: number
  bar_time?: string
  basis_55d?: number
  reference_n?: number
  [k: string]: any
}

const props = withDefaults(defineProps<{
  signals: TurtleSignal[]
  max?: number
}>(), {
  max: 20
})

const list = computed<TurtleSignal[]>(() => (props.signals || []).slice(0, props.max))

function dotColor(s: TurtleSignal): string {
  if (s.signal_type === 'entry_long') return 'var(--buy)'
  if (s.signal_type === 'entry_short') return 'var(--sell)'
  if (s.signal_type === 'stop_loss' || s.signal_type.includes('stop')) return 'var(--warn)'
  if (s.signal_type === 'add_unit' || s.signal_type.startsWith('add_')) return 'var(--accent)'
  if (s.signal_type.includes('exit')) return 'var(--warn)'
  return 'var(--muted)'
}

function dotClass(s: TurtleSignal): string {
  return s.signal_type.replace(/_/g, '-')
}

function evtLabel(t: string): string {
  const M: Record<string, string> = {
    entry_long: '做多入场',
    entry_short: '做空入场',
    stop_loss: '止损',
    add_unit: '加仓',
    add_1: '+1/2N', add_2: '+1/2N', add_3: '+1/2N', add_4: '+1/2N',
    exit_long: '多头离市',
    exit_short: '空头离市'
  }
  return M[t] || t
}

function fmt(n?: number): string {
  return n == null ? '--' : Number(n).toLocaleString(undefined, { maximumFractionDigits: 2 })
}
</script>

<template>
  <div class="sig-timeline">
    <div v-if="list.length === 0" class="empty">暂无信号记录</div>
    <div v-else class="tl-list">
      <div v-for="(s, i) in list" :key="i" class="tl-row">
        <span :class="['tl-dot', dotClass(s)]" :style="{ background: dotColor(s) }" />
        <div class="tl-info">
          <div class="tl-type" :style="{ color: dotColor(s) }">{{ evtLabel(s.signal_type) }}</div>
          <div class="tl-detail">
            触发 {{ fmt(s.trigger_price) }} · 参考 {{ fmt(s.reference_price) }}
            <span v-if="s.reference_n != null">· N={{ Number(s.reference_n).toFixed(1) }}</span>
          </div>
          <div class="tl-time">{{ s.bar_time || '--' }}</div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.sig-timeline { font-size: 12px; }
.empty { color: var(--muted); font-size: 12px; text-align: center; padding: 16px 0; }

.tl-list { display: flex; flex-direction: column; gap: 8px; max-height: 240px; overflow-y: auto; }
.tl-row {
  display: flex; gap: 8px; padding: 4px 0;
  border-bottom: 1px solid var(--border);
}
.tl-row:last-child { border-bottom: none; }

.tl-dot {
  width: 8px; height: 8px; border-radius: 50%;
  margin-top: 6px; flex-shrink: 0;
  box-shadow: 0 0 0 2px var(--card);
}
.tl-info { flex: 1; min-width: 0; }
.tl-type { font-size: 11px; font-weight: 600; }
.tl-detail { font-size: 10px; color: var(--muted); font-family: -apple-system, 'SF Mono', monospace; margin: 2px 0; }
.tl-time { font-size: 9px; color: var(--muted); }
</style>
