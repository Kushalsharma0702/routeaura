"""Speech adapters. IMPORTANT: Sarvam and Azure adapters follow the providers' documented REST shapes but were
only exercised against mocked HTTP responses in this repository, never against the live services. Audio formats
accepted by server-side STT differ per provider; the web client falls back to the browser's own speech APIs."""

from __future__ import annotations

import base64
from xml.sax.saxutils import escape

import httpx

from app.core.config import get_settings
from app.integrations.speech.base import Audio, SpeechError, SpeechNotConfigured, SpeechProvider, Transcript

LOCALES = {"en": "en-IN", "hi": "hi-IN"}
AZURE_VOICES = {"en": "en-IN-NeerjaNeural", "hi": "hi-IN-SwaraNeural"}


def _lang_from_locale(code: str | None, fallback: str) -> str:
    return (
        "hi" if (code or "").lower().startswith("hi") else "en" if (code or "").lower().startswith("en") else fallback
    )


class NoSpeech:
    name = "none"

    def transcribe(self, audio: bytes, mime: str, language: str | None) -> Transcript:
        raise SpeechNotConfigured("No speech provider is configured on the server")

    def synthesize(self, text: str, language: str) -> Audio:
        raise SpeechNotConfigured("No speech provider is configured on the server")


class SarvamSpeech:
    name = "sarvam"
    BASE = "https://api.sarvam.ai"

    def __init__(self, api_key: str, timeout: float = 30.0, client: httpx.Client | None = None):
        self.api_key, self.timeout, self._client = api_key, timeout, client

    def _http(self):
        return self._client or httpx

    def transcribe(self, audio: bytes, mime: str, language: str | None) -> Transcript:
        try:
            r = self._http().post(
                f"{self.BASE}/speech-to-text",
                headers={"api-subscription-key": self.api_key},
                timeout=self.timeout,
                files={"file": ("audio", audio, mime)},
                data={"language_code": LOCALES.get(language or "", "unknown"), "model": "saarika:v2"},
            )
            r.raise_for_status()
            body = r.json()
            text = (body.get("transcript") or "").strip()
            return Transcript(text, _lang_from_locale(body.get("language_code"), language or "en"), self.name)
        except (httpx.HTTPError, ValueError) as exc:
            raise SpeechError(f"sarvam speech-to-text failed: {type(exc).__name__}") from exc

    def synthesize(self, text: str, language: str) -> Audio:
        try:
            r = self._http().post(
                f"{self.BASE}/text-to-speech",
                headers={"api-subscription-key": self.api_key, "content-type": "application/json"},
                timeout=self.timeout,
                json={
                    "inputs": [text[:1000]],
                    "target_language_code": LOCALES.get(language, "en-IN"),
                    "model": "bulbul:v1",
                },
            )
            r.raise_for_status()
            return Audio(base64.b64decode(r.json()["audios"][0]), "audio/wav", self.name)
        except (httpx.HTTPError, KeyError, IndexError, ValueError) as exc:
            raise SpeechError(f"sarvam text-to-speech failed: {type(exc).__name__}") from exc


class AzureSpeech:
    name = "azure"

    def __init__(self, key: str, region: str, timeout: float = 30.0, client: httpx.Client | None = None):
        self.key, self.region, self.timeout, self._client = key, region, timeout, client

    def _http(self):
        return self._client or httpx

    def transcribe(self, audio: bytes, mime: str, language: str | None) -> Transcript:
        url = f"https://{self.region}.stt.speech.microsoft.com/speech/recognition/conversation/cognitiveservices/v1"
        try:
            r = self._http().post(
                url,
                params={"language": LOCALES.get(language or "en", "en-IN"), "format": "simple"},
                content=audio,
                timeout=self.timeout,
                headers={"Ocp-Apim-Subscription-Key": self.key, "Content-Type": mime, "Accept": "application/json"},
            )
            r.raise_for_status()
            body = r.json()
            if body.get("RecognitionStatus") != "Success":
                raise SpeechError(f"azure could not recognise speech ({body.get('RecognitionStatus')})")
            return Transcript(body.get("DisplayText", "").strip(), language or "en", self.name)
        except (httpx.HTTPError, ValueError) as exc:
            raise SpeechError(f"azure speech-to-text failed: {type(exc).__name__}") from exc

    def synthesize(self, text: str, language: str) -> Audio:
        locale, voice = LOCALES.get(language, "en-IN"), AZURE_VOICES.get(language, AZURE_VOICES["en"])
        ssml = f"<speak version='1.0' xml:lang='{locale}'><voice name='{voice}'>{escape(text[:1000])}</voice></speak>"
        try:
            r = self._http().post(
                f"https://{self.region}.tts.speech.microsoft.com/cognitiveservices/v1",
                content=ssml.encode(),
                timeout=self.timeout,
                headers={
                    "Ocp-Apim-Subscription-Key": self.key,
                    "Content-Type": "application/ssml+xml",
                    "X-Microsoft-OutputFormat": "audio-24khz-48kbitrate-mono-mp3",
                    "User-Agent": "routeaura",
                },
            )
            r.raise_for_status()
            return Audio(r.content, "audio/mpeg", self.name)
        except httpx.HTTPError as exc:
            raise SpeechError(f"azure text-to-speech failed: {type(exc).__name__}") from exc


def get_speech() -> SpeechProvider:
    s = get_settings()
    if s.speech_provider == "sarvam" and s.sarvam_api_key:
        return SarvamSpeech(s.sarvam_api_key)
    if s.speech_provider == "azure" and s.azure_speech_key and s.azure_speech_region:
        return AzureSpeech(s.azure_speech_key, s.azure_speech_region)
    return NoSpeech()
