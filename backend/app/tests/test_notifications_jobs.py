import threading
import uuid
from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import func, select, text, update

from app.core.timeutil import today_local
from app.database.session import get_engine, get_sessionmaker
from app.integrations.email.base import EmailError
from app.integrations.weather.base import DayForecast
from app.models.booking import Booking, Hotel, Notification, NotificationDelivery, RoomType
from app.models.catalog import Destination
from app.models.itinerary import Itinerary
from app.models.user import User
from app.modules.notifications.service import NotificationService
from app.workers import jobs
from app.workers.scheduler import LOCK_ID, run_once

from .conftest import auth

API = "/api/v1"


def register(client, email):
    return client.post(
        f"{API}/auth/register", json={"email": email, "password": "Passw0rdOK", "full_name": "N"}
    ).json()["access_token"]


@pytest.fixture
def tok(client, seeded):
    return register(client, "nj@example.com")


@pytest.fixture
def tok2(client, seeded):
    return register(client, "nj2@example.com")


@pytest.fixture
def uid(db, tok):
    return db.scalar(select(User.id).where(User.email == "nj@example.com"))


class FakeEmail:
    name = "fake-smtp"

    def __init__(self, fail_times=0):
        self.sent, self.fail_times = [], fail_times

    def send(self, to, subject, body):
        if self.fail_times:
            self.fail_times -= 1
            raise EmailError("smtp down")
        self.sent.append((to, subject))


# ------------------------------------------------------------------ idempotency
def test_notify_is_idempotent_by_key(db, uid):
    svc = NotificationService(db)
    assert (
        svc.notify(uid, "trip_reminder", "t", "b", "k1") is True
        and svc.notify(uid, "trip_reminder", "t", "b", "k1") is False
    )
    assert svc.notify(uid, "trip_reminder", "t", "b", "k2") is True
    db.commit()
    assert db.scalar(select(func.count()).select_from(Notification)) == 2


def test_concurrent_notify_with_one_key_creates_one_row(uid):
    Session = get_sessionmaker()
    barrier, results = threading.Barrier(8), []

    def worker():
        with Session() as s:
            barrier.wait()
            created = NotificationService(s).notify(uid, "weather_alert", "t", "b", "same-key")
            s.commit()
            results.append(created)

    ts = [threading.Thread(target=worker) for _ in range(8)]
    [t.start() for t in ts]
    [t.join(timeout=60) for t in ts]
    assert results.count(True) == 1 and results.count(False) == 7
    with Session() as s:
        assert s.scalar(select(func.count()).select_from(Notification)) == 1


# ------------------------------------------------------------------ reading
def test_notifications_are_listed_read_and_private(client, tok, tok2, db, uid):
    svc = NotificationService(db)
    for i in range(3):
        svc.notify(uid, "trip_reminder", f"Title {i}", "body", f"k{i}")
    other = db.scalar(select(User.id).where(User.email == "nj2@example.com"))
    svc.notify(other, "trip_reminder", "Not yours", "body", "other")
    db.commit()
    h = auth(tok)
    assert client.get(f"{API}/notifications/unread-count", headers=h).json() == {"unread": 3}
    page = client.get(f"{API}/notifications", params={"page_size": 2}, headers=h).json()
    assert page["total"] == 3 and len(page["items"]) == 2 and all(n["read_at"] is None for n in page["items"])
    nid = page["items"][0]["id"]
    assert client.post(f"{API}/notifications/{nid}/read", headers=h).json()["read_at"]
    assert client.post(f"{API}/notifications/{nid}/read", headers=h).status_code == 200  # idempotent
    assert client.get(f"{API}/notifications", params={"unread": True}, headers=h).json()["total"] == 2
    assert client.post(f"{API}/notifications/{nid}/read", headers=auth(tok2)).status_code == 404  # someone else's
    assert client.get(f"{API}/notifications", headers=auth(tok2)).json()["total"] == 1
    assert client.post(f"{API}/notifications/read-all", headers=h).json() == {"marked": 2}
    assert client.get(f"{API}/notifications/unread-count", headers=h).json() == {"unread": 0}
    assert (
        client.get(f"{API}/notifications").status_code == 401
        and client.post(f"{API}/notifications/read-all").status_code == 401
    )


