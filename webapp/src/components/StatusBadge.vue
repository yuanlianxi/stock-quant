<script setup lang="ts">
defineProps<{ status: string }>()
</script>

<template>
  <span :class="['status-badge', `status-${status}`]">{{ status }}</span>
</template>

<style scoped>
.status-badge {
  padding: 2px 6px; border-radius: 3px; font-size: 10px;
  font-weight: 600; display: inline-block;
}
.status-badge.status-completed, .status-badge.status-active { background: rgba(38,196,133,0.18); color: var(--buy); }
.status-badge.status-failed, .status-badge.status-closed { background: rgba(240,86,106,0.18); color: var(--sell); }
.status-badge.status-running, .status-badge.status-open, .status-badge.status-pending { background: rgba(91,138,240,0.18); color: var(--accent); }
</style>
