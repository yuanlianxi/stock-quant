<script setup lang="ts">
// v0.18.14 data-model Phase 2 收尾：App.vue 集成 TopBar + 5 Tab 切换
import { ref, onMounted } from 'vue'
import { useToast } from '@/composables/useToast'
import { marketApi } from '@/services/market'
import { strategyApi } from '@/services/strategy'
import { useMarketStore } from '@/stores/market'
import { useStrategyStore } from '@/stores/strategy'
import { ALL_SYMBOLS } from '@/config/symbols'
import TopBar from '@/components/TopBar.vue'
import MarketGrid from '@/views/MarketGrid.vue'
import SymbolDetail from '@/views/SymbolDetail.vue'
import AccountCenterModal from '@/views/AccountCenterModal.vue'
import ActionModalHost from '@/views/ActionModalHost.vue'
import ToastHost from '@/components/ToastHost.vue'
import MarketDataSync from '@/views/MarketDataSync.vue'

const apiStatus = ref<'unknown' | 'ok' | 'fail'>('unknown')
const signalCount = ref(0)
const showAccount = ref(false)
const showSync = ref(false)

// 5 Tab 切换（v0.18.14 data-model Phase 2 收尾）
const activeTab = ref<'signal' | 'sim' | 'live' | 'backtest' | 'session'>('sim')

const toast = useToast()
const market = useMarketStore()
const strategy = useStrategyStore()

onMounted(async () => {
  try {
    const r = await marketApi.signalsAll()
    signalCount.value = Array.isArray(r) ? r.length : 0
    apiStatus.value = 'ok'
    toast.push({
      kind: 'success',
      title: '✅ v0.18.14 加载完成',
      body: `signals=${signalCount.value}, symbols=${ALL_SYMBOLS.length}, 5 Tab + 4 操作`
    })
  } catch (e) {
    apiStatus.value = 'fail'
    toast.push({ kind: 'error', title: 'API 连接失败', body: String(e) })
  }

  // 加载策略列表（顶部栏下拉）
  try {
    const sl = await strategyApi.list()
    if (Array.isArray(sl?.strategies)) {
      strategy.setList(sl.strategies as any)
      // 默认选第一个
      if (sl.strategies.length > 0) {
        strategy.setCurrent(sl.strategies[0] as any)
      }
    }
  } catch (e) {
    console.warn('策略列表加载失败（顶部栏下拉会空）:', e)
  }
})

function onTopbarToggleSync() { showSync.value = !showSync.value }
function onTopbarOpenAccount() { showAccount.value = true }
</script>

<template>
  <div class="app-shell">
    <TopBar
      :active-tab="activeTab"
      @change-tab="activeTab = $event"
      @toggle-sync="onTopbarToggleSync"
      @open-account="onTopbarOpenAccount"
    />
    <main class="app-main">
      <MarketDataSync v-if="showSync" />
      <template v-else>
        <!-- 5 Tab 切换显示对应 view（v0.18.14 Phase 2 收尾）-->
        <template v-if="activeTab === 'sim'">
          <MarketGrid />
          <SymbolDetail v-if="market.curSym" />
        </template>
        <template v-else>
          <!-- 暂未派 Phase 3 实施，4 个 Tab 用 placeholder -->
          <div class="placeholder">
            <h2 v-if="activeTab === 'signal'">📡 信号 Tab</h2>
            <h2 v-else-if="activeTab === 'live'">💼 真实 Tab</h2>
            <h2 v-else-if="activeTab === 'backtest'">📊 回测 Tab</h2>
            <h2 v-else-if="activeTab === 'session'">📋 Session Tab</h2>
            <p>占位区：等 data-model Phase 3 实施后接对应 view。</p>
            <p class="hint">v0.18.14 Phase 2 收尾：顶部栏外壳就绪（5 Tab 切换 + 策略/账户下拉 + 4 操作按钮）</p>
            <p class="hint">模拟 Tab（默认）：MarketGrid + SymbolDetail（已可用）</p>
          </div>
        </template>
      </template>
    </main>
    <AccountCenterModal :open="showAccount" @close="showAccount = false" />
    <ActionModalHost />
    <ToastHost />
  </div>
</template>

<style scoped>
.app-shell { min-height: 100vh; background: var(--bg); color: var(--text); font-family: -apple-system, 'PingFang SC', sans-serif; display: flex; flex-direction: column; }
.app-main { flex: 1; padding: 12px; overflow-y: auto; }
.placeholder {
  padding: 40px;
  text-align: center;
  color: var(--muted);
  border: 1px dashed var(--border);
  border-radius: 6px;
  margin: 12px 0;
}
</style>
