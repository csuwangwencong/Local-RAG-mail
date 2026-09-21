from __future__ import annotations

import asyncio
import json
import os
import socket
import urllib.error
import urllib.request

from app.api.ai_models import AiMessage, AiModelInfo, AiSource, DEFAULT_AI_MODEL
from app.core.errors import AppError


DEFAULT_BASE_URL = "http://127.0.0.1:11434/v1"
DEFAULT_TIMEOUT_SECONDS = 300
MAX_CONTEXT_MESSAGES = 20
MAX_PROMPT_CHARS = 32000

SYSTEM_PROMPT = """你是 localmail 的本地邮件助手。
如果没有提供邮件知识库片段，你可以进行普通多轮对话，但不能声称已经检索、读取或引用用户邮件。
如果提供了邮件知识库片段，你必须只根据片段回答邮件相关问题；证据不足时明确说明没有找到足够邮件证据。"""

RAG_SYSTEM_PROMPT = """你是 localmail 的本地邮件助手。
请只根据下面提供的邮件来源片段回答用户问题，不要编造邮件内容。
如果邮件来源不足以回答，请直接说明没有找到足够邮件证据。
回答中需要自然提及相关邮件，并在句末使用 [来源1]、[来源2] 这样的标记。"""


class OpenAICompatibleLlmClient:
    def __init__(self) -> None:
        self.base_url = os.getenv("LOCAL_LLM_BASE_URL", DEFAULT_BASE_URL).rstrip("/")
        self.model = os.getenv("LOCAL_LLM_MODEL", DEFAULT_AI_MODEL)
        self.timeout = int(os.getenv("LOCAL_LLM_TIMEOUT_SECONDS", str(DEFAULT_TIMEOUT_SECONDS)))

    async def list_models(self) -> list[AiModelInfo]:
        return await asyncio.to_thread(self._list_models_sync)

    async def model_available(self, model: str) -> bool:
        models = await self.list_models()
        return any(item.id == model for item in models)

    async def chat(self, model: str, messages: list[AiMessage], sources: list[AiSource] | None = None) -> str:
        return await asyncio.to_thread(self._chat_sync, model, messages, sources or [])

    def _list_models_sync(self) -> list[AiModelInfo]:
        ollama_base_url = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
        configured = configured_models()
        request = urllib.request.Request(f"{ollama_base_url}/api/tags", method="GET")
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                data = json.loads(response.read().decode("utf-8"))
        except (TimeoutError, socket.timeout, urllib.error.URLError, json.JSONDecodeError):
            return [AiModelInfo(id=model, name=model, provider="ollama") for model in configured]

        names = []
        for item in data.get("models", []):
            name = item.get("name")
            if isinstance(name, str) and name:
                names.append(name)
        if not names:
            names = configured
        preferred = [model for model in configured if model in names]
        rest = sorted(model for model in names if model not in preferred)
        return [AiModelInfo(id=model, name=model, provider="ollama") for model in [*preferred, *rest]]

    def _chat_sync(self, model: str, messages: list[AiMessage], sources: list[AiSource]) -> str:
        payload = {
            "model": model,
            "stream": False,
            "messages": self._build_messages(messages, sources),
            "temperature": 0.3,
        }
        request = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                data = json.loads(response.read().decode("utf-8"))
        except (TimeoutError, socket.timeout) as exc:
            raise AppError(504, "AI_RUNTIME_TIMEOUT", "本地模型响应超时。") from exc
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                raise AppError(502, "AI_MODEL_NOT_AVAILABLE", "本地 Ollama 模型不可用，请先下载模型。") from exc
            raise AppError(502, "AI_RUNTIME_ERROR", "本地模型服务返回异常。") from exc
        except urllib.error.URLError as exc:
            raise AppError(502, "AI_RUNTIME_ERROR", "无法连接本地 Ollama 服务。") from exc
        except (json.JSONDecodeError, KeyError, IndexError, TypeError) as exc:
            raise AppError(502, "AI_RUNTIME_ERROR", "本地模型响应格式异常。") from exc

        content = data["choices"][0]["message"]["content"]
        if not isinstance(content, str):
            raise AppError(502, "AI_RUNTIME_ERROR", "本地模型响应格式异常。")
        return content.strip()

    def _build_messages(self, messages: list[AiMessage], sources: list[AiSource]) -> list[dict[str, str]]:
        selected = messages[-MAX_CONTEXT_MESSAGES:]
        system_prompt = build_rag_prompt(sources) if sources else SYSTEM_PROMPT
        api_messages = [{"role": "system", "content": system_prompt}]
        total_chars = len(system_prompt)
        for message in selected:
            if message.role == "system":
                continue
            total_chars += len(message.content)
            if total_chars > MAX_PROMPT_CHARS:
                break
            api_messages.append({"role": message.role, "content": message.content})
        return api_messages


def build_rag_prompt(sources: list[AiSource]) -> str:
    source_blocks = []
    for index, source in enumerate(sources, start=1):
        sender = source.sender_address
        if source.sender_name:
            sender = f"{source.sender_name} <{source.sender_address}>"
        source_blocks.append(
            "\n".join(
                [
                    f"[来源{index}]",
                    f"邮件UID: {source.uid or ''}",
                    f"主题: {source.title}",
                    f"发件人: {sender}",
                    f"时间: {source.received_at or ''}",
                    f"片段: {source.snippet or ''}",
                ]
            )
        )
    return f"{RAG_SYSTEM_PROMPT}\n\n邮件来源片段：\n\n" + "\n\n".join(source_blocks)


def configured_models() -> list[str]:
    raw = os.getenv("LOCAL_LLM_MODELS", f"{DEFAULT_AI_MODEL},deepseek-r1:7b")
    models = [model.strip() for model in raw.split(",") if model.strip()]
    return models or [DEFAULT_AI_MODEL]


llm_client = OpenAICompatibleLlmClient()
