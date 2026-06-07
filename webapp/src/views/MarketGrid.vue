<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useMarketStore } from '@/stores/market'
import { useToast } from '@/composables/useToast'
import { useModal } from '@/composables/useModal'
import { EX_MAP, ALL_SYMBOLS } from '@/config/symbols'
import { marketApi } from '@/services/market'
import SymbolDetail from '@/views/SymbolDetail.vue'

interface MarketCard {
  symbol: string
  name: string
  exchange: string
  current_price?: number
  change?: number
  change_pct?: number
  direction?: 'long' | 'short' | ''
  hasSignal?: boolean
  signalType?: string
  contractsCount?: number
  hasMain?: boolean
}

const market = useMarketStore()
const toast = useToast()
const modal = useModal()

// 中文名映射（参考 v1.5 hardcode）
const NAME_MAP: Record<string, string> = {
  AG: '白银', AU: '黄金', CU: '铜', AL: '铝', ZN: '锌', PB: '铅', NI: '镍', SN: '锡',
  RB: '螺纹钢', HC: '热卷', BU: '沥青', RU: '橡胶',
  I: '铁矿石', J: '焦炭', JM: '焦煤', M: '豆粕', Y: '豆油', RM: '菜粕',
  A: '豆一', C: '玉米', CS: '淀粉', JD: '鸡蛋', V: 'PVC', L: '塑料', PP: '聚丙烯', EG: '乙二醇', P: '棕榈',
  TA: 'PTA', MA: '甲醇', FG: '玻璃', SR: '白糖', CF: '棉花', OI: '菜油'
}

const EXCHANGE_TABS: Array<{ key: 'ALL' | 'SHFE' | 'DCE' | 'CZCE' | 'CFFEX'; label: string }> = [
  { key: 'ALL', label: '全部' },
  { key: 'CFFEX', label: '中金所' },
  { key: 'SHFE', label: '上期所' },
  { key: 'DCE', label: '大商所' },
  { key: 'CZCE', label: '郑商所' }
]

const loading = ref(false)
const cards = ref<MarketCard[]>([])

// 过滤当前交易所的品种
const filteredCards = computed<MarketCard[]>(() => {
  if (market.curEx === 'ALL') return cards.value
  return cards.value.filter(c => c.exchange === market.curEx)
})

const exCounts = computed(() => {
  const out: Record<string, number> = { ALL: ALL_SYMBOLS.length }
  for (const ex of ['SHFE', 'DCE', 'CZCE', 'CFFEX']) {
    out[ex] = ALL_SYMBOLS.filter(s => EX_MAP[s] === ex).length
  }
  return out
})

async function loadAll() {
  loading.value = true
  try {
    // 拉 signals/all 一次拿到所有品种的信号+价格
    const sigs = await marketApi.signalsAll()
    const sigMap: Record<string, any> = {}
    if (Array.isArray(sigs)) {
      for (const s of sigs) {
        if (s && s.symbol) sigMap[s.symbol] = s
      }
    }
    // 拉合约 badge 一次（轻量）
    const contractTasks = await Promise.all(
      ALL_SYMBOLS.map(sym =>
        marketApi
          .mainContract(sym)
          .then((d: any) => ({ sym, d }))
          .catch(() => ({ sym, d: null }))
      )
    )
    const contractMap: Record<string, any> = {}
    for (const t of contractTasks) {
      if (t.d) contractMap[t.sym] = t.d
      market.setMarketData(t.sym, t.d || {})
    }
    // 组装 cards
    cards.value = ALL_SYMBOLS.map(sym => {
      const s = sigMap[sym] || {}
      const dirRaw = s.direction
      const dir = dirRaw === 1 || dirRaw === 'long' ? 'long' : dirRaw === 2 || dirRaw === 'short' ? 'short' : ''
      const cd = contractMap[sym] || {}
      return {
        symbol: sym,
        name: NAME_MAP[sym] || sym,
        exchange: EX_MAP[sym] || '',
        current_price: s.current_price ?? s.price,
        change: s.change,
        change_pct: s.change_pct,
        direction: dir,
        hasSignal: !!s.signal_type,
        signalType: s.signal_type,
        contractsCount: cd.count || 0,
        hasMain: !!cd.main_contract
      } as MarketCard
    })
    market.setActiveSignals(sigMap)
  } catch (e) {
    toast.push({ kind: 'warn', title: '品种网格加载失败', body: String(e) })
    // 兜底：只用静态信息
    cards.value = ALL_SYMBOLS.map(sym => ({
      symbol: sym,
      name: NAME_MAP[sym] || sym,
      exchange: EX_MAP[sym] || '',
      direction: ''
    } as MarketCard))
  } finally {
    loading.value = false
  }
}

