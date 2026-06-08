<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import { useMarketStore } from '@/stores/market'
import { useToast } from '@/composables/useToast'
import { marketApi } from '@/services/market'
import { sessionApi } from '@/services/session'
import { useKLineData, type KLinePeriod } from '@/composables/useKLineData'
import KLineChart from '@/components/KLineChart.vue'
import SignalTimeline from '@/views/SignalTimeline.vue'
import PriceLineBar from '@/views/PriceLineBar.vue'
import UnitDetail from '@/views/UnitDetail.vue'
import TradeProcessTimeline from '@/views/TradeProcessTimeline.vue'

interface Position {
  total_units: number
  direction: 'long' | 'short' | ''
  symbol?: string
  [k: string]: any
}

const market = useMarketStore()
const toast = useToast()
const kline = useKLineData()

const position = ref<Position | null>(null)
const signals = ref<any[]>([])
const openSession = ref<any | null>(null)
const lines = ref<{ stop_loss?: number; add?: number; take_profit?: number; warning?: number; entry?: number }>({})
const currentPrice = ref<number>(0)
const loading = ref(false)
const chartError = ref<string>('')
const chartPeriod = ref<KLinePeriod>('15min')
const chartDays = ref<number>(7)  // sq-0009-round-3 commit 6

const curSym = computed(() => market.curSym)

// 周期 × 范围联动约束（commit 6）
// 5/15/30/60min 受 akshare 数据源限制（≤10 天），允许用户拉更远但会得到空
// 但 UI 提示：分时周期禁用 >180 天的选项（半年已是分时极限）
const minutePeriods: KLinePeriod[] = ['5min', '15min', '30min', '60min']
const isMinutePeriod = computed(() => minutePeriods.includes(chartPeriod.value))
const daysOptions = computed(() => {
  if (isMinutePeriod.value) {
    return [7, 30, 180]   // 分时周期：7天 / 30天 / 半年
  } else {
    return [7, 30, 180, 365, 730, 1095]  // 日线：7天/30天/半年/1年/2年/3年
  }
})
// 切到分时周期时，如果当前 days 超出范围，自动降级
watch(chartPeriod, () => {
  if (isMinutePeriod.value && chartDays.value > 180) {
    chartDays.value = 7
  }
})

watch(
  () => market.curSym,
  async (sym) => {
    if (sym) await loadDetail(sym)
  },
  { immediate: true }
)

// 周期/范围切换时重查 K 线
watch([chartPeriod, chartDays], async () => {
  if (curSym.value) await kline.fetchKLineData(curSym.value, chartPeriod.value, chartDays.value)
})

async function loadDetail(sym: string) {
  loading.value = true
  chartError.value = ''
  try {
    // 1. signals
    const sigResp = await marketApi.signalsBySymbol(sym)
    const dir = sigResp.direction === 1 || sigResp.direction === 'long'
      ? 'long' : sigResp.direction === 2 || sigResp.direction === 'short' ? 'short' : ''
    currentPrice.value = sigResp.current_price ?? 0
    market.setMarketData(sym, { ...sigResp, direction: dir })

    // 2. signals 时间线（海龟）
    try {
      const tl = await marketApi.turtleSignalsBySymbol(sym, 7)
      signals.value = Array.isArray(tl) ? tl : []
    } catch {
      signals.value = []
    }

    // 3. 拉 K 线（commit 4：解锁 lightweight-charts + commit 6：days 选择）
    try {
      await kline.fetchKLineData(sym, chartPeriod.value, chartDays.value)
    } catch (e) {
      chartError.value = 'K线数据加载失败'
    }

    // 4. position (用 sessionApi 替代)
    try {
      const sessList = await sessionApi.list({ symbol: sym, status: 'open', limit: 1 })
      const sList = sessList.sessions || []
      if (sList.length > 0) {
        openSession.value = sList[0]
        // 拉价格线
        try {
          const lns = await sessionApi.lines(sList[0].session_id)
          lines.value = {
            stop_loss: lns.lines?.stop_loss,
            add: lns.lines?.add,
            take_profit: lns.lines?.take_profit,
            warning: lns.lines?.warning ?? lns.lines?.exit_20,
            entry: lns.entry_price
          }
        } catch {
          lines.value = { entry: openSession.value?.entry_price }
        }
      } else {
        openSession.value = null
        lines.value = {}
      }
      position.value = {
        total_units: sList[0]?.current_units || 0,
        direction: dir,
        symbol: sym
      }
    } catch {
      position.value = { total_units: 0, direction: dir, symbol: sym }
    }
  } catch (e) {
    toast.push({ kind: 'error', title: '详情加载失败', body: String(e) })
  } finally {
    loading.value = false
  }
}

