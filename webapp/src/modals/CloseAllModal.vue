<script setup lang="ts">
import { ref } from 'vue'
import { useToast } from '@/composables/useToast'
import { sessionApi } from '@/services/session'

const props = defineProps<{ sessionId: string }>()
const emit = defineEmits<{ (e: 'close'): void }>()

const reason = ref('manual_close')
const submitLoading = ref(false)

async function submit() {
  submitLoading.value = true
  try {
    await sessionApi.close(props.sessionId, { reason: reason.value })
    useToast().push({
      kind: 'success',
      title: '✅ 全部平仓',
      body: `session=${props.sessionId.slice(0, 8)}`
    })
    emit('close')
  } catch (e) {
    useToast().push({ kind: 'error', title: '平仓失败', body: String(e) })
  } finally {
    submitLoading.value = false
  }
}
</script>

<template>
  <div class="modal-host-inner">
    <h3 class="title">⛔ 全部平仓</h3>
    <p class="warn">
      ⚠️ 此操作不可恢复，session {{ sessionId.slice(0, 8) }} 的所有 Unit 将被平仓
    </p>
    <label class="field">
      <span class="lbl">平仓原因</span>
      <select v-model="reason" class="input">
        <option value="manual_close">手动平仓</option>
        <option value="risk_control">风控平仓</option>
        <option value="strategy_exit">策略止盈/止损</option>
        <option value="end_of_day">收盘平仓</option>
      </select>
    </label>
    <div class="actions">
      <button class="btn cancel" @click="emit('close')">取消</button>
      <button class="btn confirm" :disabled="submitLoading" @click="submit">
        {{ submitLoading ? '提交中...' : '确认全部平仓' }}
      </button>
    </div>
  </div>
</template>

<style scoped>
.modal-host-inner {
  display: flex;
  flex-direction: column;
  gap: 10px;
  min-width: 320px;
}
.title {
  font-size: 15px;
  color: var(--sell);
  margin: 0 0 4px 0;
}
.warn {
  color: var(--warn);
  font-size: 12px;
  background: rgba(245, 166, 35, 0.1);
  padding: 8px;
  border-radius: 4px;
  margin: 0;
}
.field {
  display: flex;
  flex-direction: column;
  gap: 4px;
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
  background: var(--sell);
  color: #fff;
  border-color: var(--sell);
}
.btn.confirm:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.btn.cancel {
  background: transparent;
}
</style>
