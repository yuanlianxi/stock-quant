<script setup lang="ts">
import { ref, watch } from 'vue'
import { useToast } from '@/composables/useToast'
import { contractsApi } from '@/services/contracts'

interface Contract {
  contract_code: string
  name?: string
  exchange?: string
  expire_date?: string
  is_main?: boolean
  main_rank?: number
  [k: string]: any
}

interface ContractQuote {
  trade?: number
  change?: number
  change_pct?: number
  position?: number
  volume?: number
  [k: string]: any
}

const props = defineProps<{
  symbol: string
  open: boolean
}>()
const emit = defineEmits<{ (e: 'close'): void }>()

const toast = useToast()
const loading = ref(false)
const subTitle = ref('--')
const contracts = ref<Contract[]>([])
const quotes = ref<Record<string, ContractQuote>>({})

watch(
  () => [props.open, props.symbol] as const,
  async ([isOpen, sym]) => {
    if (isOpen && sym) await load(sym)
  },
  { immediate: true }
)

async function load(symbol: string) {
  loading.value = true
  subTitle.value = '加载中...'
  contracts.value = []
  quotes.value = {}
  try {
    const d: any = await contractsApi.list(symbol)
    if (!d.contracts || d.contracts.length === 0) {
      subTitle.value = d.note || '无数据'
      return
    }
    contracts.value = d.contracts
    subTitle.value = `共 ${d.count} 个合约 · 主力 ${d.main_contract || '未定'}`
    // 并行拉行情
    const tasks = d.contracts.map((c: Contract) =>
      contractsApi
        .quote(c.contract_code)
        .then((j: any) => j?.ok ? j.data : null)
        .catch(() => null)
    )
    const results = await Promise.all(tasks)
    const qMap: Record<string, ContractQuote> = {}
    d.contracts.forEach((c: Contract, i: number) => {
      if (results[i]) qMap[c.contract_code] = results[i] as ContractQuote
    })
    quotes.value = qMap
  } catch (e) {
    subTitle.value = '加载失败'
    toast.push({ kind: 'error', title: '合约列表加载失败', body: String(e) })
  } finally {
    loading.value = false
  }
}

function fmt(n?: number, digits = 2): string {
  return n == null ? '-' : Number(n).toLocaleString(undefined, { maximumFractionDigits: digits })
}
function fmtChg(pct?: number): string {
  if (pct == null) return '-'
  return (pct >= 0 ? '+' : '') + pct.toFixed(2) + '%'
}
function chgColor(pct?: number): string {
  if (pct == null) return 'var(--muted)'
  return pct >= 0 ? 'var(--up)' : 'var(--dn)'
}

function onClose() { emit('close') }
</script>

<template>
  <Transition name="drawer-slide">
    <div v-if="open" class="drawer-host" role="dialog" aria-modal="true">
      <div class="drawer-mask" @click="onClose" />
      <aside class="drawer-panel">
        <header class="drawer-head">
          <div class="drawer-title-block">
            <h3>{{ symbol }} 合约列表</h3>
            <span class="drawer-sub">{{ subTitle }}</span>
          </div>
          <button class="drawer-close" @click="onClose" aria-label="关闭">×</button>
        </header>

        <div class="drawer-body">
          <div v-if="loading" class="loading">⟳ 加载合约列表...</div>
          <table v-else-if="contracts.length > 0" class="contract-table">
            <thead>
              <tr>
                <th>主力</th>
                <th>代码</th>
                <th>名称</th>
                <th>到期</th>
                <th class="num">最新价</th>
                <th class="num">涨跌幅</th>
                <th class="num">持仓量</th>
                <th class="num">成交量</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="c in contracts" :key="c.contract_code" :class="{ 'main-row': c.is_main }">
                <td>
                  <span v-if="c.is_main" class="badge-main">⭐ 主力</span>
                  <span v-else-if="c.main_rank" class="badge-sub">次{{ c.main_rank }}</span>
                  <span v-else class="muted">-</span>
                </td>
                <td><strong>{{ c.contract_code }}</strong></td>
                <td>{{ c.name || '-' }}</td>
                <td>{{ c.expire_date || '-' }}</td>
                <td class="num">{{ fmt(quotes[c.contract_code]?.trade) }}</td>
                <td class="num" :style="{ color: chgColor(quotes[c.contract_code]?.change_pct) }">
                  {{ fmtChg(quotes[c.contract_code]?.change_pct) }}
                </td>
                <td class="num">{{ fmt(quotes[c.contract_code]?.position, 0) }}</td>
                <td class="num">{{ fmt(quotes[c.contract_code]?.volume, 0) }}</td>
              </tr>
            </tbody>
          </table>
          <div v-else class="empty">无合约数据</div>
        </div>
      </aside>
    </div>
  </Transition>
</template>

<style scoped>
.drawer-host { position: fixed; inset: 0; z-index: 1500; }
.drawer-mask { position: absolute; inset: 0; background: rgba(0,0,0,0.5); }
.drawer-panel {
  position: absolute; right: 0; top: 0; bottom: 0;
  width: 720px; max-width: 95vw;
  background: var(--card); border-left: 1px solid var(--border);
  display: flex; flex-direction: column;
  box-shadow: -8px 0 24px rgba(0,0,0,0.4);
}
.drawer-head {
  display: flex; align-items: center; justify-content: space-between;
  padding: 14px 18px; border-bottom: 1px solid var(--border);
}
.drawer-title-block h3 { font-size: 15px; color: var(--accent); margin: 0 0 4px 0; }
.drawer-sub { font-size: 11px; color: var(--muted); }
.drawer-close {
  background: transparent; border: none; color: var(--muted);
  font-size: 24px; cursor: pointer; line-height: 1; padding: 0 8px;
}
.drawer-close:hover { color: var(--text); }

.drawer-body { flex: 1; overflow-y: auto; padding: 12px 18px; }
.loading, .empty { padding: 40px; text-align: center; color: var(--muted); font-size: 13px; }

.contract-table { width: 100%; border-collapse: collapse; font-size: 12px; }
.contract-table th {
  text-align: left; color: var(--muted); font-weight: 600;
  padding: 8px 6px; border-bottom: 1px solid var(--border);
  position: sticky; top: 0; background: var(--card);
}
.contract-table td { padding: 6px; border-bottom: 1px solid var(--border); }
.contract-table th.num, .contract-table td.num { text-align: right; font-family: -apple-system, 'SF Mono', monospace; }
.contract-table tr.main-row { background: rgba(91,138,240,0.05); }
.badge-main {
  font-size: 9px; padding: 2px 5px; border-radius: 3px;
  background: rgba(91,138,240,0.18); color: var(--accent); font-weight: 600;
}
.badge-sub { font-size: 10px; color: var(--muted); }
.muted { color: var(--muted); }

.drawer-slide-enter-active, .drawer-slide-leave-active { transition: opacity 0.2s ease; }
.drawer-slide-enter-active .drawer-panel, .drawer-slide-leave-active .drawer-panel { transition: transform 0.25s ease; }
.drawer-slide-enter-from, .drawer-slide-leave-to { opacity: 0; }
.drawer-slide-enter-from .drawer-panel, .drawer-slide-leave-to .drawer-panel { transform: translateX(100%); }
</style>
