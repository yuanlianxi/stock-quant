<script setup lang="ts">
import { ref, computed } from 'vue'
import { useToast } from '@/composables/useToast'
import { sessionApi } from '@/services/session'
import SessionFormField from './SessionFormField.vue'

interface Unit {
  unit_id: string
  unit_no: number
  hand_count: number
  is_active: boolean
}

const props = defineProps<{
  sessionId: string
  units: Unit[]
}>()
const emit = defineEmits<{ (e: 'close'): void }>()

const selectedUnitId = ref<string>(
  (props.units.find(u => u.is_active) || props.units[0])?.unit_id || ''
)
const handCount = ref(1)
const orderPrice = ref<number>(0)
const submitLoading = ref(false)

const selectedUnit = computed<Unit | undefined>(() =>
  props.units.find(u => u.unit_id === selectedUnitId.value)
)
const canSubmit = computed(
  () => !!selectedUnitId.value && handCount.value > 0 && orderPrice.value > 0
)

async function submit() {
  if (!canSubmit.value) return
  submitLoading.value = true
  try {
    await sessionApi.reduceOrder(props.sessionId, {
      unit_id: selectedUnitId.value,
      hand_count: handCount.value,
      order_price: orderPrice.value
    })
    useToast().push({
      kind: 'success',
      title: '✅ 减仓成功',
      body: `unit=${selectedUnitId.value.slice(0, 8)}`
    })
    emit('close')
  } catch (e) {
    useToast().push({ kind: 'error', title: '减仓失败', body: String(e) })
  } finally {
    submitLoading.value = false
  }
}
</script>

<template>
  <div class="modal-host-inner">
    <h3 class="title">➖ 减仓 · session {{ sessionId.slice(0, 8) }}</h3>
    <div class="form-row">
      <label class="field">
        <span class="lbl">选择 Unit</span>
        <select v-model="selectedUnitId" class="input">
          <option v-for="u in units" :key="u.unit_id" :value="u.unit_id">
            Unit #{{ u.unit_id.slice(0, 4) }} · {{ u.hand_count }} 手 ·
            {{ u.is_active ? '持仓中' : '已平' }}
          </option>
          <option v-if="units.length === 0" value="" disabled>无 Unit 可选</option>
        </select>
      </label>
    </div>
    <div class="form-row">
      <SessionFormField label="减仓手数" :min="1" v-model="handCount" />
      <SessionFormField label="平仓价" :step="0.01" v-model="orderPrice" />
    </div>
    <p v-if="selectedUnit" class="hint">
      当前选中：Unit #{{ selectedUnit.unit_id.slice(0, 4) }}（{{ selectedUnit.hand_count }} 手）
    </p>
    <div class="actions">
      <button class="btn cancel" @click="emit('close')">取消</button>
      <button
        class="btn confirm"
        :disabled="!canSubmit || submitLoading"
        @click="submit"
      >
        {{ submitLoading ? '提交中...' : '确认减仓' }}
      </button>
    </div>
  </div>
</template>

<style scoped>
.modal-host-inner {
  display: flex;
  flex-direction: column;
  gap: 10px;
  min-width: 340px;
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
.hint {
  font-size: 11px;
  color: var(--muted);
  margin: 0;
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
  background: var(--warn);
  color: #fff;
  border-color: var(--warn);
}
.btn.confirm:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.btn.cancel {
  background: transparent;
}
</style>
