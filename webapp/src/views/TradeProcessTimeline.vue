<script setup lang="ts">
import { ref, watch } from 'vue'
import { useToast } from '@/composables/useToast'
import { sessionApi } from '@/services/session'

interface TradeEvent {
  event_type: string
  bar_time?: string
  signal_price?: number
  is_gap?: number | boolean
  decision_reason?: string
  units_count?: number
  [k: string]: any
}

const props = defineProps<{ sessionId: string }>()
const toast = useToast()

const events = ref<TradeEvent[]>([])
const loading = ref(false)

watch(
  () => props.sessionId,
  async (sid) => { if (sid) await load(sid) },
  { immediate: true }
)

async function load(sid: string) {
  loading.value = true
  try {
    const r = await sessionApi.tradeProcess(sid, { days: 30, limit: 50 })
    const list: TradeEvent[] = r?.events || []
    events.value = list.slice(0, 20)
  } catch (e) {
    toast.push({ kind: 'warn', title: '交易过程加载失败', body: String(e) })
  } finally {
    loading.value = false
  }
}

function evtColor(t: string): string {
  if (t.startsWith('entry_')) return 'var(--accent)'
  if (t.startsWith('add_')) return 'var(--accent)'
  if (t.includes('stop_loss')) return 'var(--sell)'
  if (t.includes('take_profit')) return 'var(--buy)'
  if (t.includes('exit')) return 'var(--warn)'
  if (t === 'gap_skipped' || t === 'gap_filled') return 'var(--warn)'
  return 'var(--muted)'
}

function evtLabel(t: string): string {
  const M: Record<string, string> = {
    entry_long: '做多入场',
    entry_short: '做空入场',
    add_1: '+1/2N 加仓',
    add_2: '+1/2N 加仓',
    add_3: '+1/2N 加仓',
    add_4: '+1/2N 加仓',
    add_filled: '加仓成交',
    entry_filled: '入场成交',
    stop_loss_triggered: '触发止损',
    take_profit_triggered: '触发止盈',
    exit_long: '多头离市',
    exit_short: '空头离市',
    gap_skipped: '跳空跳过',
    gap_filled: '跳空成交'
  }
  return M[t] || t
}

function fmt(n?: number): string {
  return n == null ? '--' : Number(n).toLocaleString(undefined, { maximumFractionDigits: 2 })
}

function isGap(e: TradeEvent): boolean {
  return e.is_gap === 1 || e.is_gap === true
}
</script>

<template>
  <div class="trade-process-panel">
    <h4 class="panel-title">交易过程时间线
      <span v-if="loading" class="loading-tag">⟳</span>
      <span v-else-if="events.length" class="count">{{ events.length }} 条</span>
    </h4>
    <div v-if="events.length === 0 && !loading" class="empty">暂无过程流水</div>
    <div v-else class="timeline">
      <div
        v-for="(e, i) in events"
        :key="i"
        :class="['timeline-item', { gap: isGap(e) }]"
      >
        <div class="t-dot" :style="{ background: evtColor(e.event_type) }" />
        <div class="t-line" v-if="i < events.length - 1" />
        <div class="t-body">
          <div class="t-head">
            <span class="t-type" :style="{ color: evtColor(e.event_type) }">{{ evtLabel(e.event_type) }}</span>
            <span v-if="isGap(e)" class="t-gap">⚠️ 跳空</span>
          </div>
          <div class="t-meta">
            <span class="t-time">{{ e.bar_time?.substring(0, 19) || '--' }}</span>
            <span v-if="e.signal_price != null" class="t-price">@ {{ fmt(e.signal_price) }}</span>
            <span v-if="e.units_count != null" class="t-units">Units: {{ e.units_count }}</span>
          </div>
          <div v-if="e.decision_reason" class="t-reason">{{ e.decision_reason }}</div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.trade-process-panel {
  background: var(--card); border: 1px solid var(--border); border-radius: 6px;
  padding: 10px 12px;
  max-height: 280px; overflow-y: auto;
}
.panel-title { font-size: 12px; color: var(--muted); margin: 0 0 8px 0; display: flex; align-items: center; gap: 6px; }
.loading-tag { color: var(--accent); font-size: 11px; }
.count { color: var(--accent); font-size: 10px; }
.empty { color: var(--muted); font-size: 12px; text-align: center; padding: 16px 0; }

.timeline { display: flex; flex-direction: column; }
.timeline-item {
  position: relative; display: grid; grid-template-columns: 16px 1fr;
  gap: 8px; padding: 6px 0; min-height: 32px;
}
.t-dot {
  width: 10px; height: 10px; border-radius: 50%;
  margin-top: 4px; z-index: 1;
  box-shadow: 0 0 0 2px var(--card);
}
.t-line {
  position: absolute; left: 5px; top: 14px; bottom: -4px;
  width: 1px; background: var(--border);
}
.t-body { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
.t-head { display: flex; align-items: center; gap: 6px; }
.t-type { font-size: 11px; font-weight: 600; }
.t-gap { font-size: 9px; color: var(--warn); background: rgba(245,166,35,0.1); padding: 1px 4px; border-radius: 2px; }
.t-meta { display: flex; gap: 8px; font-size: 10px; color: var(--muted); flex-wrap: wrap; }
.t-time, .t-price, .t-units { font-family: -apple-system, 'SF Mono', monospace; }
.t-reason { font-size: 10px; color: var(--muted); font-style: italic; }
.timeline-item.gap .t-body { background: rgba(245,166,35,0.05); padding: 2px 4px; border-radius: 2px; }
</style>
