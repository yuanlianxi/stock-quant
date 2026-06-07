<script setup lang="ts">
import { ref, computed } from 'vue'
import { useToast } from '@/composables/useToast'
import { sessionApi } from '@/services/session'
import SessionFormField from './SessionFormField.vue'

const props = defineProps<{
  sessionId: string
  currentUnits: number
  direction: 'long' | 'short'
}>()
const emit = defineEmits<{ (e: 'close'): void }>()

const handCount = ref(1)
const orderPrice = ref<number>(0)
const submitLoading = ref(false)
const remaining = computed(() => Math.max(0, 4 - props.currentUnits))
const canSubmit = computed(
  () => handCount.value > 0 && orderPrice.value > 0 && remaining.value > 0
)

async function submit() {
  if (!canSubmit.value) return
  submitLoading.value = true
  try {
    const r = await sessionApi.addOrder(props.sessionId, {
      hand_count: handCount.value,
      order_price: orderPrice.value,
      direction: props.direction
    })
    const unitId = (r && (r.unit_id || r.id)) || '未知'
    useToast().push({
      kind: 'success',
      title: '✅ 加仓成功',
      body: `session=${props.sessionId.slice(0, 8)}, unit=${String(unitId).slice(0, 8)}`
    })
    emit('close')
  } catch (e) {
    useToast().push({ kind: 'error', title: '加仓失败', body: String(e) })
  } finally {
    submitLoading.value = false
  }
}
</script>

<template>
  <div class="modal-host-inner">
    <h3 class="title">
      ➕ 加仓 · session {{ sessionId.slice(0, 8) }} · {{ currentUnits }}/4 Units
    </h3>
    <p v-if="remaining <= 0" class="warn">⚠️ 已达最大 4 Unit 上限</p>
    <div v-else class="form-row">
      <SessionFormField
        :label="`加仓手数（剩余 ${remaining} Unit）`"
        :min="1"
        v-model="handCount"
      />
      <SessionFormField label="加仓价" :step="0.01" v-model="orderPrice" />
    </div>
    <div class="actions">
      <button class="btn cancel" @click="emit('close')">取消</button>
      <button
        class="btn confirm"
        :disabled="!canSubmit || submitLoading"
        @click="submit"
      >
        {{ submitLoading ? '提交中...' : '确认加仓' }}
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
.warn {
  color: var(--warn);
  font-size: 12px;
  background: rgba(245, 166, 35, 0.1);
  padding: 8px;
  border-radius: 4px;
}
.form-row {
  display: flex;
  gap: 12px;
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
