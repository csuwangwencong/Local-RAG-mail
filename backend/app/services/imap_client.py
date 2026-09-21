from __future__ import annotations

import asyncio
import imaplib
import re
import socket
import ssl
from dataclasses import dataclass
from datetime import datetime, timedelta
from email import policy
from email.parser import BytesHeaderParser
from email.utils import parsedate_to_datetime
from typing import Any

from app.api.models import InboxStatus, MailAddress, MessageDetail, MessageSummary
from app.core.errors import AppError
from app.services.mime_parser import EMPTY_SUBJECT, decode_mime_header, parse_addresses, parse_message


IMAP_HOST = "imap.qq.com"
IMAP_PORT = 993
MAILBOX = "INBOX"
MAX_MESSAGE_BYTES = 8 * 1024 * 1024
SEARCH_WINDOWS_DAYS = [30, 90, 180, 365, 1095, 3650]


@dataclass(frozen=True)
class SummaryWithArrival:
    summary: MessageSummary
    arrival_ts: float


class QqImapClient:
    def __init__(self) -> None:
        self._imap: imaplib.IMAP4_SSL | None = None

    async def connect(self, email: str, auth_code: str) -> InboxStatus:
        try:
            return await asyncio.to_thread(self._connect_sync, email, auth_code)
        except imaplib.IMAP4.error as exc:
            raise AppError(401, "IMAP_AUTH_FAILED", "邮箱账号或授权码错误，或 IMAP 未开启。") from exc
        except (TimeoutError, socket.timeout) as exc:
            raise AppError(504, "IMAP_TIMEOUT", "连接或读取 QQ 邮箱超时。") from exc
        except OSError as exc:
            raise AppError(502, "IMAP_SERVER_ERROR", "QQ 邮箱服务暂时不可用。") from exc

    def _connect_sync(self, email: str, auth_code: str) -> InboxStatus:
        context = ssl.create_default_context()
        imap = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT, ssl_context=context, timeout=20)
        imap.login(email, auth_code)
        status, data = imap.select(MAILBOX, readonly=True)
        if status != "OK":
            raise AppError(502, "IMAP_SERVER_ERROR", "无法打开收件箱。")
        self._imap = imap
        total = _int_from_first(data)
        unread = self._search_unseen_sync()
        return InboxStatus(total=total, unread=unread)

    async def close(self) -> None:
        await asyncio.to_thread(self._close_sync)

    def _close_sync(self) -> None:
        if not self._imap:
            return
        try:
            self._imap.close()
        except imaplib.IMAP4.error:
            pass
        try:
            self._imap.logout()
        except imaplib.IMAP4.error:
            pass
        self._imap = None

    async def status(self) -> InboxStatus:
        return await asyncio.to_thread(self._status_sync)

    def _status_sync(self) -> InboxStatus:
        imap = self._require_imap()
        status, data = imap.select(MAILBOX, readonly=True)
        if status != "OK":
            raise AppError(409, "MAILBOX_NOT_CONNECTED", "邮箱连接已失效。")
        return InboxStatus(total=_int_from_first(data), unread=self._search_unseen_sync())

    async def list_messages(self, limit: int, before_uid: str | None) -> tuple[InboxStatus, list[MessageSummary]]:
        return await asyncio.to_thread(self._list_messages_sync, limit, before_uid)

    def _list_messages_sync(self, limit: int, before_uid: str | None) -> tuple[InboxStatus, list[MessageSummary]]:
        mailbox = self._status_sync()
        entries = self._sorted_summaries_by_arrival_sync(limit, before_uid)
        return mailbox, [entry.summary for entry in entries]

    def _sorted_summaries_by_arrival_sync(
        self,
        limit: int,
        before_uid: str | None,
    ) -> list[SummaryWithArrival]:
        windows = self._candidate_uid_windows_sync()
        for index, uids in enumerate(windows):
            is_last_window = index == len(windows) - 1
            entries = [self._fetch_summary_with_arrival_sync(uid) for uid in uids]
            entries.sort(key=lambda item: item.arrival_ts, reverse=True)
            try:
                start = [item.summary.uid for item in entries].index(before_uid) + 1 if before_uid else 0
            except ValueError:
                continue
            page = entries[start : start + limit]
            if len(page) >= limit or is_last_window:
                return page
        return []

    def _candidate_uid_windows_sync(self) -> list[list[str]]:
        imap = self._require_imap()
        today = datetime.now().date()
        windows: list[list[str]] = []
        seen_keys: set[tuple[str, ...]] = set()
        for days in SEARCH_WINDOWS_DAYS:
            since = (today - timedelta(days=days)).strftime("%d-%b-%Y")
            status, data = imap.uid("SEARCH", None, f"SINCE {since}")
            if status != "OK":
                raise AppError(502, "IMAP_SERVER_ERROR", "无法读取邮件列表。")
            uids = (data[0] or b"").decode().split()
            key = tuple(uids)
            if key not in seen_keys:
                seen_keys.add(key)
                windows.append(uids)
        status, data = imap.uid("SEARCH", None, "ALL")
        if status != "OK":
            raise AppError(502, "IMAP_SERVER_ERROR", "无法读取邮件列表。")
        all_uids = (data[0] or b"").decode().split()
        if tuple(all_uids) not in seen_keys:
            windows.append(all_uids)
        return windows

    def _sorted_uids_sync(self) -> list[str]:
        imap = self._require_imap()
        try:
            status, data = imap.uid("SORT", "(REVERSE ARRIVAL)", "UTF-8", "ALL")
            if status == "OK":
                return (data[0] or b"").decode().split()
        except imaplib.IMAP4.error:
            pass
        status, data = imap.uid("SEARCH", None, "ALL")
        if status != "OK":
            raise AppError(502, "IMAP_SERVER_ERROR", "无法读取邮件列表。")
        return list(reversed((data[0] or b"").decode().split()))

    def _fetch_summary_sync(self, uid: str) -> MessageSummary:
        return self._fetch_summary_with_arrival_sync(uid).summary

    def _fetch_summary_with_arrival_sync(self, uid: str) -> SummaryWithArrival:
        imap = self._require_imap()
        status, data = imap.uid(
            "FETCH",
            uid,
            "(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE)] INTERNALDATE FLAGS RFC822.SIZE)",
        )
        if status != "OK":
            raise AppError(502, "IMAP_SERVER_ERROR", "无法读取邮件摘要。")
        header_bytes = b""
        meta = b""
        for item in data:
            if isinstance(item, tuple):
                meta += item[0]
                header_bytes += item[1]
            elif isinstance(item, bytes):
                meta += item
        message = BytesHeaderParser(policy=policy.default).parsebytes(header_bytes)
        subject = decode_mime_header(message.get("Subject")) or EMPTY_SUBJECT
        sender = (parse_addresses(message.get_all("From", [])) or [MailAddress(address="")])[0]
        received_at = _extract_internal_date(meta) or _parse_date(message.get("Date"))
        summary = MessageSummary(
            uid=uid,
            subject=subject,
            sender=sender,
            received_at=received_at,
            is_read=b"\\Seen" in meta,
            size=_extract_size(meta),
        )
        return SummaryWithArrival(summary=summary, arrival_ts=_extract_internal_timestamp(meta, received_at))

    async def get_message(self, uid: str) -> MessageDetail:
        return await asyncio.to_thread(self._get_message_sync, uid)

    def _get_message_sync(self, uid: str) -> MessageDetail:
        imap = self._require_imap()
        status, data = imap.uid("FETCH", uid, "(RFC822.SIZE)")
        if status != "OK" or not data or data == [None]:
            raise AppError(404, "MESSAGE_NOT_FOUND", "邮件不存在。")
        size = _extract_size(b" ".join(x for x in data if isinstance(x, bytes)))
        if size > MAX_MESSAGE_BYTES:
            raise AppError(413, "MESSAGE_TOO_LARGE", "邮件超过大小限制。")
        status, data = imap.uid("FETCH", uid, "(INTERNALDATE BODY.PEEK[])")
        if status != "OK" or not data:
            raise AppError(404, "MESSAGE_NOT_FOUND", "邮件不存在。")
        meta = b""
        raw = b"".join(item[1] for item in data if isinstance(item, tuple) and isinstance(item[1], bytes))
        for item in data:
            if isinstance(item, tuple):
                meta += item[0]
            elif isinstance(item, bytes):
                meta += item
        if not raw:
            raise AppError(404, "MESSAGE_NOT_FOUND", "邮件不存在。")
        if len(raw) > MAX_MESSAGE_BYTES:
            raise AppError(413, "MESSAGE_TOO_LARGE", "邮件超过大小限制。")
        detail = parse_message(raw, uid)
        detail.received_at = _extract_internal_date(meta) or detail.received_at
        return detail

    def _search_unseen_sync(self) -> int:
        imap = self._require_imap()
        status, data = imap.uid("SEARCH", None, "UNSEEN")
        if status != "OK":
            return 0
        return len((data[0] or b"").decode().split())

    def _require_imap(self) -> imaplib.IMAP4_SSL:
        if self._imap is None:
            raise AppError(409, "MAILBOX_NOT_CONNECTED", "邮箱连接已失效。")
        return self._imap


def _int_from_first(data: list[Any]) -> int:
    if not data:
        return 0
    value = data[0]
    if isinstance(value, bytes):
        return int(value.decode() or "0")
    return int(value or 0)


def _extract_size(value: bytes) -> int:
    match = re.search(rb"RFC822\.SIZE\s+(\d+)", value, re.I)
    return int(match.group(1)) if match else 0


def _extract_internal_date(value: bytes) -> str | None:
    parsed = imaplib.Internaldate2tuple(value)
    if parsed is None:
        return None
    return datetime.fromtimestamp(datetime(*parsed[:6]).timestamp()).astimezone().isoformat()


def _extract_internal_timestamp(value: bytes, fallback_iso: str | None = None) -> float:
    parsed = imaplib.Internaldate2tuple(value)
    if parsed is not None:
        return datetime(*parsed[:6]).timestamp()
    if fallback_iso:
        try:
            return datetime.fromisoformat(fallback_iso).timestamp()
        except (TypeError, ValueError, IndexError, OverflowError):
            return 0
    return 0


def _parse_date(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return parsedate_to_datetime(value).isoformat()
    except (TypeError, ValueError, IndexError, OverflowError):
        return None
