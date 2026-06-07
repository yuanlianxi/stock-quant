<script setup lang="ts">
import { ref, watch } from 'vue'
import { useToast } from '@/composables/useToast'
import { useAccountStore } from '@/stores/account'
import { accountApi } from '@/services/account'

const props = defineProps<{ open: boolean }>()
const emit = defineEmits<{ (e: 'close'): void }>()

const toast = useToast()
const accountStore = useAccountStore()

const ACCOUNTS = [
  { id: 'sim_default', label: 'sim_default' },
  { id: 'sim_alpha', label: 'sim_alpha' },
  { id: 'sim_beta', label: 'sim_beta' }
]
const TABS = [
  { key: 'overview', label: '总览' },
  { key: 'positions', label: '持仓' },
  { key: 'units', label: 'Units' },
  { key: 'sessions', label: 'Session' },
  { key: 'trades', label: '交易' }
] as const

type TabKey = typeof TABS[number]['key']

const curTab = ref<TabKey>('overview')
const loading = ref(false)
const overview = ref<any | null>(null)
const positions = ref<any[]>([])
const unitsBySession = ref<Record<string, any[]>>({})
const sessions = ref<any[]>([])
const trades = ref<any[]>([])

watch(() => [props.open, accountStore.current] as const, async ([isOpen, acct]) => {
  if (isOpen && acct) await loadTab(curTab.value)
}, { immediate: true })

watch(curTab, async (t) => { if (props.open) await loadTab(t) })

async function loadTab(tab: TabKey) {
  loading.value = true
  try {
    if (tab === 'overview') {
      const r: any = await accountApi.overview(accountStore.current, 30)
      overview.value = r
    } else if (tab === 'positions') {
      const r: any = await accountApi.positions(accountStore.current)
      positions.value = r.positions || []
    } else if (tab === 'units') {
      const r: any = await accountApi.units(accountStore.current)
      unitsBySession.value = r.by_session || {}
    } else if (tab === 'sessions') {
      const r: any = await accountApi.sessions(accountStore.current, 50)
      sessions.value = r.sessions || []
    } else if (tab === 'trades') {
      const r: any = await accountApi.trades(accountStore.current, { days: 30, limit: 50 })
      trades.value = r.trades || []
    }
  } catch (e) {
    toast.push({ kind: 'warn', title: `账户 ${tab} 加载失败`, body: String(e) })
  } finally {
    loading.value = false
  }
}

function switchAccount(id: string) {
  accountStore.setCurrent(id)
  loadTab(curTab.value)
}

function onClose() { emit('close') }

function fmt(n?: number, d = 2): string {
  return n == null ? '--' : Number(n).toLocaleString(undefined, { maximumFractionDigits: d })
}
function fmtMoney(n?: number): string {
  if (n == null) return '--'
  return (n >= 0 ? '+' : '') + n.toLocaleString('zh-CN', { maximumFractionDigits: 2 })
}
function pnlClass(n?: number): string {
  if (n == null) return ''
  return n >= 0 ? 'pos' : 'neg'
}
function fmtDate(s?: string): string {
  return (s || '').substring(0, 16)
}
</script>

