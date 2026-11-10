import uuid
from datetime import timedelta

import httpx
import pytest
from sqlalchemy import func, select

from app.core.timeutil import today_local
from app.integrations.llm.base import LLMError
from app.integrations.speech.base import Audio, SpeechError, Transcript
from app.integrations.speech.providers import AzureSpeech, SarvamSpeech
from app.models.booking import AssistantConversation, AssistantMessage, Hotel, RoomType
from app.models.itinerary import Itinerary
from app.models.recommendations import RecommendationRun

from .conftest import auth

API = "/api/v1"


def register(client, email):
    return client.post(
        f"{API}/auth/register", json={"email": email, "password": "Passw0rdOK", "full_name": "V"}
    ).json()["access_token"]


@pytest.fixture
def tok(client, seeded):
    return register(client, "va@example.com")


@pytest.fixture
def tok2(client, seeded):
    return register(client, "va2@example.com")


def say(client, tok, text, cid=None, language=None, **extra):
    body = {
        "message": text,
        **({"conversation_id": cid} if cid else {}),
        **({"language": language} if language else {}),
        **extra,
    }
    r = client.post(f"{API}/assistant/chat", json=body, headers=auth(tok))
    assert r.status_code == 200, r.text
    return r.json()


# ------------------------------------------------------------------ text chat works with no speech provider
def test_text_chat_works_without_any_speech_provider_and_is_persisted(client, tok, db):
    caps = client.get(f"{API}/assistant/capabilities", headers=auth(tok)).json()
    assert caps == {
        "text_chat": True,
        "languages": ["en", "hi"],
        "speech_provider": "none",
        "server_speech_to_text": False,
        "server_text_to_speech": False,
        "browser_fallback": True,
        "max_audio_bytes": 5_000_000,
    }
    r = say(client, tok, "hello")
    assert r["language"] == "en" and "Hello" in r["reply"] and r["actions"] == [] and r["interpreted_by"] == "rules"
    conv = client.get(f"{API}/assistant/conversations/{r['conversation_id']}", headers=auth(tok)).json()
    assert (
        [m["role"] for m in conv["messages"]] == ["user", "assistant"]
        and conv["messages"][0]["content"] == "hello"
        and conv["title"] == "hello"
    )
    assert db.scalar(select(func.count()).select_from(AssistantMessage)) == 2
    again = say(client, tok, "help", r["conversation_id"])
    assert again["conversation_id"] == r["conversation_id"]
    assert (
        client.get(f"{API}/assistant/conversations/{r['conversation_id']}", headers=auth(tok)).json()["message_count"]
        == 4
    )


def test_hindi_conversation_replies_in_hindi(client, tok):
    r = say(client, tok, "नमस्ते")
    assert r["language"] == "hi" and "नमस्ते" in r["reply"] and r["detected_language"] == "hi"


def test_selected_language_is_preserved_even_when_the_user_types_another_language(client, tok):
    first = say(client, tok, "hello", language="hi")  # the user selected Hindi in the UI
    assert first["language"] == "hi" and "नमस्ते" in first["reply"]
    second = say(client, tok, "show my bookings", first["conversation_id"])  # typed in English
    assert second["language"] == "hi" and second["detected_language"] == "en" and second["language_mismatch"] is True
    assert "बुकिंग" in second["reply"]  # reply stays in the conversation language
    switched = say(client, tok, "show my bookings", first["conversation_id"], language="en")
    assert switched["language"] == "en" and "bookings" in switched["reply"].lower()
    assert say(client, tok, "ok thanks help", first["conversation_id"])["language"] == "en"  # and the choice persists


