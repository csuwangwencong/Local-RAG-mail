import type { AccountInfo, InboxStatus } from './common'

export interface ConnectResponse {
  account: AccountInfo
  inbox: InboxStatus
}

export interface SessionResponse {
  connected: boolean
  account: AccountInfo | null
  inbox: InboxStatus | null
}
