import axios, { AxiosError } from 'axios'
import type { ApiErrorBody } from '../types/api'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export const apiClient = axios.create({
  baseURL: API_URL,
})

// Attaches the JWT to every request — set once at login, read fresh
// each call rather than baked into the instance at creation time, so
// logging in/out doesn't need to reconstruct the client.
apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// A 401 means the token is missing/expired/invalid — auth_service.py
// never issues a refresh token (see docs/ADR.md ADR-003), so there's
// nothing to retry; clear it and send the user back to /login. Plain
// navigation (not react-router's navigate) since an axios interceptor
// runs outside any component's render context.
apiClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token')
      if (window.location.pathname !== '/login') {
        window.location.href = '/login'
      }
    }
    return Promise.reject(error)
  },
)

// Every backend error response uses {"detail": "..."} (or FastAPI's
// own 422 validation shape, a list of {msg, ...} objects) — this is
// the one place that turns either into a plain string for display.
export function getErrorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const status = error.response?.status
    const body = error.response?.data as ApiErrorBody | undefined
    const detail = body?.detail

    if (status === 429) {
      const retryAfter = error.response?.headers?.['retry-after']
      return retryAfter
        ? `Rate limit exceeded — try again in ${retryAfter}s.`
        : 'Rate limit exceeded — try again shortly.'
    }

    if (typeof detail === 'string') return detail
    if (Array.isArray(detail) && detail.length > 0) {
      return detail.map((d) => d.msg).join('; ')
    }
    if (!error.response) return 'Could not reach the server — is the API running?'
    return `Request failed (${status ?? 'unknown error'}).`
  }
  return error instanceof Error ? error.message : 'Something went wrong.'
}