def test_chat_validation_and_authentication(client, tok):
    for body in (
        {"message": ""},
        {"message": "x" * 1001},
        {"message": "hi", "language": "fr"},
        {"message": "hi", "input_mode": "telepathy"},
    ):
        assert client.post(f"{API}/assistant/chat", json=body, headers=auth(tok)).status_code == 422
    assert client.post(f"{API}/assistant/chat", json={"message": "hi"}).status_code == 401
    assert client.get(f"{API}/assistant/capabilities").status_code == 401
    assert (
        client.post(
            f"{API}/assistant/chat", json={"message": "hi", "conversation_id": str(uuid.uuid4())}, headers=auth(tok)
        ).status_code
        == 404
    )


# ------------------------------------------------------------------ recommendations through the existing service
def test_recommendation_queries_use_the_recommendation_service(client, tok, db):
    before = db.scalar(select(func.count()).select_from(RecommendationRun))
    r = say(client, tok, "recommend a place for history and food")
    assert r["actions"][0]["type"] == "recommend" and r["actions"][0]["status"] == "ok"
    assert r["cards"] and r["cards"][0]["type"] == "destination" and r["cards"][0]["name"] == "Jaipur"
    assert r["reply"].startswith("Here are places") and "1. Jaipur" in r["reply"]
    assert db.scalar(select(func.count()).select_from(RecommendationRun)) == before + 1  # a real, persisted run
    hi = say(client, tok, "इतिहास और खाने के लिए जगह सुझाओ", language="hi")
    assert hi["language"] == "hi" and "जगहें" in hi["reply"] and "Jaipur" in hi["reply"]


# ------------------------------------------------------------------ itinerary generation through the itinerary service
def test_planning_asks_for_missing_details_then_creates_a_real_itinerary(client, tok, tok2, db):
    a = say(client, tok, "plan a trip to Jaipur")
    assert (
        a["actions"][0] == {"type": "plan", "status": "needs_info", "detail": {"missing": "days"}}
        and "How many days" in a["reply"]
    )
    assert db.scalar(select(func.count()).select_from(Itinerary)) == 0  # nothing created yet
    b = say(client, tok, "3", a["conversation_id"])
    assert b["actions"][0]["status"] == "ok" and b["actions"][0]["type"] == "plan"
    it = db.scalar(select(Itinerary))
    assert (
        it is not None
        and it.days == 3
        and len(it.activities) >= 3
        and it.versions
        and str(it.id) == b["actions"][0]["detail"]["itinerary_id"]
    )
    assert b["cards"][0] == {"type": "itinerary", "id": str(it.id), "title": it.title} and "Day 1:" in b["reply"]
    assert "app's own planner" in b["reply"]  # fallback is disclosed in chat
    mine = client.get(f"{API}/itineraries/{it.id}", headers=auth(tok))
    assert mine.status_code == 200 and client.get(f"{API}/itineraries/{it.id}", headers=auth(tok2)).status_code == 404


def test_one_shot_planning_in_english_and_hindi_extracts_every_slot(client, tok, db):
    r = say(client, tok, "Plan 2 days in Jaipur for two, budget 30k, history and food")
    it = db.scalar(select(Itinerary))
    assert (it.days, it.traveler_count, it.budget_total_minor, sorted(it.interests)) == (
        2,
        2,
        3_000_000,
        ["food", "history"],
    ) and r["actions"][0]["status"] == "ok"
    h = say(client, tok, "जयपुर के लिए ३ दिन का प्लान बनाओ", language="hi")
    assert h["language"] == "hi"
    assert h["reply"].startswith("मैंने Jaipur की 3 दिन की यात्रा बनाई है")
    assert db.scalar(select(func.count()).select_from(Itinerary)) == 2


def test_missing_destination_is_asked_for_with_the_published_names_in_the_conversation_language(client, tok):
    r = say(client, tok, "plan 3 days", language="hi")
    assert r["actions"][0]["detail"] == {"missing": "destination"} and "उपलब्ध" in r["reply"] and "Jaipur" in r["reply"]
    done = say(client, tok, "जयपुर", r["conversation_id"])
    assert done["actions"][0]["status"] == "ok" and "3 दिन" in done["reply"]


