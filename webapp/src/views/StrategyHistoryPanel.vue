<script setup lang="ts">
import { ref, watch } from 'vue'
import { useToast } from '@/composables/useToast'
import { strategyApi } from '@/services/strategy'

const props = withDefaults(defineProps<{
  strategyId: string
  tab?: 'params' | 'signals' | 'events'
}>(), {
  tab: 'params'
})

const emit = defineEmits<{ (e: 'update:tab', v: 'params' | 'signals' | 'events'): void }>()

const toast = useToast()
const curTab = ref(props.tab)
const loading = ref(false)

const paramHistory = ref<any[]>([])
const signals = ref<any[]>([])
const events = ref<any[]>([])

watch(() => curTab.value, async (t) => {
  emit('update:tab', t)
  await load(t)
})
watch(() => props.strategyId, async () => { await load(curTab.value) }, { immediate: true })
watch(() => props.tab, (t) => { if (t && t !== curTab.value) curTab.value = t })

async function load(tab: 'params' | 'signals' | 'events') {
  if (!props.strategyId) return
  loading.value = true
  try {
    if (tab === 'params') {
      const r: any = await strategyApi.paramHistory(props.strategyId, 20)
      paramHistory.value = Array.isArray(r) ? r : (r?.history || [])
    } else if (tab === 'signals') {
      const r: any = await strategyApi.signals(props.strategyId, { days: 30, limit: 50 })
      signals.value = Array.isArray(r) ? r : (r?.signals || [])
    } else {
      const r: any = await strategyApi.events(props.strategyId, { days: 30, limit: 50 })
      events.value = Array.isArray(r) ? r : (r?.events || [])
    }
  } catch (e) {
    toast.push({ kind: 'warn', title: '策略历史加载失败', body: String(e) })
  } finally {
    loading.value = false
  }
}

function fmtDate(s?: string): string {
  return (s || '').substring(0, 16)
}
function fmt(n?: number, d = 2): string {
  return n == null ? '--' : Number(n).toLocaleString(undefined, { maximumFractionDigits: d })
}
function fmtJSON(o: any, max = 80): string {
  if (o == null) return '-'
  const s = JSON.stringify(o)
  return s.length > max ? s.substring(0, max) + '...' : s
}
function dirLabel(d: any): string {
  if (d === 1 || d === 'long') return '多'
  if (d === 2 || d === 'short') return '空'
  return '-'
}
</script>

<template>
  <div class="strategy-history-panel">
    <h3 class="panel-h3">📜 策略历史 · {{ strategyId || '--' }}</h3>
    <div class="tab-bar">
      <button :class="['tab-btn', { active: curTab === 'params' }]" @click="curTab = 'params'">参数</button>
      <button :class="['tab-btn', { active: curTab === 'signals' }]" @click="curTab = 'signals'">信号</button>
      <button :class="['tab-btn', { active: curTab === 'events' }]" @click="curTab = 'events'">事件</button>
      <span v-if="loading" class="loading-tag">⟳</span>
    </div>

    <div class="tab-content">
      <!-- params -->
      <table v-if="curTab === 'params'" class="hist-table">
        <thead>
          <tr>
            <th>时间</th>
            <th>参数</th>
            <th>原因</th>
            <th>操作人</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="paramHistory.length === 0">
            <td colspan="4" class="empty">无参数历史</td>
          </tr>
          <tr v-for="(h, i) in paramHistory" :key="i">
            <td>{{ fmtDate(h.changed_at) }}</td>
            <td class="cell-params" :title="fmtJSON(h.params, 1000)">{{ fmtJSON(h.params) }}</td>
            <td>{{ h.change_reason || '-' }}</td>
            <td>{{ h.changed_by || '-' }}</td>
          </tr>
        </tbody>
      </table>

      <!-- signals -->
      <table v-else-if="curTab === 'signals'" class="hist-table">
        <thead>
          <tr>
            <th>时间</th>
            <th>品种</th>
            <th>类型</th>
            <th>方向</th>
            <th>触发价</th>
            <th>参考价</th>
            <th>N</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="signals.length === 0">
            <td colspan="7" class="empty">无信号历史（近 30 天）</td>
          </tr>
          <tr v-for="(s, i) in signals" :key="i">
            <td>{{ fmtDate(s.bar_time) }}</td>
            <td>{{ s.symbol || '-' }}</td>
            <td><strong>{{ s.signal_type || '-' }}</strong></td>
            <td :class="['dir-tag', s.direction === 'long' || s.direction === 1 ? 'long' : s.direction === 'short' || s.direction === 2 ? 'short' : '']">
              {{ dirLabel(s.direction) }}
            </td>
            <td class="num">{{ fmt(s.trigger_price) }}</td>
            <td class="num">{{ fmt(s.reference_price) }}</td>
            <td class="num">{{ s.reference_n != null ? Number(s.reference_n).toFixed(1) : '-' }}</td>
          </tr>
        </tbody>
      </table>

      <!-- events -->
      <table v-else class="hist-table">
        <thead>
          <tr>
            <th>时间</th>
            <th>事件类型</th>
            <th>品种</th>
            <th>上下文</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="events.length === 0">
            <td colspan="4" class="empty">无事件日志（近 30 天）</td>
          </tr>
          <tr v-for="(e, i) in events" :key="i">
            <td>{{ fmtDate(e.event_at) }}</td>
            <td><strong>{{ e.event_type || '-' }}</strong></td>
            <td>{{ e.symbol || '-' }}</td>
            <td class="cell-ctx" :title="fmtJSON(e.context, 1000)">{{ fmtJSON(e.context, 100) }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<style scoped>
.strategy-history-panel {
  background: var(--card); border: 1px solid var(--border); border-radius: 6px;
  padding: 14px 16px;
}
.panel-h3 { font-size: 14px; color: var(--accent); margin: 0 0 10px 0; }

.tab-bar { display: flex; gap: 4px; border-bottom: 1px solid var(--border); margin-bottom: 10px; }
.tab-btn {
  background: transparent; border: none; color: var(--muted);
  padding: 6px 14px; font-size: 12px; cursor: pointer;
  border-bottom: 2px solid transparent; transition: all 0.15s;
}
.tab-btn:hover { color: var(--text); }
.tab-btn.active { color: var(--accent); border-bottom-color: var(--accent); font-weight: 600; }
.loading-tag { margin-left: auto; color: var(--accent); font-size: 11px; align-self: center; }

.tab-content { min-height: 200px; }

.hist-table { width: 100%; border-collapse: collapse; font-size: 11px; }
.hist-table th, .hist-table td { padding: 5px 6px; text-align: left; border-bottom: 1px solid var(--border); }
.hist-table th { color: var(--muted); font-weight: 600; background: var(--bg); position: sticky; top: 0; }
.hist-table td.num { font-family: -apple-system, 'SF Mono', monospace; text-align: right; }
.hist-table td.empty { text-align: center; padding: 20px; color: var(--muted); }
.cell-params, .cell-ctx { font-family: -apple-system, 'SF Mono', monospace; max-width: 260px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.dir-tag.long { color: var(--buy); }
.dir-tag.short { color: var(--sell); }
</style>