function closeDetail() {
  market.setSym(null)
}

function fmtPrice(n?: number): string {
  return n == null ? '--' : Number(n).toLocaleString(undefined, { maximumFractionDigits: 2 })
}
</script>

<template>
  <section v-if="curSym" class="symbol-detail">
    <header class="detail-head">
      <div class="detail-title">
        <span class="sym-name">{{ curSym }}</span>
        <span class="sym-contract" v-if="market.marketData[curSym]?.contract_code">
          📋 {{ market.marketData[curSym].contract_code }}
        </span>
        <span
          :class="['sym-badge', market.marketData[curSym]?.direction || 'hold']"
        >
          <template v-if="market.marketData[curSym]?.direction === 'long'">▲ 做多信号</template>
          <template v-else-if="market.marketData[curSym]?.direction === 'short'">▼ 做空信号</template>
          <template v-else>— 观望</template>
        </span>
      </div>
      <button class="close-btn" @click="closeDetail" aria-label="关闭">×</button>
    </header>

    <div class="detail-stats">
      <div class="stat">
        <span class="lbl">最新价</span>
        <span :class="['val', market.marketData[curSym]?.direction === 'long' ? 'up' : market.marketData[curSym]?.direction === 'short' ? 'dn' : '']">
          {{ fmtPrice(currentPrice) }}
        </span>
      </div>
      <div class="stat">
        <span class="lbl">ATR</span>
        <span class="val">{{ fmtPrice(market.marketData[curSym]?.atr) }}</span>
      </div>
      <div class="stat">
        <span class="lbl">55H</span>
        <span class="val">{{ fmtPrice(market.marketData[curSym]?.high_55) }}</span>
      </div>
      <div class="stat">
        <span class="lbl">55L</span>
        <span class="val">{{ fmtPrice(market.marketData[curSym]?.low_55) }}</span>
      </div>
      <div class="stat">
        <span class="lbl">日期</span>
        <span class="val">{{ market.marketData[curSym]?.date || '--' }}</span>
      </div>
    </div>

    <div class="detail-grid">
      <!-- 左：K 线图（commit 4：解锁 lightweight-charts + commit 6：days 选择）-->
      <div class="col col-chart">
        <h4 class="col-title">
          K 线图
          <select v-model="chartPeriod" class="period-select">
            <option value="5min">5min</option>
            <option value="15min">15min</option>
            <option value="30min">30min</option>
            <option value="60min">60min</option>
          </select>
          <select v-model.number="chartDays" class="period-select" :title="isMinutePeriod ? '分时周期最长 180 天（aksource 数据源仅 ~10 天）' : '日线最长 3 年'">
            <option v-for="d in daysOptions" :key="d" :value="d">
              {{ d === 7 ? '7 天' : d === 30 ? '30 天' : d === 180 ? '半年' : d === 365 ? '1 年' : d === 730 ? '2 年' : d === 1095 ? '3 年' : `${d} 天` }}
            </option>
          </select>
          <span v-if="kline.source.value === 'cache'" class="src-tag src-cache">🟢 缓存</span>
          <span v-else-if="kline.source.value === 'resample'" class="src-tag src-resample">🟡 resample</span>
          <span v-else-if="kline.source.value === 'empty'" class="src-tag src-empty">⚪ 空</span>
        </h4>
        <KLineChart :data="kline.data.value" :height="320" />
      </div>

      <!-- 中：持仓 + Session -->
      <div class="col col-mid">
        <h4 class="col-title">持仓 & 当前 Session</h4>
        <div v-if="position && position.total_units > 0" class="pos-item">
          <span><strong>{{ curSym }}</strong></span>
          <span :class="['pos-dir', position.direction]">
            {{ position.direction === 'long' ? '▲ 做多' : position.direction === 'short' ? '▼ 做空' : '—' }}
          </span>
          <span class="pos-units">{{ position.total_units }} 单位</span>
        </div>
        <div v-else class="pos-empty">当前无持仓</div>

        <div v-if="openSession" class="sess-info">
          <div class="row"><span class="lbl">Session</span><span class="val">{{ openSession.session_id?.slice(0, 8) || '--' }}</span></div>
          <div class="row"><span class="lbl">入场价</span><span class="val">{{ fmtPrice(openSession.entry_price) }}</span></div>
          <div class="row"><span class="lbl">状态</span><span class="val">{{ openSession.status || '--' }}</span></div>
          <div class="row"><span class="lbl">Units</span><span class="val">{{ openSession.current_units || 0 }}/{{ openSession.total_units || 4 }}</span></div>
        </div>
        <div v-else class="sess-empty">无打开 Session</div>

        <!-- 价格线 -->
        <PriceLineBar
          v-if="openSession"
          :lines="lines"
          :current-price="currentPrice"
        />
      </div>

      <!-- 右：信号时间线 -->
      <div class="col col-sig">
        <h4 class="col-title">海龟信号
          <span class="count" v-if="signals.length">{{ signals.length }} 条</span>
        </h4>
        <SignalTimeline :signals="signals" />
      </div>
    </div>

    <!-- 4 Unit + 交易过程 -->
    <div v-if="openSession" class="detail-extra">
      <UnitDetail :session-id="openSession.session_id" />
      <TradeProcessTimeline :session-id="openSession.session_id" />
    </div>
  </section>
