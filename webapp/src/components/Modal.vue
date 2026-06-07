<script setup lang="ts">
defineProps<{ title?: string; width?: number }>()
const emit = defineEmits<{ (e: 'close'): void }>()
</script>

<template>
  <div class="modal-host">
    <div class="modal-mask" @click="emit('close')" />
    <div class="modal-box" :style="{ width: (width ?? 480) + 'px' }">
      <header v-if="title" class="modal-head">
        <h3>{{ title }}</h3>
        <button class="modal-x" @click="emit('close')" aria-label="关闭">×</button>
      </header>
      <div class="modal-body"><slot /></div>
    </div>
  </div>
</template>

<style scoped>
.modal-host { position: fixed; inset: 0; z-index: 2000; }
.modal-mask { position: absolute; inset: 0; background: rgba(0,0,0,0.6); }
.modal-box {
  position: absolute; left: 50%; top: 50%; transform: translate(-50%, -50%);
  max-width: 92vw; max-height: 84vh; overflow-y: auto;
  background: var(--card); border: 1px solid var(--border); border-radius: 8px;
  padding: 18px 20px; box-shadow: 0 8px 24px rgba(0,0,0,0.4);
}
.modal-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; }
.modal-head h3 { font-size: 15px; color: var(--accent); margin: 0; }
.modal-x { background: none; border: none; color: var(--muted); font-size: 22px; cursor: pointer; line-height: 1; padding: 0 4px; }
.modal-body { font-size: 13px; }
</style>
