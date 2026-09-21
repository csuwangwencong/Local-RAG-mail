import { apiFetch } from './client'
import type { RagStatusResponse, StartRagIndexResponse } from '../types/ai'

export function fetchRagStatus() {
  return apiFetch<RagStatusResponse>('/api/v1/rag/status')
}

export function startRagIndex(limit = 50) {
  return apiFetch<StartRagIndexResponse>('/api/v1/rag/index', {
    method: 'POST',
    body: JSON.stringify({ limit }),
  })
}
