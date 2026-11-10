import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

Lang = Literal["en", "hi"]


class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=1000)
    conversation_id: uuid.UUID | None = None
    language: Lang | None = None  # explicit choice; keeps (or switches) the conversation language
    input_mode: Literal["text", "voice"] = "text"


class ActionOut(BaseModel):
    type: str
    status: Literal["ok", "failed", "needs_info", "awaiting_confirmation"]
    detail: dict = Field(default_factory=dict)


class ChatOut(BaseModel):
    conversation_id: uuid.UUID
    language: Lang
    detected_language: Lang
    language_mismatch: bool
    reply: str
    actions: list[ActionOut]
    cards: list[dict]
    awaiting_confirmation: bool
    interpreted_by: str


class MessageOut(BaseModel):
    id: uuid.UUID
    role: str
    content: str
    language: str
    input_mode: str
    actions: list
    cards: list
    created_at: datetime


class ConversationSummary(BaseModel):
    id: uuid.UUID
    title: str
    language: Lang
    updated_at: datetime
    message_count: int


class ConversationDetail(ConversationSummary):
    messages: list[MessageOut]


class ConversationPatch(BaseModel):
    language: Lang | None = None
    title: str | None = Field(default=None, min_length=1, max_length=120)


class SynthesizeIn(BaseModel):
    text: str = Field(min_length=1, max_length=1000)
    language: Lang = "en"


class TranscriptOut(BaseModel):
    text: str
    language: Lang
    provider: str


class CapabilitiesOut(BaseModel):
    text_chat: bool
    languages: list[str]
    speech_provider: str  # "none" when no server-side speech is configured
    server_speech_to_text: bool
    server_text_to_speech: bool
    browser_fallback: bool  # the client may use the browser's own speech APIs
    max_audio_bytes: int