def test_context_carries_over_for_show_add_remove_and_move(client, tok, db):
    h = auth(tok)
    c = say(client, tok, "plan 2 days in Jaipur")
    cid = c["conversation_id"]
    it = db.scalar(select(Itinerary))
    shown = say(client, tok, "show my itinerary", cid)
    assert (
        shown["actions"][0] == {"type": "show", "status": "ok", "detail": {"itinerary_id": str(it.id)}}
        and "Day 1:" in shown["reply"]
    )
    first_name = client.get(f"{API}/itineraries/{it.id}", headers=h).json()["day_plans"][0]["activities"][0][
        "attraction"
    ]["name"]

    ask = say(client, tok, f"remove {first_name}", cid)
    assert (
        ask["awaiting_confirmation"] is True
        and ask["actions"][0]["status"] == "awaiting_confirmation"
        and "Say yes" in ask["reply"]
    )
    n_before = len(client.get(f"{API}/itineraries/{it.id}", headers=h).json()["day_plans"][0]["activities"])
    assert (
        len(db.scalar(select(Itinerary)).activities) >= 1
        and client.get(f"{API}/itineraries/{it.id}", headers=h).json()["current_version"] == 1
    )  # untouched until confirmed
    declined = say(client, tok, "no", cid)
    assert (
        declined["reply"].startswith("Okay")
        and client.get(f"{API}/itineraries/{it.id}", headers=h).json()["current_version"] == 1
    )
    say(client, tok, f"remove {first_name}", cid)
    ok = say(client, tok, "yes", cid)
    assert ok["actions"][0]["status"] == "ok" and ok["reply"] == f"Done. I removed {first_name}."
    after = client.get(f"{API}/itineraries/{it.id}", headers=h).json()
    assert after["current_version"] == 2 and first_name not in [
        a["attraction"]["name"] for d in after["day_plans"] for a in d["activities"]
    ]
    assert n_before >= 1
    added = say(client, tok, f"add {first_name} to day 2", cid)
    assert added["actions"][0]["status"] == "ok" and added["reply"] == f"Added {first_name} to day 2."
    assert first_name in [
        a["attraction"]["name"]
        for a in client.get(f"{API}/itineraries/{it.id}", headers=h).json()["day_plans"][1]["activities"]
    ]
    moved_ask = say(client, tok, f"move {first_name} to day 1", cid)
    assert moved_ask["awaiting_confirmation"] and say(client, tok, "yes", cid)["actions"][0]["type"] == "move"
    assert first_name in [
        a["attraction"]["name"]
        for a in client.get(f"{API}/itineraries/{it.id}", headers=h).json()["day_plans"][0]["activities"]
    ]


def test_a_pending_confirmation_is_abandoned_by_any_other_message_and_yes_alone_does_nothing(client, tok, db):
    h = auth(tok)
    c = say(client, tok, "plan 2 days in Jaipur")
    it = db.scalar(select(Itinerary))
    name = client.get(f"{API}/itineraries/{it.id}", headers=h).json()["day_plans"][0]["activities"][0]["attraction"][
        "name"
    ]
    say(client, tok, f"remove {name}", c["conversation_id"])
    say(client, tok, "hello", c["conversation_id"])  # a different message: the removal is dropped
    r = say(client, tok, "yes", c["conversation_id"])
    assert (
        "nothing waiting" in r["reply"]
        and client.get(f"{API}/itineraries/{it.id}", headers=h).json()["current_version"] == 1
    )
    assert "nothing waiting" in say(client, tok, "yes")["reply"]  # fresh conversation, nothing pending