# ------------------------------------------------------------------ external delivery
def test_email_delivery_is_skipped_without_a_provider_and_never_pretends_to_send(db, uid):
    svc = NotificationService(db)
    svc.notify(uid, "booking_confirmed", "Confirmed", "body", "e1")
    svc.notify(uid, "recommendation", "not emailed", "body", "e2")
    db.commit()
    assert svc.deliver_pending() == {"sent": 0, "skipped": 1, "failed": 0}
    d = db.scalar(select(NotificationDelivery))
    assert d.status == "skipped" and d.provider == "none" and "no email provider" in d.detail
    assert svc.deliver_pending() == {"sent": 0, "skipped": 0, "failed": 0}  # not re-attempted forever


def test_email_is_sent_exactly_once_and_failures_are_retried_a_limited_number_of_times(db, uid):
    mail = FakeEmail(fail_times=1)
    svc = NotificationService(db, email=mail)
    svc.notify(uid, "weather_alert", "Rain", "body", "w1")
    db.commit()
    assert svc.deliver_pending() == {"sent": 0, "skipped": 0, "failed": 1}
    assert svc.deliver_pending() == {"sent": 1, "skipped": 0, "failed": 0} and mail.sent == [("nj@example.com", "Rain")]
    assert svc.deliver_pending() == {"sent": 0, "skipped": 0, "failed": 0} and len(mail.sent) == 1  # never twice
    always_down = FakeEmail(fail_times=99)
    svc2 = NotificationService(db, email=always_down)
    svc2.notify(uid, "booking_cancelled", "x", "y", "w2")
    db.commit()
    results = [svc2.deliver_pending()["failed"] for _ in range(5)]
    assert results == [1, 1, 1, 0, 0]  # gives up after 3 attempts
    assert (
        db.scalar(select(NotificationDelivery.attempts).join(Notification).where(Notification.idempotency_key == "w2"))
        == 3
    )


def test_smtp_adapter_builds_and_sends_a_message_with_a_fake_server():
    from app.integrations.email.providers import SmtpEmail

    log = []

    class FakeSMTP:
        def __init__(self, host, port, timeout):
            log.append(("connect", host, port))

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def starttls(self):
            log.append("starttls")

        def login(self, u, p):
            log.append(("login", u))

        def send_message(self, msg):
            log.append(("send", msg["To"], msg["Subject"]))

    SmtpEmail("smtp.test", 587, "u", "p", "RouteAura <a@b.c>", True, smtp_factory=FakeSMTP).send("x@y.z", "Hi", "Body")
    assert log == [("connect", "smtp.test", 587), "starttls", ("login", "u"), ("send", "x@y.z", "Hi")]

    class Broken(FakeSMTP):
        def send_message(self, msg):
            raise OSError("refused")

    with pytest.raises(EmailError):
        SmtpEmail("smtp.test", 587, None, None, "a@b.c", False, smtp_factory=Broken).send("x@y.z", "Hi", "Body")


# ------------------------------------------------------------------ reminders
def _room(db):
    h = db.scalar(select(Hotel).where(Hotel.name == "Rose Courtyard Haveli"))
    return db.scalar(select(RoomType).where(RoomType.hotel_id == h.id, RoomType.name == "Heritage Room"))


