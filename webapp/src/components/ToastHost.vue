<script setup lang="ts">
import { useToast, type ToastKind } from '@/composables/useToast'

const { items, remove } = useToast()
const classFor = (k: ToastKind) => {
  if (k === 'long' || k === 'success') return 'toast-long'
  if (k === 'short' || k === 'error') return 'toast-short'
  if (k === 'exit' || k === 'warn') return 'toast-exit'
  if (k === 'add' || k === 'info') return 'toast-add'
  return 'toast-info'
}
</script>

<template>
  <div class="toast-container">
    <div v-for="t in items" :key="t.id" :class="['toast', classFor(t.kind)]" @click="remove(t.id)">
      <div v-if="t.title" class="toast-title">{{ t.title }}</div>
      <div v-if="t.body" class="toast-body">{{ t.body }}</div>
    </div>
  </div>
</template>

<style scoped>
.toast-container {
  position: fixed; top: 60px; right: 16px; z-index: 9999;
  display: flex; flex-direction: column; gap: 8px;
  pointer-events: none;
}
.toast {
  background: var(--card); border: 1px solid var(--border); border-radius: 10px;
  padding: 12px 16px; min-width: 240px; max-width: 320px;
  box-shadow: 0 4px 20px rgba(0,0,0,0.4);
  pointer-events: auto; cursor: pointer;
}
.toast-title { font-size: 13px; font-weight: 700; margin-bottom: 4px; }
.toast-body { font-size: 12px; color: var(--muted); line-height: 1.5; }
.toast-long { border-left: 3px solid var(--buy); }
.toast-short { border-left: 3px solid var(--sell); }
.toast-exit { border-left: 3px solid var(--warn); }
.toast-add { border-left: 3px solid var(--accent); }
.toast-info { border-left: 3px solid var(--muted); }
</style>