def test_edits_are_validated_by_the_itinerary_service_and_failures_are_explained(client, tok, db):
    c = say(client, tok, "plan 1 days in Jaipur")
    cid = c["conversation_id"]
    assert say(client, tok, "remove the Eiffel Tower", cid)["actions"][0]["detail"] == {"reason": "activity_not_found"}
    assert "Your itinerary has" in say(client, tok, "remove the Eiffel Tower", cid)["reply"]
    bad_day = say(client, tok, "add Hawa Mahal to day 9", cid)
    assert "Which day" in bad_day["reply"]
    unknown = say(client, tok, "add Taj Mahal to day 1", cid)
    assert unknown["actions"][0]["detail"] == {"reason": "attraction_not_found"}
    in_trip = {a.attraction.name for a in db.scalar(select(Itinerary)).activities}
    dup = next(iter(in_trip))
    r = say(client, tok, f"add {dup} to day 1", cid)
    assert (
        r["actions"][0]["status"] == "failed" and "already in the itinerary" in r["reply"]
    )  # the service's own 409, surfaced


def test_itinerary_commands_without_an_itinerary_are_handled(client, tok):
    for text in ("show my itinerary", "remove Hawa Mahal", "add Amber Fort"):
        r = say(client, tok, text)
        assert "don't have an itinerary" in r["reply"] and r["actions"][0]["status"] == "failed"


# ------------------------------------------------------------------ bookings and hotels
def test_booking_and_hotel_queries(client, tok, db):
    assert "don't have any bookings" in say(client, tok, "show my bookings")["reply"]
    h = db.scalar(select(Hotel).where(Hotel.name == "Rose Courtyard Haveli"))
    room = db.scalar(select(RoomType).where(RoomType.hotel_id == h.id, RoomType.name == "Heritage Room"))
    ci = today_local() + timedelta(days=20)
    b = client.post(
        f"{API}/bookings",
        json={
            "room_type_id": str(room.id),
            "check_in": ci.isoformat(),
            "check_out": (ci + timedelta(days=2)).isoformat(),
            "guests": 2,
            "guest_name": "Asha",
        },
        headers={**auth(tok), "Idempotency-Key": "k"},
    ).json()
    r = say(client, tok, "show my bookings")
    assert (
        b["reference"] in r["reply"]
        and "Rose Courtyard Haveli" in r["reply"]
        and "pending payment" in r["reply"]
        and r["cards"][0]["type"] == "booking"
    )
    hi = say(client, tok, "मेरी बुकिंग दिखाओ", language="hi")
    assert "भुगतान लंबित" in hi["reply"] and b["reference"] in hi["reply"]
    hotels = say(client, tok, "hotels in Goa")
    assert (
        hotels["reply"].startswith("Hotels in Goa:")
        and "Palm Shore Resort" in hotels["reply"]
        and "₹" in hotels["reply"]
        and hotels["cards"][0]["type"] == "hotel"
    )
    assert "Which destination" in say(client, tok, "show hotels")["reply"]
    assert "होटल" in say(client, tok, "जयपुर में होटल", language="hi")["reply"]


def test_assistant_cannot_cancel_or_pay_bookings(client, tok, db):
    h = db.scalar(select(Hotel).where(Hotel.name == "Rose Courtyard Haveli"))
    room = db.scalar(select(RoomType).where(RoomType.hotel_id == h.id, RoomType.name == "Heritage Room"))
    ci = today_local() + timedelta(days=20)
    b = client.post(
        f"{API}/bookings",
        json={
            "room_type_id": str(room.id),
            "check_in": ci.isoformat(),
            "check_out": (ci + timedelta(days=1)).isoformat(),
            "guests": 1,
            "guest_name": "Asha",
        },
        headers={**auth(tok), "Idempotency-Key": "k"},
    ).json()
    for text in ("cancel my booking", "pay for my booking", "refund my booking"):
        say(client, tok, text)
    assert (
        client.get(f"{API}/bookings/{b['id']}", headers=auth(tok)).json()["status"] == "pending_payment"
    )  # financial actions stay in the booking UI


