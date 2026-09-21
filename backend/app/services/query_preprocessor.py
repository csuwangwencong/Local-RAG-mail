from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

from app.api.ai_models import AiMessage


MAIL_INTENT_TERMS = (
    "邮件",
    "收件箱",
    "发件",
    "发来",
    "收到",
    "哪封",
    "什么时候",
    "最近",
    "找",
    "查",
    "搜索",
    "总结",
    "汇总",
    "通知",
    "邀请",
    "面试",
    "招聘",
    "账单",
    "订单",
    "验证码",
    "合同",
    "回复",
    "发票",
)

REFERENCE_TERMS = (
    "这",
    "那",
    "这个",
    "那个",
    "它",
    "他",
    "她",
    "该",
    "上述",
    "上面",
    "刚才",
    "前面",
    "这家",
    "这家公司",
    "这个人",
    "这封",
    "那封",
    "还有吗",
    "最近一封",
    "上一封",
    "下一封",
)

WEAK_TERMS = (
    "帮我",
    "请",
    "麻烦",
    "一下",
    "一下子",
    "我想",
    "我要",
    "看看",
    "关于",
    "相关",
    "的",
)

ENTITY_ALIASES = {
    "猎聘": ["猎聘", "liepin", "liepin.com"],
    "boss直聘": ["boss直聘", "BOSS直聘", "boss", "zhipin", "kanzhun"],
    "BOSS直聘": ["boss直聘", "BOSS直聘", "boss", "zhipin", "kanzhun"],
    "联想": ["联想", "lenovo"],
    "腾讯": ["腾讯", "tencent", "qq.com"],
    "阿里": ["阿里", "alibaba"],
    "发票": ["发票", "invoice", "receipt"],
    "账单": ["账单", "付款", "支付", "invoice", "receipt"],
    "简历": ["简历", "CV", "resume"],
    "面试": ["面试", "interview", "邀请"],
    "验证码": ["验证码", "code", "verification"],
}


@dataclass(frozen=True)
class ProcessedQuery:
    original_query: str
    rewritten_query: str | None
    normalized_query: str
    need_rag: bool
    intent: str
    keywords: list[str] = field(default_factory=list)
    expanded_keywords: list[str] = field(default_factory=list)
    sender_hints: list[str] = field(default_factory=list)
    subject_hints: list[str] = field(default_factory=list)
    vector_query: str = ""
    bm25_query: str = ""


def preprocess_query(content: str, history: list[AiMessage]) -> ProcessedQuery:
    original = content.strip()
    normalized_original = normalize_query(original)
    needs_rewrite = has_reference(normalized_original)
    context_entity = find_context_entity(history) if needs_rewrite else ""
    rewritten = f"{context_entity} {original}".strip() if context_entity else None
    working = rewritten or original
    normalized = normalize_query(working)
    intent = detect_intent(normalized)
    keywords = extract_keywords(normalized)
    expanded = expand_keywords(keywords)
    sender_hints = extract_sender_hints(normalized, expanded)
    subject_hints = [keyword for keyword in expanded if keyword not in sender_hints]
    need_rag = should_use_rag(normalized, keywords, intent)
    vector_query = build_vector_query(normalized, keywords, expanded)
    bm25_query = build_bm25_query(expanded or keywords or [normalized])
    return ProcessedQuery(
        original_query=original,
        rewritten_query=rewritten,
        normalized_query=normalized,
        need_rag=need_rag,
        intent=intent,
        keywords=keywords,
        expanded_keywords=expanded,
        sender_hints=sender_hints,
        subject_hints=subject_hints,
        vector_query=vector_query,
        bm25_query=bm25_query,
    )


def normalize_query(query: str) -> str:
    value = unicodedata.normalize("NFKC", query)
    value = value.replace("，", " ").replace("。", " ").replace("？", " ").replace("！", " ")
    value = value.replace(",", " ").replace("?", " ").replace("!", " ")
    for term in WEAK_TERMS:
        value = value.replace(term, " ")
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def has_reference(query: str) -> bool:
    return any(term in query for term in REFERENCE_TERMS)