<template>
  <Teleport to="body">
    <Transition name="modal-fade">
      <div v-if="open" class="acct-host" role="dialog" aria-modal="true" @click.self="onClose">
        <div class="acct-mask" @click="onClose" />
        <div class="acct-box">
          <header class="acct-head">
            <h3>📊 账户中心</h3>
            <div class="acct-switch">
              <button
                v-for="a in ACCOUNTS"
                :key="a.id"
                :class="['acct-pill', { active: accountStore.current === a.id }]"
                @click="switchAccount(a.id)"
              >
                {{ a.label }}
              </button>
            </div>
            <button class="close-btn" @click="onClose" aria-label="关闭">×</button>
          </header>

          <div class="acct-tabs">
            <button
              v-for="t in TABS"
              :key="t.key"
              :class="['acct-tab', { active: curTab === t.key }]"
              @click="curTab = t.key"
            >{{ t.label }}</button>
            <span v-if="loading" class="loading-tag">⟳</span>
          </div>

          <div class="acct-body">
            <!-- overview -->
            <div v-if="curTab === 'overview'" class="tab-pane">
              <template v-if="overview">
                <h4>账户基本信息</h4>
                <table class="info-table">
                  <tr><th>账户ID</th><td>{{ overview.account?.account_id || accountStore.current }}</td></tr>
                  <tr><th>余额</th><td>{{ fmt(overview.account?.balance, 0) }}</td></tr>
                  <tr><th>可用</th><td>{{ fmt(overview.account?.available, 0) }}</td></tr>
                  <tr><th>已用保证金</th><td>{{ fmt(overview.account?.margin_used, 0) }}</td></tr>
                </table>
                <h4>总览</h4>
                <table class="info-table">
                  <tr><th>持仓价值</th><td>{{ fmt(overview.summary?.position_value, 0) }}</td></tr>
                  <tr><th>浮动盈亏</th><td :class="pnlClass(overview.summary?.unrealized_pnl)">{{ fmtMoney(overview.summary?.unrealized_pnl) }}</td></tr>
                  <tr><th>已实现</th><td :class="pnlClass(overview.summary?.realized_pnl)">{{ fmtMoney(overview.summary?.realized_pnl) }}</td></tr>
                  <tr><th>Open Sessions</th><td>{{ overview.summary?.open_sessions_count ?? 0 }}</td></tr>
                  <tr><th>Open Units</th><td>{{ overview.summary?.open_units_count ?? 0 }}</td></tr>
                </table>
                <template v-if="overview.open_sessions?.[0]?.lines">
                  <h4>价格线（首个 Session）</h4>
                  <table class="info-table"><tbody>
                    <tr><th>止损</th><td>{{ fmt(overview.open_sessions[0].lines.lines?.stop_loss) }}</td></tr>
                    <tr><th>加仓</th><td>{{ fmt(overview.open_sessions[0].lines.lines?.add) }}</td></tr>
                    <tr><th>20日反向</th><td>{{ fmt(overview.open_sessions[0].lines.lines?.exit_20) }}</td></tr>
                  </tbody></table>
                </template>
              </template>
              <div v-else class="empty">无数据</div>
            </div>

            <!-- positions -->
            <div v-else-if="curTab === 'positions'" class="tab-pane">
              <div v-if="positions.length === 0" class="empty">无持仓</div>
              <table v-else class="data-table">
                <thead><tr><th>品种</th><th>合约</th><th>数量</th><th>均价</th><th>未实现</th></tr></thead>
                <tbody>
                  <tr v-for="(p, i) in positions" :key="i">
                    <td>{{ p.symbol }}</td>
                    <td>{{ p.contract_code || '--' }}</td>
                    <td class="num">{{ p.quantity }}</td>
                    <td class="num">{{ fmt(p.avg_cost) }}</td>
                    <td :class="['num', pnlClass(p.unrealized_pnl)]">{{ fmt(p.unrealized_pnl) }}</td>
                  </tr>
                </tbody>
              </table>
            </div>

            <!-- units -->
            <div v-else-if="curTab === 'units'" class="tab-pane">
              <div v-if="Object.keys(unitsBySession).length === 0" class="empty">无 Unit 明细</div>
              <div v-else>
                <template v-for="(units, sid) in unitsBySession" :key="sid">
                  <h4>Session: {{ sid.slice(0, 8) }}</h4>
                  <table class="data-table">
                    <thead><tr><th>Unit</th><th>open</th><th>hand</th><th>状态</th><th>跳空</th><th>close</th></tr></thead>
                    <tbody>
                      <tr v-for="(u, i) in units" :key="i">
                        <td>{{ u.unit_index }}</td>
                        <td class="num">{{ fmt(u.open_price) }}</td>
                        <td class="num">{{ u.open_hand_count }}</td>
                        <td>{{ u.status }}</td>
                        <td>{{ u.is_gap === 1 || u.is_gap === true ? '⚠️' : '·' }}</td>
                        <td class="num">{{ u.close_price ? fmt(u.close_price) : '--' }}</td>
                      </tr>
                    </tbody>
                  </table>
                </template>
              </div>
            </div>

            <!-- sessions -->
            <div v-else-if="curTab === 'sessions'" class="tab-pane">
              <div v-if="sessions.length === 0" class="empty">无 Session</div>
              <table v-else class="data-table">
                <thead><tr><th>Session</th><th>品种</th><th>方向</th><th>状态</th><th>入场价</th><th>Units</th></tr></thead>
                <tbody>
                  <tr v-for="(s, i) in sessions" :key="i">
                    <td>{{ s.session_id?.slice(0, 8) }}</td>
                    <td>{{ s.symbol }}</td>
                    <td>{{ s.direction }}</td>
                    <td><span :class="['status-badge-inline', `st-${s.status}`]">{{ s.status }}</span></td>
                    <td class="num">{{ fmt(s.first_entry_price) }}</td>
                    <td>{{ s.current_units || 0 }}/{{ s.total_units || 0 }}</td>
                  </tr>
                </tbody>
              </table>
            </div>

            <!-- trades -->
            <div v-else class="tab-pane">
              <div v-if="trades.length === 0" class="empty">无成交记录</div>
              <table v-else class="data-table">
                <thead><tr><th>时间</th><th>品种</th><th>方向</th><th>价</th><th>量</th></tr></thead>
                <tbody>
                  <tr v-for="(t, i) in trades" :key="i">
                    <td>{{ fmtDate(t.filled_at) }}</td>
                    <td>{{ t.symbol }}</td>
                    <td>{{ t.direction }}</td>
                    <td class="num">{{ fmt(t.filled_price) }}</td>
                    <td class="num">{{ t.filled_quantity }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          <footer class="acct-foot">
            <button class="close-foot" @click="onClose">关闭</button>
          </footer>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.acct-host { position: fixed; inset: 0; z-index: 1800; }
.acct-mask { position: absolute; inset: 0; background: rgba(0,0,0,0.6); }
.acct-box {
  position: absolute; left: 50%; top: 50%; transform: translate(-50%, -50%);
  width: 800px; max-width: 95vw; max-height: 90vh;
  background: var(--card); border: 1px solid var(--border); border-radius: 8px;
  display: flex; flex-direction: column;
  box-shadow: 0 8px 32px rgba(0,0,0,0.5);
}

.acct-head {
  display: flex; align-items: center; gap: 12px;
  padding: 12px 18px; border-bottom: 1px solid var(--border);
}
.acct-head h3 { color: var(--accent); margin: 0; font-size: 15px; }
.acct-switch { display: flex; gap: 4px; }
.acct-pill {
  background: var(--bg); border: 1px solid var(--border);
  color: var(--muted); font-size: 11px; padding: 4px 10px;
  border-radius: 12px; cursor: pointer; transition: all 0.15s;
}
.acct-pill:hover { color: var(--text); }
.acct-pill.active { background: var(--accent); color: #fff; border-color: var(--accent); }
.close-btn { background: transparent; border: none; color: var(--muted); font-size: 22px; cursor: pointer; line-height: 1; padding: 0 8px; margin-left: auto; }
.close-btn:hover { color: var(--text); }

.acct-tabs {
  display: flex; gap: 2px; padding: 0 18px;
  border-bottom: 1px solid var(--border); background: var(--bg);
}
.acct-tab {
  background: transparent; border: none; color: var(--muted);
  padding: 8px 16px; font-size: 12px; cursor: pointer;
  border-bottom: 2px solid transparent;
}
.acct-tab:hover { color: var(--text); }
.acct-tab.active { color: var(--accent); border-bottom-color: var(--accent); font-weight: 600; }
.loading-tag { margin-left: auto; color: var(--accent); font-size: 11px; align-self: center; }

.acct-body { flex: 1; overflow-y: auto; padding: 14px 18px; }
.tab-pane { font-size: 12px; }
.tab-pane h4 { font-size: 12px; color: var(--muted); margin: 12px 0 6px 0; }
.tab-pane h4:first-child { margin-top: 0; }

.info-table, .data-table { width: 100%; border-collapse: collapse; }
.info-table th, .info-table td, .data-table th, .data-table td { padding: 5px 6px; border-bottom: 1px solid var(--border); text-align: left; }
.info-table th, .data-table th { color: var(--muted); font-weight: 600; background: var(--bg); }
.info-table th { width: 130px; }
.data-table td.num { font-family: -apple-system, 'SF Mono', monospace; text-align: right; }
.num.pos { color: var(--buy); }
.num.neg { color: var(--sell); }
.pos { color: var(--buy); }
.neg { color: var(--sell); }
.empty { padding: 30px; text-align: center; color: var(--muted); }

.status-badge-inline { padding: 1px 5px; border-radius: 3px; font-size: 9px; font-weight: 600; }
.status-badge-inline.st-completed, .status-badge-inline.st-active { background: rgba(38,196,133,0.18); color: var(--buy); }
.status-badge-inline.st-failed, .status-badge-inline.st-closed { background: rgba(240,86,106,0.18); color: var(--sell); }
.status-badge-inline.st-running, .status-badge-inline.st-open, .status-badge-inline.st-pending { background: rgba(91,138,240,0.18); color: var(--accent); }

.acct-foot {
  padding: 12px 18px; border-top: 1px solid var(--border); display: flex; justify-content: flex-end;
}
.close-foot {
  background: var(--bg); border: 1px solid var(--border); color: var(--text);
  padding: 6px 18px; border-radius: 4px; font-size: 12px; cursor: pointer;
}
.close-foot:hover { background: var(--border); }

.modal-fade-enter-active, .modal-fade-leave-active { transition: opacity 0.2s ease; }
.modal-fade-enter-from, .modal-fade-leave-to { opacity: 0; }
</style>
