from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


DEFAULT_AI_MODEL = "qwen2.5:7b-instruct"


class AiModelInfo(BaseModel):
    id: str
    name: str
    provider: str


class AiModelsResponse(BaseModel):
    items: list[AiModelInfo]


class AiSource(BaseModel):
    title: str
    uid: str | None = None
    snippet: str | None = None
    sender_name: str = ""
    sender_address: str = ""
    received_at: str | None = None
    score: float | None = None
    source_type: str = "hybrid"


class AiMessage(BaseModel):
    message_id: str
    role: Literal["user", "assistant", "system"]
    content: str
    created_at: str
    sources: list[AiSource] = Field(default_factory=list)
    feedback: Literal["liked", "disliked"] | None = None


class AiConversationSummary(BaseModel):
    conversation_id: str
    title: str
    model: str
    created_at: str
    updated_at: str


class AiConversationDetail(AiConversationSummary):
    messages: list[AiMessage]


class AiConversationsResponse(BaseModel):
    items: list[AiConversationSummary]


class CreateAiConversationRequest(BaseModel):
    model: str = DEFAULT_AI_MODEL
    title: str | None = Field(default=None, max_length=80)


class CreateAiConversationResponse(BaseModel):
    conversation: AiConversationDetail


class SendAiMessageRequest(BaseModel):
    content: str = Field(min_length=1, max_length=8000)
    model: str = DEFAULT_AI_MODEL


class SendAiMessageResponse(BaseModel):
    conversation_id: str
    user_message: AiMessage
    assistant_message: AiMessage


class RagStatusResponse(BaseModel):
    status: str
    indexed_messages: int = 0
    total_target_messages: int = 50
    last_indexed_at: str | None = None
    error: str | None = None


class StartRagIndexRequest(BaseModel):
    limit: int = Field(default=50, ge=1, le=50)


class StartRagIndexResponse(BaseModel):
    status: RagStatusResponse
