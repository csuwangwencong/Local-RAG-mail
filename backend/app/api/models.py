from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class MailAddress(BaseModel):
    name: str = ""
    address: str = ""


class InboxStatus(BaseModel):
    total: int = 0
    unread: int = 0


class AccountInfo(BaseModel):
    email: EmailStr


class ConnectRequest(BaseModel):
    email: EmailStr
    auth_code: str = Field(min_length=1, max_length=256)


class ConnectResponse(BaseModel):
    account: AccountInfo
    inbox: InboxStatus


class SessionResponse(BaseModel):
    connected: bool
    account: AccountInfo | None = None
    inbox: InboxStatus | None = None


class MessageSummary(BaseModel):
    uid: str
    subject: str
    sender: MailAddress
    received_at: str | None
    is_read: bool
    size: int


class MessageListResponse(BaseModel):
    mailbox: InboxStatus
    items: list[MessageSummary]
    next_before_uid: str | None
    has_more: bool


class MessageBody(BaseModel):
    type: Literal["html", "text", "empty"]
    html: str | None = None
    text: str | None = None


class MessageDetail(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    uid: str
    subject: str
    from_: list[MailAddress] = Field(alias="from")
    to: list[MailAddress]
    cc: list[MailAddress]
    received_at: str | None
    body: MessageBody
