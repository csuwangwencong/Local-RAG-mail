from __future__ import annotations

from fastapi import APIRouter, Cookie, Response

from app.api.ai_models import (
    AiConversationDetail,
    AiConversationsResponse,
    AiModelsResponse,
    CreateAiConversationRequest,
    CreateAiConversationResponse,
    RagStatusResponse,
    SendAiMessageRequest,
    SendAiMessageResponse,
    StartRagIndexRequest,
    StartRagIndexResponse,
)
from app.api.models import (
    AccountInfo,
    ConnectRequest,
    ConnectResponse,
    MessageDetail,
    MessageListResponse,
    SessionResponse,
)
from app.core.errors import AppError, invalid_uid_error, session_expired_error
from app.services.ai_store import new_ai_message
from app.services.imap_client import QqImapClient
from app.services.llm_client import llm_client
from app.services.query_preprocessor import preprocess_query
from app.services.rag_store import rag_store
from app.services.safety_guard import SENSITIVE_REPLY, is_sensitive_request
from app.services.session_store import session_store


router = APIRouter(prefix="/api/v1")
COOKIE_NAME = "mail_session"


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/session/connect", response_model=ConnectResponse)
async def connect_mailbox(
    payload: ConnectRequest,
    response: Response,
    mail_session: str | None = Cookie(default=None),
) -> ConnectResponse:
    email = str(payload.email).strip().lower()
    auth_code = payload.auth_code.strip()
    if not email.endswith("@qq.com"):
        raise AppError(400, "UNSUPPORTED_EMAIL_DOMAIN", "当前版本仅支持 @qq.com 邮箱。")
    if not auth_code:
        raise AppError(400, "INVALID_AUTH_CODE", "请输入 QQ 邮箱授权码。")
    await session_store.remove(mail_session)
    client = QqImapClient()
    inbox = await client.connect(email, auth_code)
    session = await session_store.create(email, client, inbox)
    response.set_cookie(
        COOKIE_NAME,
        session.session_id,
        httponly=True,
        samesite="strict",
        secure=False,
        max_age=1800,
        path="/",
    )
    return ConnectResponse(account=AccountInfo(email=email), inbox=inbox)


@router.get("/session", response_model=SessionResponse)
async def get_session(mail_session: str | None = Cookie(default=None)) -> SessionResponse:
    session = await session_store.get(mail_session)
    if not session:
        raise session_expired_error()
    async with session.lock:
        session.inbox = await session.client.status()
    return SessionResponse(
        connected=True,
        account=AccountInfo(email=session.email),
        inbox=session.inbox,
    )


@router.delete("/session", status_code=204)
async def disconnect(response: Response, mail_session: str | None = Cookie(default=None)) -> None:
    await session_store.remove(mail_session)
    response.delete_cookie(COOKIE_NAME, path="/")


@router.get("/inbox/messages", response_model=MessageListResponse)
async def list_messages(
    limit: int = 30,
    before_uid: str | None = None,
    mail_session: str | None = Cookie(default=None),
) -> MessageListResponse:
    if limit < 1 or limit > 50:
        raise AppError(400, "INVALID_REQUEST", "limit 必须在 1 到 50 之间。")
    if before_uid is not None and (not before_uid.isdigit() or int(before_uid) <= 0):
        raise invalid_uid_error()
    session = await session_store.get(mail_session)
    if not session:
        raise session_expired_error()
    async with session.lock:
        mailbox, fetched_items = await session.client.list_messages(limit + 1, before_uid)
    items = fetched_items[:limit]
    next_before_uid = items[-1].uid if items else before_uid
    return MessageListResponse(
        mailbox=mailbox,
        items=items,
        next_before_uid=next_before_uid,
        has_more=len(fetched_items) > limit,
    )


@router.get("/inbox/messages/{uid}", response_model=MessageDetail, response_model_by_alias=True)
async def get_message(
    uid: str,
    mail_session: str | None = Cookie(default=None),
) -> MessageDetail:
    if not uid.isdigit() or int(uid) <= 0:
        raise invalid_uid_error()
    session = await session_store.get(mail_session)
    if not session:
        raise session_expired_error()
    async with session.lock:
        return await session.client.get_message(uid)


@router.get("/ai/models", response_model=AiModelsResponse)
async def list_ai_models(mail_session: str | None = Cookie(default=None)) -> AiModelsResponse:
    session = await session_store.get(mail_session)
    if not session:
        raise session_expired_error()
    return AiModelsResponse(items=await llm_client.list_models())


