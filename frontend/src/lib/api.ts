import { auth } from './firebase'

const BASE = import.meta.env.VITE_API_BASE_URL ?? ''

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message)
    this.name = 'ApiError'
  }
}

async function getToken(): Promise<string> {
  const user = auth.currentUser
  if (!user) throw new ApiError(401, 'Not authenticated')
  return user.getIdToken()
}

/** Authenticated fetch — injects Firebase ID token automatically. */
export async function apiFetch(path: string, options: RequestInit = {}): Promise<Response> {
  const token = await getToken()
  const res = await fetch(`${BASE}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
      ...options.headers,
    },
  })

  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }))
    throw new ApiError(res.status, body.detail ?? 'Request failed')
  }

  return res
}

/** Typed JSON fetch shorthand. */
export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const res = await apiFetch(path, options)
  // 204 No Content — return empty object cast to T
  if (res.status === 204) return {} as T
  return res.json()
}

/** Authenticated POST that returns the raw Response for SSE streaming. */
export async function apiStream(path: string, body: unknown, signal?: AbortSignal): Promise<Response> {
  const token = await getToken()
  const res = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(body),
    signal,
  })

  if (!res.ok) {
    const data = await res.json().catch(() => ({ detail: res.statusText }))
    throw new ApiError(res.status, data.detail ?? 'Request failed')
  }

  return res
}

/** Log a frontend error to the backend (best-effort, never throws). */
export function logFrontendError(message: string, stack?: string): void {
  const payload = {
    message,
    stack,
    url: window.location.href,
    user_agent: navigator.userAgent,
  }
  // Fire-and-forget — use plain fetch to avoid circular dependency with api()
  getToken()
    .then(token =>
      fetch(`${BASE}/api/log-error`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify(payload),
      })
    )
    .catch(() => { /* swallow — logging must never crash the app */ })
}
