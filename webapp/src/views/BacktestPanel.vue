<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useToast } from '@/composables/useToast'
import { useMarketStore } from '@/stores/market'
import { useStrategyStore } from '@/stores/strategy'
import { backtestApi } from '@/services/backtest'
import { strategyApi } from '@/services/strategy'
import { ALL_SYMBOLS } from '@/config/symbols'

const toast = useToast()
const market = useMarketStore()
const strategyStore = useStrategyStore()

const form = ref({
  symbol: market.curSym || 'AG',
  strategy_id: 'turtle_v1',
  start_date: '2024-01-01',
  end_date: '2024-12-31',
  initial_capital: 1_000_000
})

const running = ref(false)
const result = ref<any | null>(null)
const trades = ref<any[]>([])

const history = ref<any[]>([])
const historyLoading = ref(false)

const detailModal = ref<{ open: boolean; runId: string | null; data: any | null; trades: any[] }>({
  open: false, runId: null, data: null, trades: []
})

async function run() {
  running.value = true
  result.value = null
  trades.value = []
  try {
    const r = await backtestApi.run({
      symbols: [form.value.symbol],
      strategy_id: form.value.strategy_id,
      start_date: form.value.start_date,
      end_date: form.value.end_date,
      initial_capital: Number(form.value.initial_capital)
    })
    result.value = r
    trades.value = r.trades || []
    toast.push({ kind: 'success', title: '回测完成', body: `收益 ${(r.total_return_pct ?? 0).toFixed(2)}%` })
    await loadHistory()
  } catch (e) {
    toast.push({ kind: 'error', title: '回测失败', body: String(e) })
  } finally {
    running.value = false
  }
}

async function loadHistory() {
  historyLoading.value = true
  try {
    const r = await backtestApi.list(20)
    history.value = r.runs || []
  } catch (e) {
    history.value = []
  } finally {
    historyLoading.value = false
  }
}

async function viewDetail(runId: string) {
  try {
    const [d, ts] = await Promise.all([
      backtestApi.get(runId),
      backtestApi.trades(runId)
    ])
    detailModal.value = { open: true, runId, data: d, trades: ts.trades || [] }
  } catch (e) {
    toast.push({ kind: 'error', title: '加载详情失败', body: String(e) })
  }
}

function closeDetail() {
  detailModal.value.open = false
}

async function loadStrategies() {
  try {
    const r = await strategyApi.list(true)
    if (r.strategies && r.strategies.length > 0) {
      strategyStore.setList(r.strategies)
      const first = r.strategies.find(s => s.is_active) || r.strategies[0]
      form.value.strategy_id = first.strategy_id
    }
  } catch { /* ignore */ }
}

onMounted(() => {
  loadStrategies()
  loadHistory()
})

