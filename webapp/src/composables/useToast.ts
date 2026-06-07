import { reactive } from 'vue'

export type ToastKind = 'info' | 'success' | 'warn' | 'error' | 'long' | 'short' | 'exit' | 'add'

export interface ToastItem {
  id: number
  kind: ToastKind
  title: string
  body?: string
  durationMs?: number
}

const state = reactive<{ items: ToastItem[]; seq: number }>({ items: [], seq: 0 })

export const useToast = () => ({
  items: state.items,
  push(item: Omit<ToastItem, 'id'>) {
    const id = ++state.seq
    const t: ToastItem = { id, durationMs: 4000, ...item }
    state.items.push(t)
    setTimeout(() => {
      const idx = state.items.findIndex(x => x.id === id)
      if (idx >= 0) state.items.splice(idx, 1)
    }, t.durationMs)
    return id
  },
  remove(id: number) {
    const idx = state.items.findIndex(x => x.id === id)
    if (idx >= 0) state.items.splice(idx, 1)
  }
})
