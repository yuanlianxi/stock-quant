<script setup lang="ts">
import { computed, markRaw } from 'vue'
import { useModal } from '@/composables/useModal'
import Modal from '@/components/Modal.vue'
import OpenSessionModal from '@/modals/OpenSessionModal.vue'
import AddUnitModal from '@/modals/AddUnitModal.vue'
import ReduceUnitModal from '@/modals/ReduceUnitModal.vue'
import CloseAllModal from '@/modals/CloseAllModal.vue'
import LineOverrideModal from '@/modals/LineOverrideModal.vue'

const { items, close } = useModal()

// 组件映射表（按名字查找）— 用 markRaw 避免被当成 reactive
const componentMap: Record<string, any> = {
  OpenSessionModal: markRaw(OpenSessionModal),
  AddUnitModal: markRaw(AddUnitModal),
  ReduceUnitModal: markRaw(ReduceUnitModal),
  CloseAllModal: markRaw(CloseAllModal),
  LineOverrideModal: markRaw(LineOverrideModal)
}

interface ResolvedModal {
  id: number
  cmp: any
  title: string
  width: number
  innerProps: Record<string, any>
}

function resolve(item: { component: any }): any {
  // 支持两种 open() 形式：
  //   1. open('OpenSessionModal', props)              → 字符串名
  //   2. open(SomeComponent, props)                   → 直接传组件
  if (typeof item.component === 'string') {
    return componentMap[item.component] || null
  }
  return item.component
}

const viewItems = computed<ResolvedModal[]>(() =>
  (items as Array<{ id: number; component: any; props?: Record<string, any> }>)
    .map((item): ResolvedModal | null => {
      const cmp = resolve(item)
      if (!cmp) return null
      const props = item.props || {}
      return {
        id: item.id,
        cmp,
        title: (props.title as string) || '操作',
        width: (props.width as number) || 480,
        // 剥离 title/width，避免传给内部组件 prop 校验失败
        innerProps: Object.fromEntries(
          Object.entries(props).filter(([k]) => k !== 'title' && k !== 'width')
        )
      }
    })
    .filter((x): x is ResolvedModal => x !== null)
)
</script>

<template>
  <Teleport to="body">
    <div class="action-modal-host-list">
      <Modal
        v-for="m in viewItems"
        :key="m.id"
        :title="m.title"
        :width="m.width"
        @close="close(m.id)"
      >
        <component :is="m.cmp" v-bind="m.innerProps" @close="close(m.id)" />
      </Modal>
    </div>
  </Teleport>
</template>

<style scoped>
.action-modal-host-list {
  position: fixed;
  inset: 0;
  z-index: 1900;
  pointer-events: none;
}
.action-modal-host-list > * {
  pointer-events: auto;
}
</style>