def detect_intent(query: str) -> str:
    if any(term in query for term in ("总结", "汇总", "归纳")):
        return "summarize_email"
    if any(term in query for term in ("找", "查", "搜索", "哪封", "发", "收到")):
        return "find_email"
    if any(term in query for term in ("什么时候", "谁", "多少", "是否", "有没有")):
        return "ask_fact"
    return "normal_chat"


def should_use_rag(query: str, keywords: list[str], intent: str) -> bool:
    if "不查邮件" in query or "不要检索" in query:
        return False
    mail_term_hit = any(term in query for term in MAIL_INTENT_TERMS)
    entity_hit = any(is_mail_entity(item) for item in keywords)
    if intent in {"find_email", "summarize_email"}:
        return mail_term_hit or entity_hit
    if intent == "ask_fact":
        return mail_term_hit and bool(keywords)
    return mail_term_hit


def extract_keywords(query: str) -> list[str]:
    tokens: list[str] = []
    tokens.extend(re.findall(r"[\w.+-]+@[\w.-]+", query))
    tokens.extend(re.findall(r"[A-Za-z0-9][A-Za-z0-9._:+-]{1,}", query))
    for alias in ENTITY_ALIASES:
        if alias.lower() in query.lower():
            tokens.append(alias)
    for token in re.findall(r"[\u4e00-\u9fff]{2,}", query):
        if token not in MAIL_INTENT_TERMS and token not in WEAK_TERMS and len(token) <= 12:
            tokens.append(token)
    return unique_preserve_order(tokens)


def expand_keywords(keywords: list[str]) -> list[str]:
    expanded: list[str] = []
    for keyword in keywords:
        aliases = ENTITY_ALIASES.get(keyword) or ENTITY_ALIASES.get(keyword.lower())
        expanded.extend(aliases or [keyword])
        if "@" in keyword:
            local, _, domain = keyword.partition("@")
            expanded.extend([local, domain])
            if "." in domain:
                expanded.append(domain.split(".")[0])
    return unique_preserve_order(expanded)


def extract_sender_hints(query: str, expanded: list[str]) -> list[str]:
    if any(term in query for term in ("发", "发来", "发的", "发给", "谁发", "来自")):
        return expanded
    return []


def build_vector_query(normalized: str, keywords: list[str], expanded: list[str]) -> str:
    if keywords and len(normalized) <= 12:
        return " ".join(keywords)
    if expanded:
        return f"{normalized} {' '.join(expanded[:4])}"
    return normalized


def build_bm25_query(terms: list[str]) -> str:
    quoted = []
    for term in unique_preserve_order(terms)[:12]:
        safe = term.replace('"', '""').strip()
        if safe:
            quoted.append(f'"{safe}"')
    return " OR ".join(quoted)


def find_context_entity(history: list[AiMessage]) -> str:
    for message in reversed(history[-8:]):
        if message.role == "assistant" and message.sources:
            for source in message.sources:
                entity = first_entity(" ".join([source.title, source.sender_name, source.sender_address]))
                if entity:
                    return entity
        if message.role == "user":
            entity = first_entity(message.content)
            if entity:
                return entity
    return ""


def first_entity(text: str) -> str:
    normalized = normalize_query(text)
    keywords = extract_keywords(normalized)
    for keyword in keywords:
        if is_strong_token(keyword):
            return keyword
    return keywords[0] if keywords else ""


def is_strong_token(token: str) -> bool:
    return bool(
        "@" in token
        or re.search(r"\d{4,}", token)
        or token in ENTITY_ALIASES
        or token.lower() in ENTITY_ALIASES
        or len(token) >= 2
    )


def is_mail_entity(token: str) -> bool:
    return bool(
        "@" in token
        or re.search(r"\d{4,}", token)
        or token in ENTITY_ALIASES
        or token.lower() in ENTITY_ALIASES
    )


def unique_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        key = value.lower()
        if value and key not in seen:
            seen.add(key)
            result.append(value)
    return result
