<script setup lang="ts">
withDefaults(
  defineProps<{
    label: string
    type?: string
    step?: number
    min?: number
    max?: number
    placeholder?: string
    disabled?: boolean
  }>(),
  {
    type: 'number',
    step: 0.01,
    min: 0
  }
)

const model = defineModel<number | string | undefined>({ required: true })
</script>

<template>
  <label class="field">
    <span class="lbl">{{ label }}</span>
    <input
      v-model="model"
      :type="type"
      :step="step"
      :min="min"
      :max="max"
      :placeholder="placeholder"
      :disabled="disabled"
      class="input"
    />
  </label>
</template>

<style scoped>
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
.input:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