def test_unrecognised_messages_cause_no_side_effects(client, tok, db):
    r = say(client, tok, "asdf qwerty")
    assert "haven't changed anything" in r["reply"] and r["actions"] == []
    assert (
        db.scalar(select(func.count()).select_from(Itinerary)) == 0
        and db.scalar(select(func.count()).select_from(RecommendationRun)) == 0
    )


# ------------------------------------------------------------------ conversation management & privacy
def test_conversations_are_private_listed_patched_and_deleted(client, tok, tok2):
    a = say(client, tok, "hello")
    say(client, tok, "help")
    b = say(client, tok2, "hello")
    h, h2 = auth(tok), auth(tok2)
    mine = client.get(f"{API}/assistant/conversations", headers=h).json()
    assert mine["total"] == 2 and {c["id"] for c in mine["items"]} != {b["conversation_id"]}
    assert (
        client.get(f"{API}/assistant/conversations", params={"page_size": 1}, headers=h).json()["items"].__len__() == 1
    )
    cid = a["conversation_id"]
    assert client.get(f"{API}/assistant/conversations/{cid}", headers=h2).status_code == 404
    assert (
        client.post(f"{API}/assistant/chat", json={"message": "hi", "conversation_id": cid}, headers=h2).status_code
        == 404
    )
    assert (
        client.patch(
            f"{API}/assistant/conversations/{cid}", json={"language": "hi", "title": "Renamed"}, headers=h2
        ).status_code
        == 404
    )
    patched = client.patch(
        f"{API}/assistant/conversations/{cid}", json={"language": "hi", "title": "Renamed"}, headers=h
    ).json()
    assert patched["language"] == "hi" and patched["title"] == "Renamed"
    assert client.patch(f"{API}/assistant/conversations/{cid}", json={"language": "fr"}, headers=h).status_code == 422
    assert "नमस्ते" in say(client, tok, "hello", cid)["reply"]
    assert client.delete(f"{API}/assistant/conversations/{cid}", headers=h2).status_code == 404
    assert client.delete(f"{API}/assistant/conversations/{cid}", headers=h).status_code == 204
    assert client.get(f"{API}/assistant/conversations/{cid}", headers=h).status_code == 404


# ------------------------------------------------------------------ optional LLM understanding never breaks the rules
class ScriptedLLM:
    name, model = "fake", "fake"

    def __init__(self, reply):
        self.reply = reply

    def complete(self, system, user, *, max_tokens=2000):
        if isinstance(self.reply, Exception):
            raise self.reply
        return self.reply


@pytest.mark.parametrize(
    "reply,by",
    [
        ('{"intent": "help", "destination": null, "days": null, "travelers": null}', "llm"),
        ("not json", "rules"),
        ('{"intent": "format_disk"}', "rules"),
        (LLMError("down"), "rules"),
    ],
)
def test_llm_understanding_is_validated_with_a_rule_based_fallback(client, tok, monkeypatch, reply, by):
    monkeypatch.setattr("app.modules.assistant.service.get_llm", lambda: ScriptedLLM(reply))
    r = say(client, tok, "hello")
    assert r["interpreted_by"] == by and r["reply"]
    if by == "rules":
        assert "Hello!" in r["reply"]


# ------------------------------------------------------------------ voice endpoints
class FakeSpeech:
    name = "fake-speech"

    def __init__(self, fail=False):
        self.fail = fail

    def transcribe(self, audio, mime, language):
        if self.fail:
            raise SpeechError("provider down")
        return Transcript("plan 2 days in Jaipur", "en", self.name)

    def synthesize(self, text, language):
        if self.fail:
            raise SpeechError("provider down")
        return Audio(b"FAKEAUDIO", "audio/mpeg", self.name)


def upload(client, tok, content=b"abc", ctype="audio/wav", **form):
    return client.post(
        f"{API}/assistant/voice/transcribe", files={"audio": ("a.wav", content, ctype)}, data=form, headers=auth(tok)
    )


