<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useToast } from '@/composables/useToast'
import { marketApi } from '@/services/market'
import { useMarketStore } from '@/stores/market'
import { ALL_SYMBOLS } from '@/config/symbols'
import MarketGrid from '@/views/MarketGrid.vue'
import SymbolDetail from '@/views/SymbolDetail.vue'
import AccountCenterModal from '@/views/AccountCenterModal.vue'
import ActionModalHost from '@/views/ActionModalHost.vue'
import ToastHost from '@/components/ToastHost.vue'
import MarketDataSync from '@/views/MarketDataSync.vue'  // sq-0009-p6

const apiStatus = ref<'unknown' | 'ok' | 'fail'>('unknown')
const signalCount = ref(0)
const buildTime = new Date().toISOString()
const showAccount = ref(false)
const showSync = ref(false)  // sq-0009-p6: 行情数据同步中心开关
const toast = useToast()
const market = useMarketStore()

onMounted(async () => {
  try {
    const r = await marketApi.signalsAll()
    signalCount.value = Array.isArray(r) ? r.length : 0
    apiStatus.value = 'ok'
    toast.push({ kind: 'success', title: '✅ Phase C1 视图层就绪', body: `signals=${signalCount.value}, symbols=${ALL_SYMBOLS.length}` })
  } catch (e) {
    apiStatus.value = 'fail'
    toast.push({ kind: 'error', title: 'API 连接失败', body: String(e) })
  }
})
</script>

<template>
  <div class="app-shell">
    <header class="app-header">
      <h1>📈 Stock Quant v2.0</h1>
      <span class="subtitle">Vue 3 + 11 view 组件</span>
      <button class="acct-btn" @click="showSync = !showSync">
        {{ showSync ? '← 返回行情' : '📊 行情数据同步' }}
      </button>
      <button class="acct-btn" @click="showAccount = true">账户中心</button>
    </header>
    <main class="app-main">
      <MarketDataSync v-if="showSync" />
      <template v-else>
        <MarketGrid />
        <SymbolDetail v-if="market.curSym" />
      </template>
    </main>
    <AccountCenterModal :open="showAccount" @close="showAccount = false" />
    <ActionModalHost />
    <ToastHost />
  </div>
</template>

<style scoped>
.app-shell { min-height: 100vh; background: var(--bg); color: var(--text); font-family: -apple-system, 'PingFang SC', sans-serif; display: flex; flex-direction: column; }
.app-header { background: var(--card); border-bottom: 1px solid var(--border); padding: 12px 20px; display: flex; align-items: center; gap: 16px; }
.app-header h1 { font-size: 16px; color: var(--accent); margin: 0; }
.subtitle { color: var(--muted); font-size: 12px; flex: 1; }
.acct-btn { background: var(--accent); color: #fff; border: none; padding: 6px 14px; border-radius: 4px; font-size: 12px; }
.app-main { flex: 1; padding: 12px; overflow-y: auto; }
</style>
