from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import socket
import sqlite3
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime
from html import unescape
from pathlib import Path
from typing import Any

from app.api.ai_models import AiSource, RagStatusResponse
from app.api.models import MessageDetail, MessageSummary
from app.core.errors import AppError
from app.services.query_preprocessor import ProcessedQuery


RAG_TARGET_MESSAGES = 50
VECTOR_TOP_K = 12
BM25_TOP_K = 12
RERANK_CANDIDATE_K = 20
FINAL_TOP_K = 8
RRF_K = 60
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 160
DEFAULT_OLLAMA_URL = "http://127.0.0.1:11434"
DEFAULT_EMBED_MODEL = "bge-m3:latest"
DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "rag"


@dataclass(frozen=True)
class RagChunk:
    chunk_id: str
    uid: str
    subject: str
    sender_name: str
    sender_address: str
    received_at: str | None
    chunk_index: int
    text: str


class OllamaEmbeddingClient:
    def __init__(self) -> None:
        self.base_url = os.getenv("OLLAMA_BASE_URL", DEFAULT_OLLAMA_URL).rstrip("/")
        self.model = os.getenv("LOCAL_EMBED_MODEL", DEFAULT_EMBED_MODEL)
        self.timeout = int(os.getenv("LOCAL_EMBED_TIMEOUT_SECONDS", "300"))

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return await asyncio.to_thread(self._embed_sync, texts)

    def _embed_sync(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        payload = {"model": self.model, "input": texts}
        request = urllib.request.Request(
            f"{self.base_url}/api/embed",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                data = json.loads(response.read().decode("utf-8"))
        except (TimeoutError, socket.timeout) as exc:
            raise AppError(504, "RAG_EMBED_TIMEOUT", "本地 embedding 模型响应超时。") from exc
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                raise AppError(502, "RAG_EMBED_MODEL_NOT_AVAILABLE", "本地 embedding 模型不可用。") from exc
            raise AppError(502, "RAG_EMBED_ERROR", "本地 embedding 服务返回异常。") from exc
        except urllib.error.URLError as exc:
            raise AppError(502, "RAG_EMBED_ERROR", "无法连接本地 Ollama embedding 服务。") from exc
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            raise AppError(502, "RAG_EMBED_ERROR", "本地 embedding 响应格式异常。") from exc

        embeddings = data.get("embeddings")
        if not isinstance(embeddings, list):
            raise AppError(502, "RAG_EMBED_ERROR", "本地 embedding 响应格式异常。")
        return embeddings


class HybridRagStore:
    def __init__(self) -> None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.sqlite_path = DATA_DIR / "localmail.sqlite3"
        self.chroma_path = DATA_DIR / "chroma"
        self.embedding = OllamaEmbeddingClient()
        self._init_sqlite()

    async def status(self, email: str) -> RagStatusResponse:
        return await asyncio.to_thread(self._status_sync, account_hash(email))

    async def rebuild(
        self,
        email: str,
        summaries: list[MessageSummary],
        details: list[MessageDetail],
        target_messages: int = RAG_TARGET_MESSAGES,
    ) -> RagStatusResponse:
        chunks = details_to_chunks(email, summaries, details)
        embeddings = await self.embedding.embed([chunk.text for chunk in chunks])
        return await asyncio.to_thread(
            self._rebuild_sync,
            account_hash(email),
            target_messages,
            chunks,
            embeddings,
        )

    async def retrieve(self, email: str, query: ProcessedQuery) -> list[AiSource]:
        if not query.need_rag or not query.normalized_query:
            return []
        status = await self.status(email)
        if status.status != "ready":
            return []
        query_embedding = (await self.embedding.embed([query.vector_query or query.normalized_query]))[0]
        return await asyncio.to_thread(self._retrieve_sync, account_hash(email), query, query_embedding)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.sqlite_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _init_sqlite(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS rag_status (
                  account_hash TEXT PRIMARY KEY,
                  status TEXT NOT NULL,
                  indexed_messages INTEGER NOT NULL DEFAULT 0,
                  total_target_messages INTEGER NOT NULL DEFAULT 50,
                  last_indexed_at TEXT,
                  error TEXT
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS mail_chunks (
                  account_hash TEXT NOT NULL,
                  chunk_id TEXT PRIMARY KEY,
                  uid TEXT NOT NULL,
                  subject TEXT NOT NULL,
                  sender_name TEXT NOT NULL,
                  sender_address TEXT NOT NULL,
                  received_at TEXT,
                  chunk_index INTEGER NOT NULL,
                  body TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS mail_chunks_fts USING fts5(
                  chunk_id UNINDEXED,
                  account_hash UNINDEXED,
                  uid UNINDEXED,
                  subject,
                  sender,
                  body
                )
                """
            )

    def _status_sync(self, acc_hash: str) -> RagStatusResponse:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM rag_status WHERE account_hash = ?",
                (acc_hash,),
            ).fetchone()
        if row is None:
            return RagStatusResponse(status="not_built")
        return RagStatusResponse(
            status=row["status"],
            indexed_messages=row["indexed_messages"],
            total_target_messages=row["total_target_messages"],
            last_indexed_at=row["last_indexed_at"],
            error=row["error"],
        )

    def _rebuild_sync(
        self,
        acc_hash: str,
        target_messages: int,
        chunks: list[RagChunk],
        embeddings: list[list[float]],
    ) -> RagStatusResponse:
        if len(chunks) != len(embeddings):
            raise AppError(502, "RAG_EMBED_ERROR", "embedding 数量与邮件片段数量不一致。")
        indexed_messages = len({chunk.uid for chunk in chunks})
        now = datetime.now(UTC).astimezone().isoformat()
        self._set_status(acc_hash, "indexing", 0, target_messages, None, None)
        try:
            self._reset_account(acc_hash)
            if chunks:
                self._upsert_chroma(acc_hash, chunks, embeddings)
                self._insert_sqlite_chunks(acc_hash, chunks)
            self._set_status(acc_hash, "ready", indexed_messages, target_messages, now, None)
        except Exception as exc:
            if isinstance(exc, AppError):
                message = exc.message
            else:
                message = "知识库构建失败。"
            self._set_status(acc_hash, "error", 0, target_messages, None, message)
            if isinstance(exc, AppError):
                raise
            raise AppError(500, "RAG_INDEX_ERROR", "知识库构建失败。") from exc
        return self._status_sync(acc_hash)

    def _set_status(
        self,
        acc_hash: str,
        status: str,
        indexed_messages: int,
        target_messages: int,
        last_indexed_at: str | None,
        error: str | None,
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO rag_status (
                  account_hash, status, indexed_messages, total_target_messages, last_indexed_at, error
                )
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(account_hash) DO UPDATE SET
                  status = excluded.status,
                  indexed_messages = excluded.indexed_messages,
                  total_target_messages = excluded.total_target_messages,
                  last_indexed_at = excluded.last_indexed_at,
                  error = excluded.error
                """,
                (acc_hash, status, indexed_messages, target_messages, last_indexed_at, error),
            )

    def _reset_account(self, acc_hash: str) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM mail_chunks WHERE account_hash = ?", (acc_hash,))
            connection.execute("DELETE FROM mail_chunks_fts WHERE account_hash = ?", (acc_hash,))
        collection = self._collection(acc_hash)
        existing = collection.get(include=[])
        ids = existing.get("ids", [])
        if ids:
            collection.delete(ids=ids)

    def _insert_sqlite_chunks(self, acc_hash: str, chunks: list[RagChunk]) -> None:
        rows = [
            (
                acc_hash,
                chunk.chunk_id,
                chunk.uid,
                chunk.subject,
                chunk.sender_name,
                chunk.sender_address,
                chunk.received_at,
                chunk.chunk_index,
                chunk.text,
            )
            for chunk in chunks
        ]
        with self._connect() as connection:
            connection.executemany(
                """
                INSERT INTO mail_chunks (
                  account_hash, chunk_id, uid, subject, sender_name, sender_address,
                  received_at, chunk_index, body
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
            connection.executemany(
                """
                INSERT INTO mail_chunks_fts (chunk_id, account_hash, uid, subject, sender, body)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        chunk.chunk_id,
                        acc_hash,
                        chunk.uid,
                        chunk.subject,
                        f"{chunk.sender_name} {chunk.sender_address}".strip(),
                        chunk.text,
                    )
                    for chunk in chunks
                ],
            )

    def _upsert_chroma(
        self,
        acc_hash: str,
        chunks: list[RagChunk],
        embeddings: list[list[float]],
    ) -> None:
        collection = self._collection(acc_hash)
        collection.upsert(
            ids=[chunk.chunk_id for chunk in chunks],
            documents=[chunk.text for chunk in chunks],
            embeddings=embeddings,
            metadatas=[
                {
                    "uid": chunk.uid,
                    "subject": chunk.subject,
                    "sender_name": chunk.sender_name,
                    "sender_address": chunk.sender_address,
                    "received_at": chunk.received_at or "",
                    "chunk_index": chunk.chunk_index,
                }
                for chunk in chunks
            ],
        )

    def _retrieve_sync(
        self,
        acc_hash: str,
        query: ProcessedQuery,
        query_embedding: list[float],
    ) -> list[AiSource]:
        vector_ids = self._vector_search_ids(acc_hash, query_embedding)
        bm25_ids = self._bm25_search_ids(acc_hash, query)
        fused_ids = rrf_fuse([vector_ids, bm25_ids])[:RERANK_CANDIDATE_K]
        if not fused_ids:
            return []
        ranked_ids = self._rerank_ids(acc_hash, fused_ids, query)[:FINAL_TOP_K]
        return self._chunks_to_sources(acc_hash, ranked_ids)

    def _vector_search_ids(self, acc_hash: str, query_embedding: list[float]) -> list[str]:
        collection = self._collection(acc_hash)
        result = collection.query(
            query_embeddings=[query_embedding],
            n_results=VECTOR_TOP_K,
            include=["metadatas"],
        )
        ids = result.get("ids", [[]])
        return [item for item in ids[0] if isinstance(item, str)]

    def _bm25_search_ids(self, acc_hash: str, query: ProcessedQuery) -> list[str]:
        match_query = query.bm25_query or build_fts_query(query.normalized_query)
        if not match_query:
            return []
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT chunk_id
                FROM mail_chunks_fts
                WHERE mail_chunks_fts MATCH ? AND account_hash = ?
                ORDER BY bm25(mail_chunks_fts)
                LIMIT ?
                """,
                (match_query, acc_hash, BM25_TOP_K),
            ).fetchall()
        return [row["chunk_id"] for row in rows]

    def _rerank_ids(self, acc_hash: str, chunk_ids: list[str], query: ProcessedQuery) -> list[str]:
        if not chunk_ids:
            return []
        rows = self._fetch_chunk_rows(acc_hash, chunk_ids)
        by_id = {row["chunk_id"]: row for row in rows}
        rrf_scores = {chunk_id: 1 / (RRF_K + rank) for rank, chunk_id in enumerate(chunk_ids, start=1)}
        scored = []
        for chunk_id in chunk_ids:
            row = by_id.get(chunk_id)
            if row is None:
                continue
            scored.append(
                (
                    chunk_id,
                    rrf_scores.get(chunk_id, 0) + rule_rerank_score(row, query),
                )
            )
        return [chunk_id for chunk_id, _score in sorted(scored, key=lambda item: item[1], reverse=True)]

    def _chunks_to_sources(self, acc_hash: str, chunk_ids: list[str]) -> list[AiSource]:
        rows = self._fetch_chunk_rows(acc_hash, chunk_ids)
        by_id = {row["chunk_id"]: row for row in rows}
        seen_uids: set[str] = set()
        sources: list[AiSource] = []
        for rank, chunk_id in enumerate(chunk_ids, start=1):
            row = by_id.get(chunk_id)
            if row is None or row["uid"] in seen_uids:
                continue
            seen_uids.add(row["uid"])
            sources.append(
                AiSource(
                    title=row["subject"],
                    uid=row["uid"],
                    snippet=trim_snippet(row["body"]),
                    sender_name=row["sender_name"],
                    sender_address=row["sender_address"],
                    received_at=row["received_at"],
                    score=1 / (RRF_K + rank),
                    source_type="hybrid",
                )
            )
        return sources

    def _fetch_chunk_rows(self, acc_hash: str, chunk_ids: list[str]) -> list[sqlite3.Row]:
        placeholders = ",".join("?" for _ in chunk_ids)
        params = [acc_hash, *chunk_ids]
        with self._connect() as connection:
            return connection.execute(
                f"""
                SELECT *
                FROM mail_chunks
                WHERE account_hash = ? AND chunk_id IN ({placeholders})
                """,
                params,
            ).fetchall()

    def _collection(self, acc_hash: str) -> Any:
        try:
            import chromadb
        except ImportError as exc:
            raise AppError(500, "RAG_VECTOR_STORE_UNAVAILABLE", "Chroma 未安装或不可用。") from exc
        client = chromadb.PersistentClient(path=str(self.chroma_path))
        return client.get_or_create_collection(
            name=f"mail_chunks_{acc_hash[:16]}",
            metadata={"hnsw:space": "cosine"},
        )


def account_hash(email: str) -> str:
    return hashlib.sha256(email.strip().lower().encode("utf-8")).hexdigest()


def details_to_chunks(
    email: str,
    summaries: list[MessageSummary],
    details: list[MessageDetail],
) -> list[RagChunk]:
    summary_by_uid = {summary.uid: summary for summary in summaries}
    chunks: list[RagChunk] = []
    for detail in details:
        text = message_text(detail)
        if not text:
            continue
        summary = summary_by_uid.get(detail.uid)
        sender = detail.from_[0] if detail.from_ else summary.sender if summary else None
        subject = detail.subject or summary.subject if summary else detail.subject
        for index, chunk_text in enumerate(split_chunks(text)):
            chunks.append(
                RagChunk(
                    chunk_id=f"{account_hash(email)[:16]}:{detail.uid}:{index}",
                    uid=detail.uid,
                    subject=subject or "无主题",
                    sender_name=sender.name if sender else "",
                    sender_address=sender.address if sender else "",
                    received_at=detail.received_at,
                    chunk_index=index,
                    text=chunk_text,
                )
            )
    return chunks


def message_text(detail: MessageDetail) -> str:
    if detail.body.type == "html" and detail.body.html:
        raw = html_to_text(detail.body.html)
    else:
        raw = detail.body.text or ""
    lines = [
        f"主题：{detail.subject or '无主题'}",
        f"发件人：{format_sources_sender(detail)}",
        f"时间：{detail.received_at or ''}",
        raw,
    ]
    return normalize_text("\n".join(lines))


def format_sources_sender(detail: MessageDetail) -> str:
    if not detail.from_:
        return ""
    return "; ".join(
        f"{address.name} <{address.address}>" if address.name else address.address
        for address in detail.from_
    )


def html_to_text(html: str) -> str:
    text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", "", html)
    text = re.sub(r"(?s)<br\s*/?>", "\n", text)
    text = re.sub(r"(?s)</p\s*>", "\n", text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    return unescape(text)


def normalize_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def split_chunks(text: str) -> list[str]:
    if len(text) <= CHUNK_SIZE:
        return [text]
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(len(text), start + CHUNK_SIZE)
        chunks.append(text[start:end].strip())
        if end == len(text):
            break
        start = max(0, end - CHUNK_OVERLAP)
    return [chunk for chunk in chunks if chunk]


def build_fts_query(query: str) -> str:
    terms = re.findall(r"[\w.@:+-]+", query, flags=re.UNICODE)
    if not terms:
        query = query.replace('"', '""').strip()
        return f'"{query}"' if query else ""
    quoted = []
    for term in terms[:8]:
        safe = term.replace('"', '""')
        quoted.append(f'"{safe}"')
    return " OR ".join(quoted)


def rule_rerank_score(row: sqlite3.Row, query: ProcessedQuery) -> float:
    subject = (row["subject"] or "").lower()
    sender = f"{row['sender_name'] or ''} {row['sender_address'] or ''}".lower()
    body = (row["body"] or "").lower()
    score = 0.0
    terms = query.expanded_keywords or query.keywords
    for term in terms:
        normalized = term.lower().strip()
        if not normalized:
            continue
        if normalized in sender:
            score += 0.16
        if normalized in subject:
            score += 0.12
        if normalized in body:
            score += 0.04
    for hint in query.sender_hints:
        normalized = hint.lower().strip()
        if normalized and normalized in sender:
            score += 0.18
    for hint in query.subject_hints:
        normalized = hint.lower().strip()
        if normalized and normalized in subject:
            score += 0.08
    if query.intent == "find_email":
        score += 0.03
    elif query.intent == "summarize_email":
        score += 0.02

    received_at = row["received_at"]
    if received_at:
        try:
            received = datetime.fromisoformat(received_at)
            now = datetime.now(received.tzinfo or UTC)
            age_days = max(0, (now - received).days)
            if age_days <= 30:
                score += 0.02
            elif age_days <= 90:
                score += 0.01
        except ValueError:
            pass
    return score


def rrf_fuse(rankings: list[list[str]]) -> list[str]:
    scores: dict[str, float] = {}
    for ranking in rankings:
        for rank, chunk_id in enumerate(ranking, start=1):
            scores[chunk_id] = scores.get(chunk_id, 0) + 1 / (RRF_K + rank)
    return [chunk_id for chunk_id, _score in sorted(scores.items(), key=lambda item: item[1], reverse=True)]


def trim_snippet(text: str, limit: int = 160) -> str:
    compact = re.sub(r"\s+", " ", text).strip()
    return compact if len(compact) <= limit else f"{compact[:limit]}..."


rag_store = HybridRagStore()
