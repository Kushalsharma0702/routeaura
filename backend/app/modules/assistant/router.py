import uuid
from typing import Annotated

from fastapi import APIRouter, File, Form, Query, Response, UploadFile

from app.api.deps import CurrentUser, DbSession
from app.core.config import get_settings
from app.core.errors import AppError
from app.integrations.speech.base import SpeechError, SpeechNotConfigured
from app.integrations.speech.providers import get_speech
from app.modules.assistant.service import AssistantService
from app.schemas.assistant import (
    CapabilitiesOut,
    ChatIn,
    ChatOut,
    ConversationDetail,
    ConversationPatch,
    ConversationSummary,
    SynthesizeIn,
    TranscriptOut,
)
from app.schemas.user import Page

router = APIRouter(prefix="/assistant", tags=["assistant"])


@router.get("/capabilities", response_model=CapabilitiesOut)
def capabilities(_: CurrentUser) -> CapabilitiesOut:
    """What the server can do. Never includes credentials."""
    s = get_speech()
    on = s.name != "none"
    return CapabilitiesOut(
        text_chat=True,
        languages=["en", "hi"],
        speech_provider=s.name,
        server_speech_to_text=on,
        server_text_to_speech=on,
        browser_fallback=True,
        max_audio_bytes=get_settings().speech_max_audio_bytes,
    )


@router.post("/chat", response_model=ChatOut)
def chat(data: ChatIn, user: CurrentUser, db: DbSession):
    """Text chat. Independent of speech: it works with no speech provider and when voice endpoints fail."""
    return AssistantService(db).chat(user, data.message.strip(), data.conversation_id, data.language, data.input_mode)


@router.get("/conversations", response_model=Page[ConversationSummary])
def conversations(
    user: CurrentUser,
    db: DbSession,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=50)] = 20,
):
    items, total = AssistantService(db).list(user, page, page_size)
    return Page(items=items, total=total, page=page, page_size=page_size)


@router.get("/conversations/{conversation_id}", response_model=ConversationDetail)
def conversation(conversation_id: uuid.UUID, user: CurrentUser, db: DbSession):
    return AssistantService(db).detail(user, conversation_id)


@router.patch("/conversations/{conversation_id}", response_model=ConversationSummary)
def patch_conversation(conversation_id: uuid.UUID, data: ConversationPatch, user: CurrentUser, db: DbSession):
    return AssistantService(db).patch(user, conversation_id, data.language, data.title)


@router.delete("/conversations/{conversation_id}", status_code=204)
def delete_conversation(conversation_id: uuid.UUID, user: CurrentUser, db: DbSession):
    AssistantService(db).delete(user, conversation_id)


@router.post("/voice/transcribe", response_model=TranscriptOut)
async def transcribe(
    _: CurrentUser, audio: Annotated[UploadFile, File()], language: Annotated[str | None, Form()] = None
):
    limit = get_settings().speech_max_audio_bytes
    data = await audio.read(limit + 1)
    if len(data) > limit:
        raise AppError(413, "audio_too_large", f"Audio must be at most {limit} bytes")
    if not (audio.content_type or "").startswith("audio/"):
        raise AppError(422, "unsupported_media", "Upload an audio file")
    if language not in (None, "en", "hi"):
        raise AppError(422, "validation_error", "language must be en or hi")
    try:
        t = get_speech().transcribe(data, audio.content_type or "audio/wav", language)
    except SpeechNotConfigured as exc:
        raise AppError(
            503, "speech_not_configured", f"{exc}. Use the browser's speech recognition or type your message."
        ) from exc
    except SpeechError as exc:
        raise AppError(
            502, "speech_error", f"Speech recognition failed: {exc}. You can type your message instead."
        ) from exc
    return TranscriptOut(text=t.text, language=t.language if t.language in ("en", "hi") else "en", provider=t.provider)


@router.post("/voice/synthesize")
def synthesize(data: SynthesizeIn, _: CurrentUser) -> Response:
    try:
        a = get_speech().synthesize(data.text, data.language)
    except SpeechNotConfigured as exc:
        raise AppError(
            503, "speech_not_configured", f"{exc}. The browser's text-to-speech can be used instead."
        ) from exc
    except SpeechError as exc:
        raise AppError(502, "speech_error", f"Speech synthesis failed: {exc}") from exc
    return Response(content=a.data, media_type=a.mime, headers={"Cache-Control": "no-store"})
