<script setup lang="ts">
import { ref, computed } from 'vue'
import { useToast } from '@/composables/useToast'
import { sessionApi } from '@/services/session'
import SessionFormField from './SessionFormField.vue'

const props = defineProps<{
  sessionId: string
  currentLines: { entry: number; stop_loss: number; take_profit: number; warning: number }
}>()
const emit = defineEmits<{ (e: 'close'): void }>()

const entry = ref<number>(props.currentLines.entry)
const stopLoss = ref<number>(props.currentLines.stop_loss)
const takeProfit = ref<number>(props.currentLines.take_profit)
const warning = ref<number>(props.currentLines.warning)
const reason = ref('manual_adjust')
const submitLoading = ref(false)

const changes = computed<string[]>(() => {
  const list: string[] = []
  if (entry.value !== props.currentLines.entry) list.push('entry')
  if (stopLoss.value !== props.currentLines.stop_loss) list.push('stop_loss')
  if (takeProfit.value !== props.currentLines.take_profit) list.push('take_profit')
  if (warning.value !== props.currentLines.warning) list.push('warning')
  return list
})

const priceFor = (lineType: string): number => {
  switch (lineType) {
    case 'entry':
      return entry.value
    case 'stop_loss':
      return stopLoss.value
    case 'take_profit':
      return takeProfit.value
    case 'warning':
      return warning.value
    default:
      return 0
  }
}

async function submit() {
  if (changes.value.length === 0) {
    useToast().push({ kind: 'warn', title: '未检测到改动' })
    return
  }
  submitLoading.value = true
  try {
    for (const lineType of changes.value) {
      await sessionApi.setLine(props.sessionId, lineType, {
        price: priceFor(lineType),
        reason: reason.value
      })
    }
    useToast().push({
      kind: 'success',
      title: '✅ 调价成功',
      body: `改了 ${changes.value.length} 条线`
    })
    emit('close')
  } catch (e) {
    useToast().push({ kind: 'error', title: '调价失败', body: String(e) })
  } finally {
    submitLoading.value = false
  }
}
</script>

<template>
  <div class="modal-host-inner">
    <h3 class="title">✏️ 调价 · session {{ sessionId.slice(0, 8) }}</h3>
    <div class="form-row">
      <SessionFormField
        label="入场价（不可改）"
        :step="0.01"
        v-model="entry"
        :disabled="true"
      />
      <SessionFormField label="止损价" :step="0.01" v-model="stopLoss" />
    </div>
    <div class="form-row">
      <SessionFormField label="止盈价" :step="0.01" v-model="takeProfit" />
      <SessionFormField label="预警价" :step="0.01" v-model="warning" />
    </div>
    <label class="field">
      <span class="lbl">调价原因</span>
      <select v-model="reason" class="input">
        <option value="manual_adjust">手动调整</option>
        <option value="volatility_change">波动率变化</option>
        <option value="trend_break">趋势突破</option>
        <option value="news_driven">消息面驱动</option>
      </select>
    </label>
    <p v-if="changes.length === 0" class="hint">
      无改动（修改任意价格字段后即可提交）
    </p>
    <p v-else class="hint">
      将改动：<strong>{{ changes.join(', ') }}</strong>
    </p>
    <div class="actions">
      <button class="btn cancel" @click="emit('close')">取消</button>
      <button
        class="btn confirm"
        :disabled="submitLoading || changes.length === 0"
        @click="submit"
      >
        {{ submitLoading ? '提交中...' : '确认调价' }}
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
.hint strong {
  color: var(--accent);
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
  background: var(--accent);
  color: #fff;
  border-color: var(--accent);
}
.btn.confirm:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.btn.cancel {
  background: transparent;
}
</style>
