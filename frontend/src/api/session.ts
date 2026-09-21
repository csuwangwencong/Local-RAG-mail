import { apiFetch } from './client'
import type { ConnectResponse, SessionResponse } from '../types/session'

export function connectSession(email: string, authCode: string) {
  return apiFetch<ConnectResponse>('/api/v1/session/connect', {
    method: 'POST',
    body: JSON.stringify({ email, auth_code: authCode }),
  })
}

export function fetchSession() {
  return apiFetch<SessionResponse>('/api/v1/session')
}

export function deleteSession() {
  return apiFetch<void>('/api/v1/session', { method: 'DELETE' })
}
