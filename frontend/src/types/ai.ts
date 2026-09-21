export const DEFAULT_AI_MODEL = 'qwen2.5:7b-instruct'

export interface AiModelInfo {
  id: string
  name: string
  provider: string
}

export interface AiModelsResponse {
  items: AiModelInfo[]
}

export interface AiSource {
  title: string
  uid: string | null
  snippet: string | null
  sender_name: string
  sender_address: string
  received_at: string | null
  score: number | null
  source_type: string
}

export interface AiMessage {
  message_id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  created_at: string
  sources: AiSource[]
  feedback: 'liked' | 'disliked' | null
}

export interface AiConversationSummary {
  conversation_id: string
  title: string
  model: string
  created_at: string
  updated_at: string
}

export interface AiConversationDetail extends AiConversationSummary {
  messages: AiMessage[]
}

export interface AiConversationsResponse {
  items: AiConversationSummary[]
}

export interface CreateAiConversationResponse {
  conversation: AiConversationDetail
}

export interface SendAiMessageResponse {
  conversation_id: string
  user_message: AiMessage
  assistant_message: AiMessage
}

export interface RagStatusResponse {
  status: string
  indexed_messages: number
  total_target_messages: number
  last_indexed_at: string | null
  error: string | null
}

export interface StartRagIndexResponse {
  status: RagStatusResponse
}
