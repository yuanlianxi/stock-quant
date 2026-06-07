import { reactive } from 'vue'

interface ModalItem { id: number; component: any; props?: Record<string, any> }
const state = reactive<{ items: ModalItem[]; seq: number }>({ items: [], seq: 0 })

export const useModal = () => ({
  items: state.items,
  open(component: any, props?: Record<string, any>) {
    const id = ++state.seq
    state.items.push({ id, component, props })
    return id
  },
  close(id: number) {
    const idx = state.items.findIndex(x => x.id === id)
    if (idx >= 0) state.items.splice(idx, 1)
  }
})
