from __future__ import annotations

import asyncio
import secrets
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from app.api.models import InboxStatus
from app.services.ai_store import AiConversationStore
from app.services.imap_client import QqImapClient


SESSION_TTL = timedelta(minutes=30)


@dataclass
class MailSession:
    session_id: str
    email: str
    client: QqImapClient
    inbox: InboxStatus
    ai_conversations: AiConversationStore = field(default_factory=AiConversationStore)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    last_accessed: datetime = field(default_factory=lambda: datetime.now(UTC))

    def touch(self) -> None:
        self.last_accessed = datetime.now(UTC)


class SessionStore:
    def __init__(self) -> None:
        self._sessions: dict[str, MailSession] = {}
        self._lock = asyncio.Lock()

    async def create(self, email: str, client: QqImapClient, inbox: InboxStatus) -> MailSession:
        session = MailSession(secrets.token_urlsafe(32), email, client, inbox)
        async with self._lock:
            self._sessions[session.session_id] = session
        return session

    async def get(self, session_id: str | None) -> MailSession | None:
        if not session_id:
            return None
        async with self._lock:
            session = self._sessions.get(session_id)
            if session:
                session.touch()
            return session

    async def remove(self, session_id: str | None) -> None:
        if not session_id:
            return
        async with self._lock:
            session = self._sessions.pop(session_id, None)
        if session:
            await session.client.close()

    async def cleanup_expired(self) -> int:
        cutoff = datetime.now(UTC) - SESSION_TTL
        async with self._lock:
            expired = [
                session_id
                for session_id, session in self._sessions.items()
                if session.last_accessed < cutoff
            ]
            sessions = [self._sessions.pop(session_id) for session_id in expired]
        for session in sessions:
            await session.client.close()
        return len(sessions)

    async def close_all(self) -> None:
        async with self._lock:
            sessions = list(self._sessions.values())
            self._sessions.clear()
        for session in sessions:
            await session.client.close()


session_store = SessionStore()
