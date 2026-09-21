from __future__ import annotations

from email import policy
from email.header import decode_header
from email.message import EmailMessage, Message
from email.parser import BytesParser
from email.utils import getaddresses, parsedate_to_datetime
from html import unescape
import re

from app.api.models import MailAddress, MessageBody, MessageDetail


EMPTY_SUBJECT = "无主题"


def parse_message(raw: bytes, uid: str) -> MessageDetail:
    message = BytesParser(policy=policy.default).parsebytes(raw)
    subject = decode_mime_header(message.get("Subject")) or EMPTY_SUBJECT
    body = extract_body(message)
    return MessageDetail(
        uid=uid,
        subject=subject,
        from_=parse_addresses(message.get_all("From", [])),
        to=parse_addresses(message.get_all("To", [])),
        cc=parse_addresses(message.get_all("Cc", [])),
        received_at=parse_date(message.get("Date")),
        body=body,
    )


def decode_mime_header(value: str | None) -> str:
    if not value:
        return ""
    parts: list[str] = []
    for decoded, charset in decode_header(value):
        if isinstance(decoded, bytes):
            enc = charset or "utf-8"
            try:
                parts.append(decoded.decode(enc, errors="replace"))
            except LookupError:
                parts.append(decoded.decode("utf-8", errors="replace"))
        else:
            parts.append(decoded)
    return "".join(parts).strip()


def parse_addresses(values: list[str] | tuple[str, ...]) -> list[MailAddress]:
    result: list[MailAddress] = []
    for name, address in getaddresses(values):
        if not address:
            continue
        result.append(MailAddress(name=decode_mime_header(name), address=address))
    return result


def parse_date(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return parsedate_to_datetime(value).isoformat()
    except (TypeError, ValueError, IndexError, OverflowError):
        return None


def extract_body(message: EmailMessage | Message) -> MessageBody:
    html = first_body_part(message, "html")
    text = first_body_part(message, "plain")
    if html is not None:
        return MessageBody(type="html", html=html, text=text or html_to_text(html))
    if text is not None:
        return MessageBody(type="text", html=None, text=text)
    return MessageBody(type="empty", html=None, text=None)


def first_body_part(message: EmailMessage | Message, subtype: str) -> str | None:
    if message.is_multipart():
        for part in message.walk():
            if part.is_multipart() or is_attachment(part):
                continue
            if part.get_content_type() == f"text/{subtype}":
                return decode_part(part)
        return None
    if not is_attachment(message) and message.get_content_type() == f"text/{subtype}":
        return decode_part(message)
    return None


def is_attachment(part: EmailMessage | Message) -> bool:
    disposition = (part.get_content_disposition() or "").lower()
    return disposition == "attachment"


def decode_part(part: EmailMessage | Message) -> str:
    payload = part.get_payload(decode=True)
    if payload is None:
        value = part.get_payload()
        return value if isinstance(value, str) else ""
    charset = part.get_content_charset() or "utf-8"
    try:
        return payload.decode(charset, errors="replace")
    except LookupError:
        return payload.decode("utf-8", errors="replace")


def html_to_text(html: str) -> str:
    text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", "", html)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", unescape(text)).strip()