def test_voice_endpoints_report_missing_speech_clearly_and_text_chat_keeps_working(client, tok):
    r = upload(client, tok)
    assert (
        r.status_code == 503
        and r.json()["error"]["code"] == "speech_not_configured"
        and "type your message" in r.json()["error"]["message"]
    )
    s = client.post(f"{API}/assistant/voice/synthesize", json={"text": "hello", "language": "en"}, headers=auth(tok))
    assert s.status_code == 503 and s.json()["error"]["code"] == "speech_not_configured"
    assert say(client, tok, "hello")["reply"]  # text chat is unaffected


def test_voice_provider_failures_do_not_break_text_chat(client, tok, monkeypatch):
    monkeypatch.setattr("app.modules.assistant.router.get_speech", lambda: FakeSpeech(fail=True))
    assert upload(client, tok).status_code == 502 and upload(client, tok).json()["error"]["code"] == "speech_error"
    assert (
        client.post(f"{API}/assistant/voice/synthesize", json={"text": "hi"}, headers=auth(tok)).json()["error"]["code"]
        == "speech_error"
    )
    r = say(client, tok, "hello", input_mode="voice")
    assert (
        r["reply"]
        and client.get(f"{API}/assistant/conversations/{r['conversation_id']}", headers=auth(tok)).json()["messages"][
            0
        ]["input_mode"]
        == "voice"
    )


def test_voice_round_trip_with_a_configured_provider(client, tok, monkeypatch):
    monkeypatch.setattr("app.modules.assistant.router.get_speech", lambda: FakeSpeech())
    t = upload(client, tok, language="en").json()
    assert t == {"text": "plan 2 days in Jaipur", "language": "en", "provider": "fake-speech"}
    chat = say(client, tok, t["text"], input_mode="voice")  # the transcript goes through normal chat
    assert chat["actions"][0]["type"] == "plan" and chat["actions"][0]["status"] == "ok"
    audio = client.post(
        f"{API}/assistant/voice/synthesize", json={"text": chat["reply"][:100], "language": "en"}, headers=auth(tok)
    )
    assert (
        audio.status_code == 200
        and audio.content == b"FAKEAUDIO"
        and audio.headers["content-type"] == "audio/mpeg"
        and audio.headers["cache-control"] == "no-store"
    )
    caps = client.get(f"{API}/assistant/capabilities", headers=auth(tok)).json()
    assert caps["speech_provider"] == "fake-speech" and caps["server_speech_to_text"] and caps["browser_fallback"]


def test_audio_upload_validation(client, tok, monkeypatch):
    monkeypatch.setattr("app.modules.assistant.router.get_speech", lambda: FakeSpeech())
    assert upload(client, tok, ctype="text/plain").status_code == 422
    assert upload(client, tok, language="fr").status_code == 422
    monkeypatch.setenv("SPEECH_MAX_AUDIO_BYTES", "10")
    from app.core.config import get_settings

    get_settings.cache_clear()
    try:
        assert upload(client, tok, content=b"x" * 50).status_code == 413
    finally:
        monkeypatch.delenv("SPEECH_MAX_AUDIO_BYTES")
        get_settings.cache_clear()
    assert (
        client.post(f"{API}/assistant/voice/transcribe", files={"audio": ("a.wav", b"abc", "audio/wav")}).status_code
        == 401
    )
    assert client.post(f"{API}/assistant/voice/synthesize", json={"text": "x"}).status_code == 401
    assert (
        client.post(
            f"{API}/assistant/voice/synthesize", json={"text": "", "language": "en"}, headers=auth(tok)
        ).status_code
        == 422
    )


