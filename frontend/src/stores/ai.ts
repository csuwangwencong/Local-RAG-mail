import { defineStore } from 'pinia'

import { ApiError } from '../api/client'
import {
  createAiConversation,
  deleteAiConversation,
  fetchAiConversation,
  fetchAiConversations,
  fetchAiModels,
  sendAiMessage,
} from '../api/ai'
import { fetchRagStatus, startRagIndex } from '../api/rag'
import {
  DEFAULT_AI_MODEL,
  type AiConversationSummary,
  type AiMessage,
  type AiModelInfo,
  type RagStatusResponse,
} from '../types/ai'
import { useMailStore } from './mail'

function messageOf(error: unknown) {
  return error instanceof Error ? error.message : '请求失败'
}

function createPendingUserMessage(content: string): AiMessage {
  return {
    message_id: `pending-${crypto.randomUUID()}`,
    role: 'user',
    content,
    created_at: new Date().toISOString(),
    sources: [],
    feedback: null,
  }
}

export const useAiStore = defineStore('ai', {
  state: () => ({
    models: [] as AiModelInfo[],
    selectedModel: DEFAULT_AI_MODEL,
    conversations: [] as AiConversationSummary[],
    selectedConversationId: null as string | null,
    messages: [] as AiMessage[],
    ragStatus: null as RagStatusResponse | null,
    loadingModels: false,
    loadingConversations: false,
    loadingConversation: false,
    indexing: false,
    sending: false,
    error: null as string | null,
  }),
  getters: {
    activeConversation(state) {
      return state.conversations.find((item) => item.conversation_id === state.selectedConversationId) ?? null
    },
  },
  actions: {
    clear() {
      this.models = []
      this.conversations = []
      this.selectedConversationId = null
      this.messages = []
      this.ragStatus = null
      this.error = null
      this.sending = false
    },
    handleApiError(error: unknown) {
      if (error instanceof ApiError && error.status === 401 && error.code === 'SESSION_EXPIRED') {
        useMailStore().handleApiError(error)
        this.clear()
        return true
      }
      return false
    },
    async bootstrap() {
      if (this.loadingModels || this.loadingConversations) return
      await Promise.all([this.loadModels(), this.loadConversations(), this.loadRagStatus()])
      const selectedExists = this.conversations.some((item) => item.conversation_id === this.selectedConversationId)
      if (selectedExists && this.selectedConversationId) {
        await this.selectConversation(this.selectedConversationId)
      } else if (this.conversations[0]) {
        await this.selectConversation(this.conversations[0].conversation_id)
      } else {
        await this.newConversation()
      }
    },
    async loadModels() {
      this.loadingModels = true
      try {
        const response = await fetchAiModels()
        this.models = response.items
        this.selectedModel = response.items[0]?.id ?? DEFAULT_AI_MODEL
      } catch (error) {
        if (!this.handleApiError(error)) this.error = messageOf(error)
      } finally {
        this.loadingModels = false
      }
    },
    async loadConversations() {
      this.loadingConversations = true
      try {
        const response = await fetchAiConversations()
        this.conversations = response.items
      } catch (error) {
        if (!this.handleApiError(error)) this.error = messageOf(error)
      } finally {
        this.loadingConversations = false
      }
    },
    async loadRagStatus() {
      try {
        this.ragStatus = await fetchRagStatus()
      } catch (error) {
        if (!this.handleApiError(error)) this.error = messageOf(error)
      }
    },
    async buildKnowledgeBase() {
      if (this.indexing) return
      this.indexing = true
      this.error = null
      try {
        const response = await startRagIndex(50)
        this.ragStatus = response.status
      } catch (error) {
        if (!this.handleApiError(error)) this.error = messageOf(error)
      } finally {
        this.indexing = false
      }
    },
    async newConversation() {
      this.error = null
      try {
        const response = await createAiConversation(this.selectedModel)
        this.conversations.unshift(response.conversation)
        this.selectedConversationId = response.conversation.conversation_id
        this.messages = response.conversation.messages
      } catch (error) {
        if (!this.handleApiError(error)) this.error = messageOf(error)
      }
    },
    async selectConversation(conversationId: string) {
      this.selectedConversationId = conversationId
      this.loadingConversation = true
      this.error = null
      try {
        const conversation = await fetchAiConversation(conversationId)
        this.selectedModel = conversation.model
        this.messages = conversation.messages
      } catch (error) {
        if (!this.handleApiError(error)) this.error = messageOf(error)
      } finally {
        this.loadingConversation = false
      }
    },
    async removeConversation(conversationId: string) {
      try {
        await deleteAiConversation(conversationId)
        this.conversations = this.conversations.filter((item) => item.conversation_id !== conversationId)
        if (this.selectedConversationId === conversationId) {
          this.selectedConversationId = null
          this.messages = []
          if (this.conversations[0]) {
            await this.selectConversation(this.conversations[0].conversation_id)
          } else {
            await this.newConversation()
          }
        }
      } catch (error) {
        if (!this.handleApiError(error)) this.error = messageOf(error)
      }
    },
    async submit(content: string) {
      const trimmed = content.trim()
      if (!trimmed || this.sending) return
      if (!this.selectedConversationId) await this.newConversation()
      if (!this.selectedConversationId) return
      const pendingUserMessage = createPendingUserMessage(trimmed)
      this.messages.push(pendingUserMessage)
      this.sending = true
      this.error = null
      try {
        const response = await sendAiMessage(this.selectedConversationId, this.selectedModel, trimmed)
        const pendingIndex = this.messages.findIndex((message) => message.message_id === pendingUserMessage.message_id)
        if (pendingIndex >= 0) {
          this.messages.splice(pendingIndex, 1, response.user_message)
        } else {
          this.messages.push(response.user_message)
        }
        this.messages.push(response.assistant_message)
        await this.loadConversations()
      } catch (error) {
        if (!this.handleApiError(error)) this.error = messageOf(error)
      } finally {
        this.sending = false
      }
    },
  },
})