function setEx(ex: 'ALL' | 'SHFE' | 'DCE' | 'CZCE' | 'CFFEX') {
  market.setEx(ex)
}

function selectSym(sym: string) {
  market.setSym(sym)
}

function fmtPrice(n?: number): string {
  return n == null ? '---' : Number(n).toLocaleString(undefined, { maximumFractionDigits: 2 })
}

function fmtChg(n?: number, pct?: number): string {
  if (n != null) return (n >= 0 ? '+' : '') + n.toFixed(0)
  if (pct != null) return (pct >= 0 ? '+' : '') + pct.toFixed(2) + '%'
  return '--'
}

onMounted(() => {
  loadAll()
  // 每 30s 刷新一次
  setInterval(loadAll, 30_000)
})
</script>

<template>
  <section class="market-grid-wrap">
    <!-- 顶部交易所 Tab -->
    <div class="exchange-bar">
      <button
        v-for="t in EXCHANGE_TABS"
        :key="t.key"
        :class="['ex-tab', { active: market.curEx === t.key }]"
        @click="setEx(t.key)"
      >
        {{ t.label }}
        <span class="ex-count">{{ exCounts[t.key] || 0 }}</span>
      </button>
      <div class="ex-loading" v-if="loading">⟳ 刷新中</div>
    </div>

    <!-- 品种网格 -->
    <div class="mkt-grid">
      <div
        v-for="c in filteredCards"
        :key="c.symbol"
        :class="[
          'mkt-card',
          c.direction === 'long' ? 'up' : c.direction === 'short' ? 'dn' : 'flat',
          { active: market.curSym === c.symbol }
        ]"
        @click="selectSym(c.symbol)"
      >
        <!-- 信号点 -->
        <span
          v-if="c.hasSignal"
          :class="['mkt-sig-dot', c.signalType === 'entry_long' ? 'long' : c.signalType === 'entry_short' ? 'short' : 'has-pos']"
        />
        <!-- 合约角标 -->
        <div class="mkt-contract-badge" :class="{ main: c.hasMain }">
          📋 {{ c.contractsCount || 0 }}
        </div>
        <div class="mkt-sym">
          <strong>{{ c.symbol }}</strong>
          <span class="mkt-name">{{ c.name }}</span>
        </div>
        <div class="mkt-price">{{ fmtPrice(c.current_price) }}</div>
        <div class="mkt-change">
          <span class="chg">{{ fmtChg(c.change, c.change_pct) }}</span>
        </div>
      </div>
      <div v-if="!loading && filteredCards.length === 0" class="empty">
        当前交易所暂无品种
      </div>
    </div>

    <!-- 选中品种的详情（v-if 控制，无 router） -->
    <SymbolDetail v-if="market.curSym" />

    <!-- 手动交易测试触发器（开发期，Phase C2 端到端验证用） -->
    <section class="test-triggers">
      <h3>🧪 手动交易测试（开发期）</h3>
      <div class="trigger-row">
        <button
          @click="
            modal.open('OpenSessionModal', {
              signal: { symbol: 'AG', direction: 'long', basis_price: 17500, atr: 200 },
              title: '开仓测试'
            })
          "
        >
          开仓
        </button>
        <button
          @click="
            modal.open(
              'AddUnitModal',
              {
                sessionId: 'test-session-id',
                currentUnits: 2,
                direction: 'long',
                title: '加仓测试'
              }
            )
          "
        >
          加仓
        </button>
        <button
          @click="
            modal.open('ReduceUnitModal', {
              sessionId: 'test-session-id',
              units: [
                { unit_id: 'u1', unit_no: 1, hand_count: 1, is_active: true },
                { unit_id: 'u2', unit_no: 2, hand_count: 1, is_active: true }
              ],
              title: '减仓测试'
            })
          "
        >
          减仓
        </button>
        <button
          @click="
            modal.open('CloseAllModal', {
              sessionId: 'test-session-id',
              title: '全平测试'
            })
          "
        >
          全平
        </button>
        <button
          @click="
            modal.open('LineOverrideModal', {
              sessionId: 'test-session-id',
              currentLines: { entry: 17500, stop_loss: 17000, take_profit: 18000, warning: 17600 },
              title: '调价测试'
            })
          "
        >
          调价
        </button>
      </div>
    </section>
  </section>
