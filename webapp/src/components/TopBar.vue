<script setup lang="ts">
// v0.18.14 data-model Phase 2 收尾：顶部栏外壳
// 包含 5 Tab 切换 + 策略/账户下拉 + 4 操作按钮 + 入口按钮
import { ref } from 'vue'
import { useStrategyStore } from '@/stores/strategy'
import { useAccountStore } from '@/stores/account'
import { useModal } from '@/composables/useModal'

const strategy = useStrategyStore()
const account = useAccountStore()
const modal = useModal()

// 5 Tab 切换（由父组件 App.vue 控制 + emit 通知）
const props = defineProps<{
  activeTab: 'signal' | 'sim' | 'live' | 'backtest' | 'session'
}>()

const emit = defineEmits<{
  (e: 'change-tab', tab: 'signal' | 'sim' | 'live' | 'backtest' | 'session'): void
  (e: 'toggle-sync'): void
  (e: 'open-account'): void
}>()

const tabs = [
  { id: 'signal', label: '信号' },
  { id: 'sim', label: '模拟' },
  { id: 'live', label: '真实' },
  { id: 'backtest', label: '回测' },
  { id: 'session', label: 'Session' }
] as const

// 4 操作按钮（触发对应 modal）
function openModal(name: string) {
  modal.open(name)
}

function onTabClick(tab: typeof props.activeTab) {
  emit('change-tab', tab)
}
</script>

<template>
  <header class="topbar">
    <div class="topbar-brand">
      <h1>📈 Stock Quant v2.0</h1>
      <span class="subtitle">Vue 3 + 5 Tab + 多策略/多账户</span>
    </div>

    <!-- 5 Tab 切换 -->
    <nav class="tabs">
      <button v-for="t in tabs" :key="t.id"
              :class="['tab-btn', { active: props.activeTab === t.id }]"
              @click="onTabClick(t.id)">
        {{ t.label }}
      </button>
    </nav>

    <!-- 策略下拉 -->
    <label class="topbar-label">
      策略:
      <select class="topbar-select" :value="strategy.current?.strategy_id ?? ''"
              @change="strategy.setCurrent({ strategy_id: ($event.target as HTMLSelectElement).value } as any)">
        <option value="">-- 选策略 --</option>
        <option v-for="s in strategy.list" :key="s.strategy_id" :value="s.strategy_id">
          {{ s.name }}{{ s.version ? ' v' + s.version : '' }}
        </option>
      </select>
    </label>

    <!-- 账户下拉（mock 3 个 sim 账户）-->
    <label class="topbar-label">
      账户:
      <select class="topbar-select" :value="account.current"
              @change="account.setCurrent(($event.target as HTMLSelectElement).value)">
        <option v-for="a in ['sim_default', 'sim_user1', 'sim_user2']" :key="a" :value="a">
          {{ a }}
        </option>
      </select>
    </label>

    <!-- 4 操作按钮（建仓/加仓/减仓/全平）-->
    <div class="action-group">
      <button class="action-btn" @click="openModal('OpenSessionModal')">➕建仓</button>
      <button class="action-btn" @click="openModal('AddUnitModal')">➕加仓</button>
      <button class="action-btn" @click="openModal('ReduceUnitModal')">➖减仓</button>
      <button class="action-btn" @click="openModal('CloseAllModal')">🔒全平</button>
    </div>

    <!-- 入口按钮（行情同步 + 账户中心）-->
    <div class="entry-group">
      <button class="entry-btn" @click="emit('toggle-sync')">📊 行情同步</button>
      <button class="entry-btn" @click="emit('open-account')">账户中心</button>
    </div>
  </header>
</template>

<style scoped>
.topbar {
  background: var(--card);
  border-bottom: 1px solid var(--border);
  padding: 8px 16px;
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  font-size: 12px;
}
.topbar-brand { display: flex; align-items: center; gap: 8px; }
.topbar-brand h1 { font-size: 14px; color: var(--accent); margin: 0; }
.subtitle { color: var(--muted); font-size: 11px; }
.tabs { display: flex; gap: 4px; }
.tab-btn {
  background: transparent;
  border: 1px solid var(--border);
  color: var(--muted);
  padding: 4px 12px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 12px;
}
.tab-btn:hover { border-color: var(--accent); }
.tab-btn.active {
  background: var(--accent);
  color: #fff;
  border-color: var(--accent);
}
.topbar-label {
  display: flex;
  align-items: center;
  gap: 4px;
  color: var(--muted);
  font-size: 11px;
}
.topbar-select {
  background: var(--bg);
  border: 1px solid var(--border);
  color: var(--text);
  padding: 3px 6px;
  border-radius: 3px;
  font-size: 11px;
  min-width: 80px;
}
.action-group, .entry-group { display: flex; gap: 4px; }
.action-btn {
  background: var(--card-hover, #2a2a2a);
  color: var(--text);
  border: 1px solid var(--border);
  padding: 4px 8px;
  border-radius: 3px;
  font-size: 11px;
  cursor: pointer;
}
.action-btn:hover { border-color: var(--accent); }
.entry-btn {
  background: var(--accent);
  color: #fff;
  border: none;
  padding: 4px 12px;
  border-radius: 3px;
  font-size: 11px;
  cursor: pointer;
}
.entry-btn:hover { opacity: 0.9; }
</style>
