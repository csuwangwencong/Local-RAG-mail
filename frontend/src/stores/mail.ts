import { defineStore } from 'pinia'

import { ApiError } from '../api/client'
import { deleteSession, connectSession, fetchSession } from '../api/session'
import { fetchMessageDetail, fetchMessages } from '../api/inbox'
import type { MessageDetail, MessageSummary } from '../types/message'

let detailController: AbortController | null = null
const messageCache = new Map<string, MessageDetail>()

function messageOf(error: unknown) {
  return error instanceof Error ? error.message : '请求失败'
}

export const useMailStore = defineStore('mail', {
  state: () => ({
    bootstrapping: true,
    connected: false,
    activeView: 'inbox' as 'inbox' | 'ai',
    accountEmail: '',
    inboxTotal: 0,
    inboxUnread: 0,
    messages: [] as MessageSummary[],
    nextBeforeUid: null as string | null,
    hasMore: false,
    selectedUid: null as string | null,
    selectedMessage: null as MessageDetail | null,
    listLoading: false,
    moreLoading: false,
    detailLoading: false,
    refreshLoading: false,
    loginError: null as string | null,
    listError: null as string | null,
    detailError: null as string | null,
  }),
  actions: {
    clearMailbox() {
      this.connected = false
      this.activeView = 'inbox'
      this.accountEmail = ''
      this.inboxTotal = 0
      this.inboxUnread = 0
      this.messages = []
      this.nextBeforeUid = null
      this.hasMore = false
      this.selectedUid = null
      this.selectedMessage = null
      messageCache.clear()
    },
    openInbox() {
      this.activeView = 'inbox'
    },
    openAiAssistant() {
      this.activeView = 'ai'
    },
    handleApiError(error: unknown) {
      if (error instanceof ApiError && error.status === 401 && error.code === 'SESSION_EXPIRED') {
        this.clearMailbox()
        this.loginError = error.message
        return true
      }
      return false
    },
    async restoreSession() {
      this.bootstrapping = true
      try {
        const session = await fetchSession()
        this.connected = session.connected
        this.accountEmail = session.account?.email ?? ''
        this.inboxTotal = session.inbox?.total ?? 0
        this.inboxUnread = session.inbox?.unread ?? 0
        if (this.connected) await this.loadFirstPage()
      } catch (error) {
        this.handleApiError(error)
      } finally {
        this.bootstrapping = false
      }
    },
    async connect(email: string, authCode: string) {
      this.loginError = null
      try {
        const response = await connectSession(email, authCode)
        this.connected = true
        this.accountEmail = response.account.email
        this.inboxTotal = response.inbox.total
        this.inboxUnread = response.inbox.unread
        await this.loadFirstPage()
      } catch (error) {
        this.loginError = messageOf(error)
        throw error
      }
    },
    async disconnect() {
      await deleteSession().catch(() => undefined)
      this.clearMailbox()
    },
    async loadFirstPage() {
      this.listLoading = true
      this.listError = null
      try {
        const response = await fetchMessages()
        this.inboxTotal = response.mailbox.total
        this.inboxUnread = response.mailbox.unread
        this.messages = response.items
        this.nextBeforeUid = response.next_before_uid
        this.hasMore = response.has_more
      } catch (error) {
        if (!this.handleApiError(error)) this.listError = messageOf(error)
      } finally {
        this.listLoading = false
      }
    },
    async refreshInbox() {
      if (this.refreshLoading) return
      this.refreshLoading = true
      const selected = this.selectedUid
      await this.loadFirstPage()
      if (selected && this.messages.some((item) => item.uid === selected)) {
        this.selectedUid = selected
      } else if (selected) {
        this.selectedUid = null
        this.selectedMessage = null
      }
      this.refreshLoading = false
    },
    async loadMore() {
      if (!this.hasMore || this.moreLoading) return
      this.moreLoading = true
      this.listError = null
      try {
        const response = await fetchMessages(30, this.nextBeforeUid)
        const known = new Set(this.messages.map((item) => item.uid))
        this.messages.push(...response.items.filter((item) => !known.has(item.uid)))
        this.inboxTotal = response.mailbox.total
        this.inboxUnread = response.mailbox.unread
        this.nextBeforeUid = response.next_before_uid
        this.hasMore = response.has_more
      } catch (error) {
        if (!this.handleApiError(error)) this.listError = messageOf(error)
      } finally {
        this.moreLoading = false
      }
    },
    async selectMessage(uid: string) {
      detailController?.abort()
      detailController = new AbortController()
      this.selectedUid = uid
      this.detailError = null
      const cached = messageCache.get(uid)
      if (cached) {
        this.selectedMessage = cached
        return
      }
      this.detailLoading = true
      try {
        const detail = await fetchMessageDetail(uid, detailController.signal)
        if (this.selectedUid === uid) {
          this.selectedMessage = detail
          messageCache.set(uid, detail)
        }
      } catch (error) {
        if (error instanceof DOMException && error.name === 'AbortError') return
        if (!this.handleApiError(error)) this.detailError = messageOf(error)
      } finally {
        if (this.selectedUid === uid) this.detailLoading = false
      }
    },
    async reloadSelectedMessage() {
      if (!this.selectedUid) return
      messageCache.delete(this.selectedUid)
      await this.selectMessage(this.selectedUid)
    },
    clearErrors() {
      this.loginError = null
      this.listError = null
      this.detailError = null
    },
  },
})