def test_trip_reminders_are_sent_once_for_trips_starting_tomorrow_only(client, tok, db, uid):
    room, tomorrow = _room(db), today_local() + timedelta(days=1)
    h = auth(tok)

    def book(ci, key):
        r = client.post(
            f"{API}/bookings",
            json={
                "room_type_id": str(room.id),
                "check_in": ci.isoformat(),
                "check_out": (ci + timedelta(days=1)).isoformat(),
                "guests": 2,
                "guest_name": "Asha",
            },
            headers={**h, "Idempotency-Key": key},
        ).json()
        client.post(
            f"{API}/bookings/{r['id']}/pay",
            json={"payment_method": "dev_card_ok"},
            headers={**h, "Idempotency-Key": key + "p"},
        )
        return r

    book(tomorrow, "a")
    book(tomorrow + timedelta(days=3), "b")
    pending = client.post(
        f"{API}/bookings",
        json={
            "room_type_id": str(room.id),
            "check_in": tomorrow.isoformat(),
            "check_out": (tomorrow + timedelta(days=2)).isoformat(),
            "guests": 1,
            "guest_name": "Unpaid",
        },
        headers={**h, "Idempotency-Key": "c"},
    )
    assert pending.status_code == 201  # unpaid bookings get no reminder
    dest = db.scalar(select(Destination).where(Destination.slug == "jaipur"))
    it = client.post(
        f"{API}/itineraries/generate",
        json={"destination_id": str(dest.id), "days": 1, "start_date": tomorrow.isoformat()},
        headers=h,
    ).json()
    assert jobs.send_trip_reminders(db) == {"created": 2}
    assert jobs.send_trip_reminders(db) == {"created": 0}  # idempotent
    types = [
        (n["type"], n["title"])
        for n in client.get(f"{API}/notifications", headers=h).json()["items"]
        if n["type"] == "trip_reminder"
    ]
    assert (
        len(types) == 2 and any("Check-in tomorrow" in t for _, t in types) and any(it["title"] in t for _, t in types)
    )


# ------------------------------------------------------------------ weather alerts & adaptation notifications
class FakeWeather:
    name = "fake-weather"

    def forecast(self, lat, lng, start, end):
        out, d = [], start
        while d <= end:
            out.append(DayForecast(d, 15.0, 90.0, 25.0, None, self.name, datetime.now(UTC)))
            d += timedelta(days=1)
        return out


@pytest.fixture
def rainy_trip(client, tok, db):
    h = auth(tok)
    start = today_local() + timedelta(days=3)
    dest = db.scalar(select(Destination).where(Destination.slug == "jaipur"))
    it = client.post(
        f"{API}/itineraries/generate",
        json={"destination_id": str(dest.id), "days": 1, "start_date": start.isoformat(), "interests": ["history"]},
        headers=h,
    ).json()
    names = {a["attraction"]["name"]: a["id"] for d in it["day_plans"] for a in d["activities"]}
    if "City Palace" in names:
        client.delete(f"{API}/itineraries/{it['id']}/activities/{names['City Palace']}", headers=h)
    if "Jantar Mantar" not in names:
        j = client.get(f"{API}/attractions", params={"q": "Jantar"}).json()["items"][0]["id"]
        client.post(f"{API}/itineraries/{it['id']}/activities", json={"attraction_id": j, "day_number": 1}, headers=h)
    return it


def test_weather_alert_job_is_skipped_without_a_provider(db, rainy_trip):
    assert jobs.weather_alerts(db) == {"skipped": "no weather provider configured", "checked": 0}
    assert db.scalar(select(func.count()).select_from(Notification)) == 0


def test_weather_alert_job_notifies_once_per_proposal(client, tok, db, rainy_trip, monkeypatch):
    monkeypatch.setattr("app.modules.context.service.get_weather", lambda: FakeWeather())
    monkeypatch.setattr("app.integrations.weather.providers.get_weather", lambda: FakeWeather())
    assert jobs.weather_alerts(db) == {"checked": 1}
    assert jobs.weather_alerts(db) == {"checked": 1}
    notes = client.get(f"{API}/notifications", headers=auth(tok)).json()["items"]
    alerts = [n for n in notes if n["type"] == "weather_alert"]
    assert (
        len(alerts) == 1
        and "rain" in alerts[0]["body"].lower()
        and "nothing is changed until you approve" in alerts[0]["body"]
    )
    assert alerts[0]["data"]["itinerary_id"] == rainy_trip["id"]


