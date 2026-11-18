"""Configurable LLM provider abstraction.

The LLM is used only for (1) turning a question into a structured tool call and (2) phrasing an
answer from tool results. It never computes prices or statistics. With no provider configured,
the deterministic engine handles supported queries on its own."""
import json
from typing import Any, Protocol

import httpx

from app.core.config import get_settings


class LLMProvider(Protocol):
    name: str

    def complete_json(self, system: str, user: str) -> dict[str, Any]: ...

    def complete_text(self, system: str, user: str) -> str: ...


class _Base:
    def __init__(self, api_key: str, model: str, base_url: str, timeout: int):
        self.api_key, self.model, self.base_url, self.timeout = api_key, model, base_url.rstrip("/"), timeout

    def complete_json(self, system: str, user: str) -> dict[str, Any]:
        text = self.complete_text(system + "\nRespond with a single JSON object only.", user)
        start, end = text.find("{"), text.rfind("}")
        if start < 0 or end < 0:
            raise ValueError("LLM did not return JSON")
        return json.loads(text[start:end + 1])


class OpenAICompatibleProvider(_Base):
    name = "openai_compatible"

    def complete_text(self, system: str, user: str) -> str:
        r = httpx.post(f"{self.base_url}/chat/completions", timeout=self.timeout,
                       headers={"Authorization": f"Bearer {self.api_key}"},
                       json={"model": self.model, "temperature": 0,
                             "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]})
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]


class AnthropicProvider(_Base):
    name = "anthropic"

    def complete_text(self, system: str, user: str) -> str:
        r = httpx.post(f"{self.base_url or 'https://api.anthropic.com'}/v1/messages", timeout=self.timeout,
                       headers={"x-api-key": self.api_key, "anthropic-version": "2023-06-01"},
                       json={"model": self.model, "max_tokens": 1024, "system": system, "temperature": 0,
                             "messages": [{"role": "user", "content": user}]})
        r.raise_for_status()
        return "".join(b.get("text", "") for b in r.json().get("content", []))


def get_provider() -> LLMProvider | None:
    s = get_settings()
    if not s.llm_provider or not s.llm_api_key or not s.llm_model:
        return None
    if s.llm_provider == "openai_compatible":
        return OpenAICompatibleProvider(s.llm_api_key, s.llm_model, s.llm_base_url or "https://api.openai.com/v1", s.llm_timeout_seconds)
    if s.llm_provider == "anthropic":
        return AnthropicProvider(s.llm_api_key, s.llm_model, s.llm_base_url, s.llm_timeout_seconds)
    return None