</template>

<style scoped>
.market-grid-wrap { display: flex; flex-direction: column; gap: 8px; }
.exchange-bar {
  background: var(--card); border: 1px solid var(--border); border-radius: 6px;
  display: flex; gap: 2px; padding: 4px;
}
.ex-tab {
  padding: 8px 14px; font-size: 12px; color: var(--muted);
  background: transparent; border: none; border-bottom: 2px solid transparent;
  cursor: pointer; transition: all 0.15s;
  display: flex; align-items: center; gap: 6px;
}
.ex-tab:hover { color: var(--text); }
.ex-tab.active { color: var(--accent); border-bottom-color: var(--accent); font-weight: 600; }
.ex-count { font-size: 10px; color: var(--muted); padding: 1px 5px; background: var(--bg); border-radius: 8px; }
.ex-loading { margin-left: auto; padding: 8px; font-size: 11px; color: var(--muted); }

.mkt-grid {
  display: grid; grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: 6px;
}
.mkt-card {
  position: relative; background: var(--card); border: 1px solid var(--border);
  border-radius: 6px; padding: 10px 12px; cursor: pointer; transition: all 0.15s;
  display: flex; flex-direction: column; gap: 4px; min-height: 78px;
}
.mkt-card:hover { border-color: var(--accent); transform: translateY(-1px); }
.mkt-card.active { border-color: var(--accent); box-shadow: 0 0 0 1px var(--accent); }
.mkt-card.up { border-top: 2px solid var(--buy); }
.mkt-card.dn { border-top: 2px solid var(--sell); }
.mkt-card.flat { border-top: 2px solid var(--border); }

.mkt-sig-dot {
  position: absolute; top: 6px; right: 6px;
  width: 8px; height: 8px; border-radius: 50%;
}
.mkt-sig-dot.long { background: var(--buy); }
.mkt-sig-dot.short { background: var(--sell); }
.mkt-sig-dot.has-pos { background: var(--warn); }

.mkt-contract-badge {
  position: absolute; bottom: 4px; right: 6px;
  font-size: 9px; color: var(--muted);
  background: var(--bg); padding: 1px 4px; border-radius: 3px;
}
.mkt-contract-badge.main { color: var(--accent); }

.mkt-sym { display: flex; align-items: baseline; gap: 6px; }
.mkt-sym strong { font-size: 14px; color: var(--text); }
.mkt-name { font-size: 10px; color: var(--muted); }

.mkt-price { font-size: 15px; font-weight: 600; font-family: -apple-system, 'SF Mono', monospace; }
.mkt-card.up .mkt-price { color: var(--buy); }
.mkt-card.dn .mkt-price { color: var(--sell); }

.mkt-change .chg { font-size: 11px; color: var(--muted); }
.mkt-card.up .mkt-change .chg { color: var(--buy); }
.mkt-card.dn .mkt-change .chg { color: var(--sell); }

.empty { padding: 40px; text-align: center; color: var(--muted); font-size: 12px; grid-column: 1/-1; }

.test-triggers {
  background: var(--card);
  border: 1px dashed var(--border);
  border-radius: 8px;
  padding: 12px;
  margin-top: 16px;
}
.test-triggers h3 {
  font-size: 12px;
  color: var(--muted);
  margin: 0 0 8px 0;
}
.trigger-row {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}
.trigger-row button {
  background: var(--bg);
  border: 1px solid var(--border);
  color: var(--text);
  padding: 6px 12px;
  border-radius: 4px;
  font-size: 11px;
  cursor: pointer;
}
.trigger-row button:hover {
  border-color: var(--accent);
}
</style>
