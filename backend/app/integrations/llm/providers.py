from __future__ import annotations

import httpx

from app.core.config import get_settings
from app.integrations.llm.base import LLMClient, LLMError, ProviderNotConfigured


class NoLLM:
    name, model = "none", "none"

    def complete(self, system: str, user: str, *, max_tokens: int = 2000) -> str:
        raise ProviderNotConfigured("No LLM provider is configured (set LLM_PROVIDER and LLM_API_KEY)")


class AnthropicLLM:
    """Anthropic Messages API over HTTPS. Not exercised against the live API in the test suite
    (tests use a fake client); verified only for request shape and error handling."""

    name = "anthropic"
    URL = "https://api.anthropic.com/v1/messages"

    def __init__(self, api_key: str, model: str, timeout: float):
        self.api_key, self.model, self.timeout = api_key, model, timeout

    def complete(self, system: str, user: str, *, max_tokens: int = 2000) -> str:
        try:
            r = httpx.post(
                self.URL,
                timeout=self.timeout,
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": self.model,
                    "max_tokens": max_tokens,
                    "system": system,
                    "messages": [{"role": "user", "content": user}],
                },
            )
            r.raise_for_status()
            blocks = r.json()["content"]
            return "".join(b.get("text", "") for b in blocks if b.get("type") == "text")
        except (httpx.HTTPError, KeyError, ValueError) as exc:
            raise LLMError(f"anthropic request failed: {type(exc).__name__}") from exc


def get_llm() -> LLMClient:
    s = get_settings()
    if s.llm_provider == "anthropic":
        if not s.llm_api_key:
            return NoLLM()
        return AnthropicLLM(s.llm_api_key, s.llm_model, s.llm_timeout_s)
    return NoLLM()
