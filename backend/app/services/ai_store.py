from __future__ import annotations

import secrets
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal

from app.api.ai_models import AiConversationDetail, AiConversationSummary, AiMessage


MAX_MESSAGES_PER_CONVERSATION = 100


def now_iso() -> str:
    return datetime.now(UTC).astimezone().isoformat()


@dataclass
class AiConversation:
    conversation_id: str
    title: str
    model: str
    created_at: str = field(default_factory=now_iso)
    updated_at: str = field(default_factory=now_iso)
    messages: list[AiMessage] = field(default_factory=list)

    def to_summary(self) -> AiConversationSummary:
        return AiConversationSummary(
            conversation_id=self.conversation_id,
            title=self.title,
            model=self.model,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )

    def to_detail(self) -> AiConversationDetail:
        return AiConversationDetail(
            conversation_id=self.conversation_id,
            title=self.title,
            model=self.model,
            created_at=self.created_at,
            updated_at=self.updated_at,
            messages=self.messages,
        )

    def append(self, message: AiMessage) -> None:
        self.messages.append(message)
        if len(self.messages) > MAX_MESSAGES_PER_CONVERSATION:
            self.messages = self.messages[-MAX_MESSAGES_PER_CONVERSATION:]
        self.updated_at = now_iso()
        if self.title == "新的邮件问答" and message.role == "user":
            self.title = message.content.strip().replace("\n", " ")[:28] or self.title


class AiConversationStore:
    def __init__(self) -> None:
        self._conversations: dict[str, AiConversation] = {}

    def list(self) -> list[AiConversationSummary]:
        return [
            conversation.to_summary()
            for conversation in sorted(
                self._conversations.values(),
                key=lambda item: item.updated_at,
                reverse=True,
            )
        ]

    def create(self, model: str, title: str | None = None) -> AiConversation:
        conversation = AiConversation(
            conversation_id=secrets.token_urlsafe(16),
            title=title.strip() if title and title.strip() else "新的邮件问答",
            model=model,
        )
        self._conversations[conversation.conversation_id] = conversation
        return conversation

    def get(self, conversation_id: str) -> AiConversation | None:
        return self._conversations.get(conversation_id)

    def delete(self, conversation_id: str) -> None:
        self._conversations.pop(conversation_id, None)

    def clear(self) -> None:
        self._conversations.clear()


def new_ai_message(role: Literal["user", "assistant", "system"], content: str) -> AiMessage:
    return AiMessage(
        message_id=secrets.token_urlsafe(12),
        role=role,
        content=content,
        created_at=now_iso(),
        sources=[],
        feedback=None,
    )