</template>

<style scoped>
.symbol-detail {
  background: var(--card); border: 1px solid var(--border); border-radius: 8px;
  padding: 14px 16px; margin-top: 12px;
  display: flex; flex-direction: column; gap: 12px;
}
.detail-head { display: flex; align-items: center; justify-content: space-between; }
.detail-title { display: flex; align-items: center; gap: 10px; }
.sym-name { font-size: 18px; font-weight: 700; color: var(--text); }
.sym-contract { font-size: 11px; color: var(--muted); }
.sym-badge {
  padding: 3px 8px; border-radius: 3px; font-size: 11px; font-weight: 600;
}
.sym-badge.long { background: rgba(38,196,133,0.18); color: var(--buy); }
.sym-badge.short { background: rgba(240,86,106,0.18); color: var(--sell); }
.sym-badge.hold { background: rgba(107,114,128,0.18); color: var(--muted); }
.close-btn { background: transparent; border: none; color: var(--muted); font-size: 22px; cursor: pointer; padding: 0 8px; }
.close-btn:hover { color: var(--text); }

.detail-stats { display: flex; gap: 24px; padding-bottom: 10px; border-bottom: 1px solid var(--border); }
.stat { display: flex; flex-direction: column; gap: 2px; }
.stat .lbl { font-size: 10px; color: var(--muted); }
.stat .val { font-size: 13px; font-weight: 600; color: var(--text); }
.stat .val.up { color: var(--buy); }
.stat .val.dn { color: var(--sell); }

.detail-grid {
  display: grid; grid-template-columns: 2fr 1.4fr 1fr; gap: 12px;
}
.col { background: var(--bg); border-radius: 6px; padding: 10px; min-height: 200px; }
.col-title { font-size: 11px; color: var(--muted); margin: 0 0 8px 0; display: flex; align-items: center; gap: 6px; }
.col-title .count { color: var(--accent); }

.chart-placeholder {
  height: 320px; background: var(--card); border-radius: 4px;
  display: flex; align-items: center; justify-content: center;
  color: var(--muted); font-size: 12px;
}
.period-select {
  margin-left: 8px;
  padding: 2px 6px;
  font-size: 11px;
  background: var(--bg);
  color: var(--text);
  border: 1px solid var(--border);
  border-radius: 3px;
}
.src-tag {
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 3px;
  margin-left: auto;
}
.src-cache { background: rgba(34,197,94,0.15); color: #22c55e; }
.src-resample { background: rgba(234,179,8,0.15); color: #eab308; }
.src-empty { background: rgba(156,163,175,0.15); color: #9ca3af; }

.pos-item { display: flex; align-items: center; gap: 10px; padding: 6px 0; }
.pos-dir.long { color: var(--buy); font-weight: 600; }
.pos-dir.short { color: var(--sell); font-weight: 600; }
.pos-units { color: var(--accent); font-weight: 600; }
.pos-empty, .sess-empty { color: var(--muted); font-size: 12px; padding: 8px 0; text-align: center; }

.sess-info { margin-top: 10px; display: flex; flex-direction: column; gap: 4px; }
.sess-info .row { display: flex; justify-content: space-between; font-size: 12px; }
.sess-info .lbl { color: var(--muted); }
.sess-info .val { color: var(--text); font-weight: 600; }

.detail-extra { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }

@media (max-width: 1100px) {
  .detail-grid { grid-template-columns: 1fr; }
  .detail-extra { grid-template-columns: 1fr; }
}
</style>
