import { apiFetch } from './client'
import type { MessageDetail, MessageListResponse } from '../types/message'

export function fetchMessages(limit = 30, beforeUid?: string | null) {
  const params = new URLSearchParams({ limit: String(limit) })
  if (beforeUid) params.set('before_uid', beforeUid)
  return apiFetch<MessageListResponse>(`/api/v1/inbox/messages?${params}`)
}

export function fetchMessageDetail(uid: string, signal?: AbortSignal) {
  return apiFetch<MessageDetail>(`/api/v1/inbox/messages/${encodeURIComponent(uid)}`, { signal })
}
