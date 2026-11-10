"""Speech provider interface. Credentials never leave the server: clients only learn *whether* speech is available."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class SpeechError(Exception):
    pass


class SpeechNotConfigured(SpeechError):
    pass


@dataclass
class Transcript:
    text: str
    language: str  # "en" | "hi"
    provider: str


@dataclass
class Audio:
    data: bytes
    mime: str
    provider: str


class SpeechProvider(Protocol):
    name: str

    def transcribe(self, audio: bytes, mime: str, language: str | None) -> Transcript: ...
    def synthesize(self, text: str, language: str) -> Audio: ...
