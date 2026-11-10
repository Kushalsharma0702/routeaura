"""Provider-independent LLM interface. The itinerary generator depends only on `LLMClient`."""

from __future__ import annotations

import json
import re
from typing import Protocol


class LLMError(Exception):
    """Transport/provider failure (network, auth, rate limit, malformed envelope)."""


class ProviderNotConfigured(LLMError):
    """No LLM provider/credentials configured: callers must use their deterministic fallback."""


class LLMClient(Protocol):
    name: str
    model: str

    def complete(self, system: str, user: str, *, max_tokens: int = 2000) -> str: ...


def extract_json(text: str) -> object:
    """Parse the JSON payload of a model reply, tolerating markdown fences and surrounding prose."""
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    body = fenced.group(1) if fenced else text
    start = min((i for i in (body.find("{"), body.find("[")) if i != -1), default=-1)
    if start == -1:
        raise ValueError("no JSON object in model output")
    decoder = json.JSONDecoder()
    obj, _ = decoder.raw_decode(body[start:])
    return obj