function fmt(n?: number, d = 2): string {
  return n == null ? '--' : Number(n).toLocaleString(undefined, { maximumFractionDigits: d })
}
function fmtPct(n?: number): string {
  if (n == null) return '--'
  return (n >= 0 ? '+' : '') + n.toFixed(2) + '%'
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
  <section class="backtest-panel">
    <h3 class="panel-h3">📊 回测面板</h3>

    <!-- 表单 -->
    <div class="bt-form">
      <div class="form-row">
        <div class="form-field">
          <label>品种</label>
          <select v-model="form.symbol">
            <option v-for="s in ALL_SYMBOLS" :key="s" :value="s">{{ s }}</option>
          </select>
        </div>
        <div class="form-field">
          <label>策略</label>
          <select v-model="form.strategy_id">
            <option v-for="s in strategyStore.list" :key="s.strategy_id" :value="s.strategy_id">
              {{ s.name || s.strategy_id }}
            </option>
            <option v-if="strategyStore.list.length === 0" value="turtle_v1">turtle_v1</option>
          </select>
        </div>
      </div>
      <div class="form-row">
        <div class="form-field">
          <label>开始日期</label>
          <input v-model="form.start_date" type="date" />
        </div>
        <div class="form-field">
          <label>结束日期</label>
          <input v-model="form.end_date" type="date" />
        </div>
        <div class="form-field">
          <label>初始资金</label>
          <input v-model.number="form.initial_capital" type="number" min="0" step="10000" />
        </div>
        <div class="form-field form-action">
          <button class="run-btn" :disabled="running" @click="run">
            <span v-if="running">⟳ 运行中...</span>
            <span v-else>▶ 运行回测</span>
          </button>
        </div>
      </div>
    </div>

    <!-- 本次回测结果 -->
    <div v-if="result" class="bt-result">
      <h4>本次结果</h4>
      <div class="metrics">
        <div class="metric">
          <span class="lbl">总收益</span>
          <span :class="['val', pnlClass(result.total_return_pct)]">{{ fmtPct(result.total_return_pct) }}</span>
        </div>
        <div class="metric">
          <span class="lbl">年化</span>
          <span :class="['val', pnlClass(result.annual_return)]">{{ fmtPct(result.annual_return) }}</span>
        </div>
        <div class="metric">
          <span class="lbl">夏普</span>
          <span :class="['val', pnlClass(result.sharpe_ratio)]">{{ fmt(result.sharpe_ratio) }}</span>
        </div>
        <div class="metric">
          <span class="lbl">最大回撤</span>
          <span class="val neg">{{ result.max_drawdown != null ? result.max_drawdown.toFixed(2) + '%' : '--' }}</span>
        </div>
        <div class="metric">
          <span class="lbl">交易数</span>
          <span class="val">{{ trades.length }}</span>
        </div>
        <div class="metric">
          <span class="lbl">胜率</span>
          <span class="val">{{ result.win_rate != null ? (result.win_rate * 100).toFixed(1) + '%' : '--' }}</span>
        </div>
      </div>
      <div v-if="trades.length > 0" class="trades-block">
        <h5>成交明细（前 15 条）</h5>
        <div class="trade-rows">
          <div v-for="(t, i) in trades.slice(0, 15)" :key="i" class="trade-row">
            <span class="trade-date">{{ t.entry_date || '--' }}</span>
            <span :class="['trade-dir', t.direction]">
              {{ t.direction === 'long' ? '▲多' : t.direction === 'short' ? '▼空' : '-' }}
            </span>
            <span class="trade-price">{{ fmt(t.entry_price) }}</span>
            <span :class="['trade-pnl', pnlClass(t.pnl)]">{{ t.pnl != null ? (t.pnl >= 0 ? '+' : '') + t.pnl.toFixed(0) : '--' }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 历史回测 -->
    <div class="bt-history">
      <h4>历史回测
        <button class="refresh-btn" @click="loadHistory" :disabled="historyLoading">
          {{ historyLoading ? '⟳' : '↻' }} 刷新
        </button>
      </h4>
      <table v-if="history.length > 0" class="hist-table">
        <thead>
          <tr>
            <th>时间</th>
            <th>策略</th>
            <th>品种</th>
            <th>状态</th>
            <th>收益</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="r in history" :key="r.run_id">
            <td>{{ fmtDate(r.created_at) }}</td>
            <td>{{ r.strategy_id }}</td>
            <td>{{ r.symbol }}</td>
            <td><span :class="['status-badge-inline', `st-${r.status}`]">{{ r.status }}</span></td>
            <td :class="pnlClass(r.total_return_pct)">{{ fmtPct(r.total_return_pct) }}</td>
            <td>
              <button class="action-btn" @click="viewDetail(r.run_id)">查看</button>
            </td>
          </tr>
        </tbody>
      </table>
      <div v-else class="empty">暂无历史回测</div>
    </div>

    <!-- 详情模态框 -->
    <Teleport to="body">
      <div v-if="detailModal.open" class="detail-host" @click.self="closeDetail">
        <div class="detail-box">
          <header>
            <h4>回测详情 · {{ detailModal.runId?.slice(0, 8) }}</h4>
            <button class="close-btn" @click="closeDetail">×</button>
          </header>
          <div v-if="detailModal.data" class="detail-body">
            <table class="info-table">
              <tr><th>策略</th><td>{{ detailModal.data.strategy_id }}</td></tr>
              <tr><th>品种</th><td>{{ detailModal.data.symbol }}</td></tr>
              <tr><th>区间</th><td>{{ detailModal.data.start_date }} ~ {{ detailModal.data.end_date }}</td></tr>
              <tr><th>状态</th><td>{{ detailModal.data.status }}</td></tr>
              <tr><th>初始资金</th><td>{{ fmt(detailModal.data.initial_capital, 0) }}</td></tr>
              <tr><th>最终资金</th><td>{{ fmt(detailModal.data.final_capital, 0) }}</td></tr>
              <tr><th>总收益</th><td :class="pnlClass(detailModal.data.total_return_pct)">{{ fmtPct(detailModal.data.total_return_pct) }}</td></tr>
              <tr><th>最大回撤</th><td class="neg">{{ detailModal.data.max_drawdown_pct }}%</td></tr>
              <tr><th>总成交</th><td>{{ detailModal.data.total_trades }}</td></tr>
              <tr><th>创建</th><td>{{ detailModal.data.created_at }}</td></tr>
              <tr><th>完成</th><td>{{ detailModal.data.completed_at || '--' }}</td></tr>
            </table>
            <h5 style="margin-top:12px">成交记录</h5>
            <div v-if="detailModal.trades.length > 0" class="trade-rows">
              <div v-for="(t, i) in detailModal.trades.slice(0, 30)" :key="i" class="trade-row">
                <span class="trade-date">{{ t.entry_date || '--' }}</span>
                <span :class="['trade-dir', t.direction]">{{ t.direction === 'long' ? '▲多' : t.direction === 'short' ? '▼空' : '-' }}</span>
                <span class="trade-price">{{ fmt(t.entry_price) }}</span>
                <span :class="['trade-pnl', pnlClass(t.pnl)]">{{ t.pnl != null ? (t.pnl >= 0 ? '+' : '') + t.pnl.toFixed(0) : '--' }}</span>
              </div>
            </div>
            <div v-else class="empty">无成交记录</div>
          </div>
        </div>
      </div>
    </Teleport>
  </section>
</template>

<style scoped>
.backtest-panel {
  background: var(--card); border: 1px solid var(--border); border-radius: 6px;
  padding: 14px 16px;
}
.panel-h3 { font-size: 14px; color: var(--accent); margin: 0 0 10px 0; }
.bt-form {
  display: flex; flex-direction: column; gap: 8px;
  background: var(--bg); border-radius: 4px; padding: 10px;
}
.form-row { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; }
.form-field { display: flex; flex-direction: column; gap: 3px; }
.form-field label { font-size: 10px; color: var(--muted); }
.form-field input, .form-field select {
  background: var(--card); border: 1px solid var(--border); color: var(--text);
  border-radius: 3px; padding: 5px 8px; font-size: 12px;
}
.form-action { justify-content: flex-end; }
.run-btn {
  background: var(--accent); color: #fff; border: none;
  padding: 7px 14px; border-radius: 3px; font-size: 12px; cursor: pointer;
  font-weight: 600; margin-top: 14px;
}
.run-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.run-btn:hover:not(:disabled) { opacity: 0.85; }

.bt-result { margin-top: 14px; background: var(--bg); border-radius: 4px; padding: 10px; }
.bt-result h4 { font-size: 12px; color: var(--muted); margin: 0 0 8px 0; }
.metrics { display: grid; grid-template-columns: repeat(6, 1fr); gap: 8px; }
.metric {
  display: flex; flex-direction: column; align-items: center; gap: 2px;
  background: var(--card); padding: 6px; border-radius: 3px;
}
.metric .lbl { font-size: 10px; color: var(--muted); }
.metric .val { font-size: 13px; font-weight: 600; }
.val.pos { color: var(--buy); }
.val.neg { color: var(--sell); }

.trades-block { margin-top: 10px; }
.trades-block h5 { font-size: 11px; color: var(--muted); margin: 0 0 6px 0; }
.trade-rows { display: flex; flex-direction: column; gap: 2px; max-height: 200px; overflow-y: auto; }
.trade-row {
  display: grid; grid-template-columns: 100px 50px 1fr 1fr;
  gap: 8px; font-size: 11px; padding: 3px 0;
  border-bottom: 1px dashed var(--border);
}
.trade-row:last-child { border-bottom: none; }
.trade-date { color: var(--muted); font-family: monospace; }
.trade-dir.long { color: var(--buy); }
.trade-dir.short { color: var(--sell); }
.trade-price { font-family: monospace; }
.trade-pnl.pos { color: var(--buy); }
.trade-pnl.neg { color: var(--sell); }
.trade-pnl.profit { color: var(--buy); }
.trade-pnl.loss { color: var(--sell); }

.bt-history { margin-top: 14px; }
.bt-history h4 { font-size: 12px; color: var(--muted); margin: 0 0 8px 0; display: flex; align-items: center; gap: 8px; }
.refresh-btn { background: transparent; border: 1px solid var(--border); color: var(--muted); font-size: 10px; padding: 2px 6px; border-radius: 3px; cursor: pointer; }
.refresh-btn:hover { color: var(--text); }

.hist-table { width: 100%; border-collapse: collapse; font-size: 11px; }
.hist-table th, .hist-table td { padding: 5px 6px; text-align: left; border-bottom: 1px solid var(--border); }
.hist-table th { color: var(--muted); font-weight: 600; }
.status-badge-inline {
  padding: 1px 5px; border-radius: 3px; font-size: 9px; font-weight: 600;
}
.status-badge-inline.st-completed, .status-badge-inline.st-active { background: rgba(38,196,133,0.18); color: var(--buy); }
.status-badge-inline.st-failed, .status-badge-inline.st-closed { background: rgba(240,86,106,0.18); color: var(--sell); }
.status-badge-inline.st-running, .status-badge-inline.st-pending { background: rgba(91,138,240,0.18); color: var(--accent); }
.action-btn { background: var(--accent); color: #fff; border: none; padding: 2px 8px; border-radius: 3px; font-size: 10px; cursor: pointer; }
.action-btn:hover { opacity: 0.85; }
.empty { padding: 16px; text-align: center; color: var(--muted); font-size: 12px; }

.detail-host { position: fixed; inset: 0; z-index: 2000; background: rgba(0,0,0,0.6); display: flex; align-items: center; justify-content: center; }
.detail-box { background: var(--card); border: 1px solid var(--border); border-radius: 8px; width: 600px; max-width: 92vw; max-height: 84vh; overflow-y: auto; }
.detail-box header { display: flex; align-items: center; justify-content: space-between; padding: 12px 16px; border-bottom: 1px solid var(--border); }
.detail-box header h4 { color: var(--accent); margin: 0; font-size: 14px; }
.close-btn { background: transparent; border: none; color: var(--muted); font-size: 20px; cursor: pointer; }
.detail-body { padding: 12px 16px; }
.info-table { width: 100%; border-collapse: collapse; font-size: 12px; }
.info-table th, .info-table td { padding: 4px 6px; border-bottom: 1px solid var(--border); text-align: left; }
.info-table th { color: var(--muted); font-weight: 500; width: 100px; }
</style>
