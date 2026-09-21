import type { InboxStatus, MailAddress } from './common'

export interface MessageSummary {
  uid: string
  subject: string
  sender: MailAddress
  received_at: string | null
  is_read: boolean
  size: number
}

export interface MessageListResponse {
  mailbox: InboxStatus
  items: MessageSummary[]
  next_before_uid: string | null
  has_more: boolean
}

export interface MessageBody {
  type: 'html' | 'text' | 'empty'
  html: string | null
  text: string | null
}

export interface MessageDetail {
  uid: string
  subject: string
  from: MailAddress[]
  to: MailAddress[]
  cc: MailAddress[]
  received_at: string | null
  body: MessageBody
}
