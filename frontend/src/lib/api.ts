// Axios client: same-origin calls (dev server proxies /api to FastAPI),
// cookies sent with credentials, silent refresh on 401.

import axios, { AxiosError, type InternalAxiosRequestConfig } from 'axios'

export const api = axios.create({
  baseURL: '/api',
  withCredentials: true,
  headers: { 'Content-Type': 'application/json' },
})

export class ApiError extends Error {
  status: number
  constructor(message: string, status: number) {
    super(message)
    this.status = status
  }
}

export function getErrorMessage(error: unknown, fallback = 'Something went wrong'): string {
  if (error instanceof AxiosError) {
    const detail = error.response?.data?.detail
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail) && detail.length > 0) {
      const first = detail[0]
      if (first?.msg) return first.msg
    }
    if (error.message === 'Network Error') return 'Cannot reach the server. Is the backend running?'
  }
  if (error instanceof Error && error.message) return error.message
  return fallback
}

let refreshing: Promise<boolean> | null = null

async function tryRefresh(): Promise<boolean> {
  try {
    await axios.post('/api/auth/refresh', null, { withCredentials: true })
    return true
  } catch {
    return false
  }
}

api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const original = error.config as InternalAxiosRequestConfig & { _retried?: boolean }
    const isAuthCall = original?.url?.includes('/auth/')
    if (
      error.response?.status === 401 &&
      original &&
      !original._retried &&
      !isAuthCall
    ) {
      original._retried = true
      refreshing = refreshing ?? tryRefresh()
      const ok = await refreshing
      refreshing = null
      if (ok) return api(original)
    }
    return Promise.reject(error)
  },
)
