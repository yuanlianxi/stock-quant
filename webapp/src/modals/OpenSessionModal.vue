<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useToast } from '@/composables/useToast'
import { sessionApi } from '@/services/session'
import { strategyApi } from '@/services/strategy'
import SessionFormField from './SessionFormField.vue'

const props = defineProps<{
  signal: {
    symbol: string
    direction: 'long' | 'short'
    basis_price?: number
    atr?: number
    signal_id?: string | number
  }
}>()
const emit = defineEmits<{ (e: 'close'): void }>()

const accountId = ref('sim_default')
const strategyId = ref('turtle_v1')
const handCount = ref(1)
const entryPrice = ref<number>(props.signal.basis_price ?? 0)
const stopLoss = ref<number>(0)
const takeProfit = ref<number>(0)
const warning = ref<number>(0)
const submitLoading = ref(false)
const strategies = ref<Array<{ strategy_id: string; name?: string; is_active?: boolean }>>([])

onMounted(async () => {
  try {
    const r = await strategyApi.list(true)
    strategies.value = r.strategies || []
  } catch {
    // 静默：策略列表不可用时保留默认值
  }
})

const canSubmit = computed(() => handCount.value > 0 && entryPrice.value > 0)
const directionLabel = computed(() => (props.signal.direction === 'long' ? '做多' : '做空'))

async function submit() {
  if (!canSubmit.value) return
  submitLoading.value = true
  try {
    const r = await sessionApi.open({
      account_id: accountId.value,
      symbol: props.signal.symbol,
      direction: props.signal.direction,
      strategy_id: strategyId.value,
      entry_price: entryPrice.value,
      hand_count: handCount.value,
      stop_loss: stopLoss.value || null,
      take_profit: takeProfit.value || null,
      warning: warning.value || null
    })
    const sid = (r && (r.session_id || r.id)) || '未知'
    useToast().push({ kind: 'success', title: '✅ 开仓成功', body: `session_id=${sid}` })
    emit('close')
  } catch (e) {
    useToast().push({ kind: 'error', title: '开仓失败', body: String(e) })
  } finally {
    submitLoading.value = false
  }
}
</script>

<template>
  <div class="modal-host-inner">
    <h3 class="title">📈 开仓 · {{ signal.symbol }} · {{ directionLabel }}</h3>
    <div class="form-row">
      <SessionFormField label="账户 ID" type="text" v-model="accountId" />
      <label class="field">
        <span class="lbl">策略 ID</span>
        <select v-model="strategyId" class="input">
          <option
            v-for="s in strategies"
            :key="s.strategy_id"
            :value="s.strategy_id"
          >
            {{ s.strategy_id }}{{ s.name ? ' · ' + s.name : '' }}{{ s.is_active ? '' : ' (停用)' }}
          </option>
          <option v-if="strategies.length === 0" value="turtle_v1">turtle_v1</option>
        </select>
      </label>
    </div>
    <div class="form-row">
      <SessionFormField label="数量（手）" :min="1" v-model="handCount" />
      <SessionFormField label="入场价" :step="0.01" v-model="entryPrice" />
    </div>
    <div class="form-row">
      <SessionFormField
        label="止损价（可选）"
        :step="0.01"
        v-model="stopLoss"
        placeholder="0=不设"
      />
      <SessionFormField
        label="止盈价（可选）"
        :step="0.01"
        v-model="takeProfit"
        placeholder="0=不设"
      />
    </div>
    <div class="form-row">
      <SessionFormField
        label="预警价（可选）"
        :step="0.01"
        v-model="warning"
        placeholder="0=不设"
      />
    </div>
    <div class="actions">
      <button class="btn cancel" @click="emit('close')">取消</button>
      <button
        class="btn confirm"
        :disabled="!canSubmit || submitLoading"
        @click="submit"
      >
        {{ submitLoading ? '提交中...' : '确认开仓' }}
      </button>
    </div>
  </div>
</template>

<style scoped>
.modal-host-inner {
  display: flex;
  flex-direction: column;
  gap: 10px;
  min-width: 360px;
}
.title {
  font-size: 15px;
  color: var(--accent);
  margin: 0 0 4px 0;
}
.form-row {
  display: flex;
  gap: 12px;
}
.field {
  display: flex;
  flex-direction: column;
  gap: 4px;
  flex: 1;
}
.lbl {
  font-size: 11px;
  color: var(--muted);
}
.input {
  background: var(--bg);
  border: 1px solid var(--border);
  color: var(--text);
  padding: 6px 8px;
  border-radius: 4px;
  font-size: 12px;
  outline: none;
}
.input:focus {
  border-color: var(--accent);
}
.actions {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
  margin-top: 6px;
}
.btn {
  padding: 6px 14px;
  border-radius: 4px;
  font-size: 12px;
  border: 1px solid var(--border);
  background: var(--card);
  color: var(--text);
  cursor: pointer;
}
.btn.confirm {
  background: var(--buy);
  color: #fff;
  border-color: var(--buy);
}
.btn.confirm:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.btn.cancel {
  background: transparent;
}
</style>
