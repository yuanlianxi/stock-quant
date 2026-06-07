const BASE_URL = import.meta.env.VITE_API_BASE ?? '/api/v1'

export class ApiError extends Error {
  constructor(public status: number, public detail: string, public path: string) {
    super(`[${status}] ${path}: ${detail}`)
    this.name = 'ApiError'
  }
}

interface RequestOptions {
  params?: Record<string, any>
  body?: any
  signal?: AbortSignal
  timeoutMs?: number
}

async function request<T>(method: string, path: string, opts: RequestOptions = {}): Promise<T> {
  const url = new URL(BASE_URL + path, window.location.origin)
  if (opts.params) {
    Object.entries(opts.params).forEach(([k, v]) => {
      if (v != null) url.searchParams.set(k, String(v))
    })
  }

  const ctrl = new AbortController()
  const timeoutId = opts.timeoutMs
    ? setTimeout(() => ctrl.abort(), opts.timeoutMs)
    : null
  if (opts.signal) {
    opts.signal.addEventListener('abort', () => ctrl.abort())
  }

  try {
    const r = await fetch(url.toString().replace(window.location.origin, ''), {
      method,
      headers: { 'Content-Type': 'application/json' },
      body: opts.body ? JSON.stringify(opts.body) : undefined,
      signal: ctrl.signal
    })
    if (timeoutId) clearTimeout(timeoutId)
    if (!r.ok) {
      let detail = r.statusText
      try { detail = (await r.json()).detail ?? detail } catch {}
      throw new ApiError(r.status, detail, path)
    }
    return r.status === 204 ? (null as T) : await r.json()
  } catch (e) {
    if (timeoutId) clearTimeout(timeoutId)
    if (e instanceof ApiError) throw e
    throw new ApiError(0, e instanceof Error ? e.message : String(e), path)
  }
}

export const useApi = () => ({
  get:    <T>(p: string, params?: Record<string, any>) => request<T>('GET', p, { params }),
  post:   <T>(p: string, body?: any) => request<T>('POST', p, { body }),
  put:    <T>(p: string, body?: any) => request<T>('PUT', p, { body }),
  delete: <T>(p: string) => request<T>('DELETE', p)
})