def test_approving_an_adaptation_notifies_the_owner(client, tok, db, rainy_trip, monkeypatch):
    monkeypatch.setattr("app.modules.context.service.get_weather", lambda: FakeWeather())
    h = auth(tok)
    client.post(f"{API}/itineraries/{rainy_trip['id']}/context/refresh", headers=h)
    res = client.post(f"{API}/itineraries/{rainy_trip['id']}/adapt", headers=h).json()
    client.post(f"{API}/itineraries/{rainy_trip['id']}/adapt", headers=h)  # repeat: no duplicate alert
    assert (
        sum(1 for n in client.get(f"{API}/notifications", headers=h).json()["items"] if n["type"] == "weather_alert")
        == 1
    )
    client.post(f"{API}/adaptations/{res['proposals'][0]['id']}/approve", headers=h)
    types = sorted(n["type"] for n in client.get(f"{API}/notifications", headers=h).json()["items"])
    assert types == ["itinerary_adapted", "weather_alert"]


# ------------------------------------------------------------------ scheduler
def test_run_all_isolates_failures(db, monkeypatch):
    def boom(_db):
        raise RuntimeError("job broke")

    monkeypatch.setitem(jobs.JOBS, "trip_reminders", boom)
    out = jobs.run_all(db)
    assert out["trip_reminders"] == {"error": "RuntimeError"} and set(out) == {
        "expire_holds",
        "trip_reminders",
        "weather_alerts",
        "deliver_notifications",
    }
    assert out["expire_holds"] == {"released": 0}


def test_scheduler_tick_runs_every_job_and_respects_the_advisory_lock():
    res = run_once()
    assert res is not None and set(res) == {"expire_holds", "trip_reminders", "weather_alerts", "deliver_notifications"}
    conn = get_engine().raw_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT pg_advisory_lock(%s)", (LOCK_ID,))
        assert run_once() is None  # another instance holds the lock: skip the tick, do nothing
        cur.execute("SELECT pg_advisory_unlock(%s)", (LOCK_ID,))
    finally:
        conn.close()
    assert run_once() is not None


def test_scheduler_releases_expired_holds_end_to_end(client, tok, db):
    room = _room(db)
    ci = today_local() + timedelta(days=10)
    r = client.post(
        f"{API}/bookings",
        json={
            "room_type_id": str(room.id),
            "check_in": ci.isoformat(),
            "check_out": (ci + timedelta(days=1)).isoformat(),
            "guests": 1,
            "guest_name": "Hold",
        },
        headers={**auth(tok), "Idempotency-Key": "h"},
    ).json()
    db.execute(
        update(Booking)
        .where(Booking.id == uuid.UUID(r["id"]))
        .values(hold_expires_at=datetime.now(UTC) - timedelta(minutes=1))
    )
    db.commit()
    assert run_once()["expire_holds"] == {"released": 1}
    assert client.get(f"{API}/bookings/{r['id']}", headers=auth(tok)).json()["status"] == "expired"
    assert (
        db.scalar(
            text("select booked from room_inventory where day = :d and room_type_id = :r"), {"d": ci, "r": room.id}
        )
        == 0
    )
    _ = (date, Itinerary)


def test_a_tick_never_leaks_the_advisory_lock_even_when_jobs_commit_and_fail(monkeypatch):
    """Regression: the lock used to be released on a different pooled connection than it was taken on."""
    monkeypatch.setitem(jobs.JOBS, "trip_reminders", lambda _db: (_ for _ in ()).throw(RuntimeError("x")))
    for _ in range(3):
        assert run_once() is not None
    other = get_engine().connect()
    try:
        assert other.execute(text("SELECT pg_try_advisory_lock(:i)"), {"i": LOCK_ID}).scalar() is True     # nobody still holds it
        other.execute(text("SELECT pg_advisory_unlock(:i)"), {"i": LOCK_ID})
    finally:
        other.close()
