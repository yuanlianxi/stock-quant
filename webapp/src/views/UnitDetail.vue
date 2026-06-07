<script setup lang="ts">
import { ref, watch } from 'vue'
import { useToast } from '@/composables/useToast'
import { sessionApi } from '@/services/session'

interface UnitEvent {
  event_type: string
  signal_price?: number
  exec_status?: string
  exec_hand_count?: number
  is_gap?: number | boolean
  bar_time?: string
  [k: string]: any
}

const props = defineProps<{ sessionId: string }>()
const toast = useToast()

const units = ref<(UnitEvent | null)[]>([null, null, null, null])
const loading = ref(false)

watch(
  () => props.sessionId,
  async (sid) => { if (sid) await load(sid) },
  { immediate: true }
)

async function load(sid: string) {
  loading.value = true
  try {
    // entry_filled (unit 1) + add_filled (unit 2-4) 按时间序填 1-4
    const [r1, r2] = await Promise.all([
      sessionApi.tradeProcess(sid, { event_type: 'entry_filled', days: 30, limit: 5 }),
      sessionApi.tradeProcess(sid, { event_type: 'add_filled', days: 30, limit: 20 })
    ])
    const entryEvts: UnitEvent[] = r1?.events || []
    const addEvts: UnitEvent[] = r2?.events || []
    const allFilled = [...entryEvts, ...addEvts]
    const next: (UnitEvent | null)[] = [null, null, null, null]
    for (let i = 0; i < 4; i++) {
      next[i] = allFilled[i] || null
    }
    units.value = next
  } catch (e) {
    toast.push({ kind: 'warn', title: 'Unit 详情加载失败', body: String(e) })
  } finally {
    loading.value = false
  }
}

function isGap(u: UnitEvent | null): boolean {
  if (!u) return false
  return u.is_gap === 1 || u.is_gap === true
}

function fmt(n?: number): string {
  return n == null ? '--' : Number(n).toLocaleString(undefined, { maximumFractionDigits: 2 })
}
</script>

<template>
  <div class="unit-detail-panel">
    <h4 class="panel-title">4 Unit 明细
      <span v-if="loading" class="loading-tag">⟳</span>
    </h4>
    <div class="unit-grid">
      <div
        v-for="(u, i) in units"
        :key="i"
        :class="['unit-card', { gap: isGap(u), empty: !u }]"
      >
        <h5>Unit {{ i + 1 }}
          <span v-if="isGap(u)" class="gap-icon" title="跳空跳过">⚠️</span>
        </h5>
        <template v-if="u">
          <div class="unit-row">
            <span class="lbl">open</span>
            <span class="val">{{ fmt(u.signal_price) }}</span>
          </div>
          <div class="unit-row">
            <span class="lbl">状态</span>
            <span class="val">{{ u.exec_status || '--' }}</span>
          </div>
          <div class="unit-row">
            <span class="lbl">hand</span>
            <span class="val">{{ u.exec_hand_count ?? '--' }}</span>
          </div>
          <div v-if="u.bar_time" class="unit-row">
            <span class="lbl">时间</span>
            <span class="val time">{{ u.bar_time.substring(0, 16) }}</span>
          </div>
          <div v-if="isGap(u)" class="gap-badge">跳空跳过 ⚠️</div>
        </template>
        <template v-else>
          <div class="unit-row empty-row">未建仓</div>
        </template>
      </div>
    </div>
  </div>
</template>

<style scoped>
.unit-detail-panel {
  background: var(--card); border: 1px solid var(--border); border-radius: 6px;
  padding: 10px 12px;
}
.panel-title { font-size: 12px; color: var(--muted); margin: 0 0 8px 0; display: flex; align-items: center; gap: 6px; }
.loading-tag { color: var(--accent); font-size: 11px; }

.unit-grid {
  display: grid; grid-template-columns: repeat(4, 1fr); gap: 6px;
}
.unit-card {
  background: var(--bg); border: 1px solid var(--border); border-radius: 4px;
  padding: 8px 10px; min-height: 96px;
}
.unit-card.gap { border-color: var(--warn); }
.unit-card.empty { opacity: 0.55; }
.unit-card h5 {
  font-size: 11px; color: var(--accent); margin: 0 0 6px 0;
  display: flex; align-items: center; gap: 4px;
}
.gap-icon { color: var(--warn); }
.unit-row { display: flex; justify-content: space-between; font-size: 11px; padding: 2px 0; }
.unit-row .lbl { color: var(--muted); }
.unit-row .val { color: var(--text); font-weight: 600; font-family: -apple-system, 'SF Mono', monospace; }
.unit-row .val.time { font-size: 10px; color: var(--muted); }
.empty-row { color: var(--muted); font-size: 11px; text-align: center; padding: 16px 0; }
.gap-badge {
  margin-top: 4px; font-size: 9px; color: var(--warn);
  background: rgba(245,166,35,0.1); padding: 2px 4px; border-radius: 2px; text-align: center;
}
</style>
