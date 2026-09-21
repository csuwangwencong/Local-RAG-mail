import { apiFetch } from './client'
import type {
  AiConversationDetail,
  AiConversationsResponse,
  AiModelsResponse,
  CreateAiConversationResponse,
  SendAiMessageResponse,
} from '../types/ai'

export function fetchAiModels() {
  return apiFetch<AiModelsResponse>('/api/v1/ai/models')
}

export function fetchAiConversations() {
  return apiFetch<AiConversationsResponse>('/api/v1/ai/conversations')
}

export function createAiConversation(model: string, title?: string) {
  return apiFetch<CreateAiConversationResponse>('/api/v1/ai/conversations', {
    method: 'POST',
    body: JSON.stringify({ model, title }),
  })
}

export function fetchAiConversation(conversationId: string) {
  return apiFetch<AiConversationDetail>(`/api/v1/ai/conversations/${encodeURIComponent(conversationId)}`)
}

export function deleteAiConversation(conversationId: string) {
  return apiFetch<void>(`/api/v1/ai/conversations/${encodeURIComponent(conversationId)}`, {
    method: 'DELETE',
  })
}

export function sendAiMessage(conversationId: string, model: string, content: string) {
  return apiFetch<SendAiMessageResponse>(
    `/api/v1/ai/conversations/${encodeURIComponent(conversationId)}/messages`,
    {
      method: 'POST',
      body: JSON.stringify({ model, content }),
    },
  )
}