@router.get("/rag/status", response_model=RagStatusResponse)
async def get_rag_status(mail_session: str | None = Cookie(default=None)) -> RagStatusResponse:
    session = await session_store.get(mail_session)
    if not session:
        raise session_expired_error()
    return await rag_store.status(session.email)


@router.post("/rag/index", response_model=StartRagIndexResponse)
async def start_rag_index(
    payload: StartRagIndexRequest,
    mail_session: str | None = Cookie(default=None),
) -> StartRagIndexResponse:
    session = await session_store.get(mail_session)
    if not session:
        raise session_expired_error()

    async with session.lock:
        _mailbox, summaries = await session.client.list_messages(payload.limit, None)
        details: list[MessageDetail] = []
        for summary in summaries[: payload.limit]:
            try:
                details.append(await session.client.get_message(summary.uid))
            except AppError as exc:
                if exc.code in {"MESSAGE_TOO_LARGE", "MESSAGE_NOT_FOUND"}:
                    continue
                raise
    status = await rag_store.rebuild(session.email, summaries, details, payload.limit)
    return StartRagIndexResponse(status=status)


@router.get("/ai/conversations", response_model=AiConversationsResponse)
async def list_ai_conversations(
    mail_session: str | None = Cookie(default=None),
) -> AiConversationsResponse:
    session = await session_store.get(mail_session)
    if not session:
        raise session_expired_error()
    return AiConversationsResponse(items=session.ai_conversations.list())


@router.post("/ai/conversations", response_model=CreateAiConversationResponse)
async def create_ai_conversation(
    payload: CreateAiConversationRequest,
    mail_session: str | None = Cookie(default=None),
) -> CreateAiConversationResponse:
    session = await session_store.get(mail_session)
    if not session:
        raise session_expired_error()
    if not await llm_client.model_available(payload.model):
        raise AppError(400, "AI_MODEL_UNSUPPORTED", "当前版本不支持该模型。")
    conversation = session.ai_conversations.create(payload.model, payload.title)
    return CreateAiConversationResponse(conversation=conversation.to_detail())


@router.get("/ai/conversations/{conversation_id}", response_model=AiConversationDetail)
async def get_ai_conversation(
    conversation_id: str,
    mail_session: str | None = Cookie(default=None),
) -> AiConversationDetail:
    session = await session_store.get(mail_session)
    if not session:
        raise session_expired_error()
    conversation = session.ai_conversations.get(conversation_id)
    if not conversation:
        raise AppError(404, "AI_CONVERSATION_NOT_FOUND", "对话不存在。")
    return conversation.to_detail()


@router.delete("/ai/conversations/{conversation_id}", status_code=204)
async def delete_ai_conversation(
    conversation_id: str,
    mail_session: str | None = Cookie(default=None),
) -> None:
    session = await session_store.get(mail_session)
    if not session:
        raise session_expired_error()
    session.ai_conversations.delete(conversation_id)


@router.post("/ai/conversations/{conversation_id}/messages", response_model=SendAiMessageResponse)
async def send_ai_message(
    conversation_id: str,
    payload: SendAiMessageRequest,
    mail_session: str | None = Cookie(default=None),
) -> SendAiMessageResponse:
    content = payload.content.strip()
    if not content:
        raise AppError(400, "AI_MESSAGE_TOO_LONG", "请输入问题内容。")
    session = await session_store.get(mail_session)
    if not session:
        raise session_expired_error()
    conversation = session.ai_conversations.get(conversation_id)
    if not conversation:
        raise AppError(404, "AI_CONVERSATION_NOT_FOUND", "对话不存在。")

    user_message = new_ai_message("user", content)
    if is_sensitive_request(content):
        assistant_message = new_ai_message("assistant", SENSITIVE_REPLY)
        conversation.append(user_message)
        conversation.append(assistant_message)
        return SendAiMessageResponse(
            conversation_id=conversation.conversation_id,
            user_message=user_message,
            assistant_message=assistant_message,
        )

    if not await llm_client.model_available(payload.model):
        raise AppError(400, "AI_MODEL_UNSUPPORTED", "当前版本不支持该模型。")
    processed_query = preprocess_query(content, conversation.messages)
    sources = await rag_store.retrieve(session.email, processed_query)
    assistant_content = await llm_client.chat(payload.model, [*conversation.messages, user_message], sources)
    assistant_message = new_ai_message("assistant", assistant_content)
    assistant_message.sources = sources
    conversation.model = payload.model
    conversation.append(user_message)
    conversation.append(assistant_message)
    return SendAiMessageResponse(
        conversation_id=conversation.conversation_id,
        user_message=user_message,
        assistant_message=assistant_message,
    )