def test_provider_credentials_are_never_exposed_to_clients(client, tok, monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setenv("SPEECH_PROVIDER", "azure")
    monkeypatch.setenv("AZURE_SPEECH_KEY", "SUPER-SECRET-KEY-123")
    monkeypatch.setenv("AZURE_SPEECH_REGION", "centralindia")
    get_settings.cache_clear()
    try:
        r = client.get(f"{API}/assistant/capabilities", headers=auth(tok))
        assert r.json()["speech_provider"] == "azure" and "SUPER-SECRET" not in r.text and "centralindia" not in r.text
        for path in ("/openapi.json",):
            assert "SUPER-SECRET" not in client.get(path).text
    finally:
        monkeypatch.undo()
        get_settings.cache_clear()


# ------------------------------------------------------------------ provider adapters (mocked HTTP only)
def http(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_azure_adapter_request_and_response_shapes():
    seen = {}

    def handler(req: httpx.Request):
        seen[str(req.url.host)] = req
        if "stt" in req.url.host:
            return httpx.Response(200, json={"RecognitionStatus": "Success", "DisplayText": "जयपुर के लिए प्लान बनाओ।"})
        return httpx.Response(200, content=b"MP3DATA")

    az = AzureSpeech("KEY", "centralindia", client=http(handler))
    t = az.transcribe(b"audio", "audio/wav", "hi")
    assert t.text == "जयपुर के लिए प्लान बनाओ।" and t.language == "hi" and t.provider == "azure"
    stt = seen["centralindia.stt.speech.microsoft.com"]
    assert stt.headers["Ocp-Apim-Subscription-Key"] == "KEY" and "language=hi-IN" in str(stt.url)
    a = az.synthesize("नमस्ते <b>&", "hi")
    tts = seen["centralindia.tts.speech.microsoft.com"]
    body = tts.content.decode()
    assert (
        a.data == b"MP3DATA"
        and a.mime == "audio/mpeg"
        and "hi-IN-SwaraNeural" in body
        and "&lt;b&gt;&amp;" in body
        and "xml:lang='hi-IN'" in body
    )  # XML-escaped
    bad = AzureSpeech("K", "r", client=http(lambda r: httpx.Response(200, json={"RecognitionStatus": "NoMatch"})))
    with pytest.raises(SpeechError):
        bad.transcribe(b"x", "audio/wav", "en")
    with pytest.raises(SpeechError):
        AzureSpeech("K", "r", client=http(lambda r: httpx.Response(401))).synthesize("x", "en")


def test_sarvam_adapter_request_and_response_shapes():
    import base64

    def handler(req: httpx.Request):
        assert req.headers["api-subscription-key"] == "SKEY"
        if req.url.path.endswith("speech-to-text"):
            return httpx.Response(200, json={"transcript": "show my bookings", "language_code": "en-IN"})
        return httpx.Response(200, json={"audios": [base64.b64encode(b"WAVDATA").decode()]})

    sv = SarvamSpeech("SKEY", client=http(handler))
    t = sv.transcribe(b"audio", "audio/wav", None)
    assert (t.text, t.language, t.provider) == ("show my bookings", "en", "sarvam")
    a = sv.synthesize("hello", "hi")
    assert a.data == b"WAVDATA" and a.mime == "audio/wav"
    for bad in (lambda r: httpx.Response(500), lambda r: httpx.Response(200, json={"audios": []})):
        with pytest.raises(SpeechError):
            SarvamSpeech("K", client=http(bad)).synthesize("x", "en")
    with pytest.raises(SpeechError):
        SarvamSpeech("K", client=http(lambda r: httpx.Response(200, text="nope"))).transcribe(b"x", "audio/wav", "en")


def test_conversation_rows_cascade_with_their_messages(client, tok, db):
    r = say(client, tok, "hello")
    client.delete(f"{API}/assistant/conversations/{r['conversation_id']}", headers=auth(tok))
    assert (
        db.scalar(select(func.count()).select_from(AssistantConversation)) == 0
        and db.scalar(select(func.count()).select_from(AssistantMessage)) == 0
    )
