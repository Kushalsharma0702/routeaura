import threading
import uuid
from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import func, select, update

from app.core.timeutil import today_local
from app.database.session import get_sessionmaker
from app.models.booking import Booking, Hotel, Payment, RoomInventory, RoomType
from app.models.user import User
from app.modules.bookings.service import BookingService, refund_amount
from app.schemas.booking import BookingCreate

from .conftest import auth

API = "/api/v1"
CI = today_local() + timedelta(days=30)
CO = CI + timedelta(days=2)


def register(client, email):
    return client.post(
        f"{API}/auth/register", json={"email": email, "password": "Passw0rdOK", "full_name": "Guest"}
    ).json()["access_token"]


@pytest.fixture
def tok(client, seeded):
    return register(client, "bk@example.com")


@pytest.fixture
def tok2(client, seeded):
    return register(client, "bk2@example.com")


@pytest.fixture
def room(db, seeded):
    """Rose Courtyard Haveli / Royal Suite: capacity 3, 2 rooms."""
    h = db.scalar(select(Hotel).where(Hotel.name == "Rose Courtyard Haveli"))
    return db.scalar(select(RoomType).where(RoomType.hotel_id == h.id, RoomType.name == "Royal Suite"))


def body(room, **kw):
    return {
        "room_type_id": str(room.id),
        "check_in": CI.isoformat(),
        "check_out": CO.isoformat(),
        "rooms": 1,
        "guests": 2,
        "guest_name": "Asha Rao",
        **kw,
    }


def book(client, tok, room, key=None, **kw):
    return client.post(
        f"{API}/bookings", json=body(room, **kw), headers={**auth(tok), "Idempotency-Key": key or uuid.uuid4().hex}
    )


def pay(client, tok, bid, method="dev_card_ok", key=None):
    return client.post(
        f"{API}/bookings/{bid}/pay",
        json={"payment_method": method},
        headers={**auth(tok), "Idempotency-Key": key or uuid.uuid4().hex},
    )


def free_rooms(db, room, day=CI):
    db.expire_all()
    inv = db.get(RoomInventory, (room.id, day))
    return room.total_rooms if inv is None else inv.total - inv.booked


# ------------------------------------------------------------------ hotels & availability
def test_public_hotel_catalogue_search_filters_and_detail(client, seeded):
    r = client.get(f"{API}/hotels").json()
    assert r["total"] == 10 and all(
        h["source"] == "seed" and h["room_types"] and h["from_price_minor"] for h in r["items"]
    )
    assert client.get(f"{API}/hotels", params={"destination": "jaipur"}).json()["total"] == 2
    assert [h["name"] for h in client.get(f"{API}/hotels", params={"q": "rose"}).json()["items"]] == [
        "Rose Courtyard Haveli"
    ]
    assert client.get(f"{API}/hotels", params={"min_stars": 4}).json()["total"] == 4
    cheap = client.get(f"{API}/hotels", params={"max_price_minor": 250000, "sort": "price"}).json()["items"]
    assert (
        cheap
        and all(h["from_price_minor"] <= 250000 for h in cheap)
        and [h["from_price_minor"] for h in cheap] == sorted(h["from_price_minor"] for h in cheap)
    )
    assert client.get(f"{API}/hotels", params={"page_size": 3, "page": 2}).json()["items"].__len__() == 3
    h = client.get(f"{API}/hotels/rose-courtyard-haveli").json()
    assert h["destination_name"] == "Jaipur" and {r["name"] for r in h["room_types"]} == {
        "Heritage Room",
        "Royal Suite",
    }
    assert (
        client.get(f"{API}/hotels/nope").status_code == 404
        and client.get(f"{API}/hotels", params={"sort": "x"}).status_code == 422
    )


def test_unpublished_hotels_are_hidden(client, seeded, db):
    db.execute(update(Hotel).where(Hotel.name == "Rose Courtyard Haveli").values(is_published=False))
    db.commit()
    assert client.get(f"{API}/hotels/rose-courtyard-haveli").status_code == 404
    assert client.get(f"{API}/hotels").json()["total"] == 9


def test_availability_reports_prices_capacity_and_reasons(client, seeded, room):
    q = {"check_in": CI.isoformat(), "check_out": CO.isoformat(), "guests": 2, "rooms": 1}
    out = client.get(f"{API}/hotels/rose-courtyard-haveli/availability", params=q).json()
    suite = next(o for o in out["options"] if o["room_type"]["name"] == "Royal Suite")
    assert (
        suite["nights"] == 2
        and suite["available_rooms"] == 2
        and suite["total_minor"] == 9200 * 100 * 2
        and suite["can_book"] is True
    )
    big = client.get(f"{API}/hotels/rose-courtyard-haveli/availability", params={**q, "guests": 9}).json()
    assert all(not o["can_book"] and "at most" in o["reason"] for o in big["options"])
    for bad in (
        {"check_out": CI.isoformat()},
        {"check_in": (today_local() - timedelta(days=1)).isoformat()},
        {"check_out": (CI + timedelta(days=31)).isoformat()},
    ):
        assert client.get(f"{API}/hotels/rose-courtyard-haveli/availability", params={**q, **bad}).status_code == 422
    assert (
        client.get(f"{API}/hotels/rose-courtyard-haveli/availability", params={"check_in": CI.isoformat()}).status_code
        == 422
    )


# ------------------------------------------------------------------ create / hold / pay / confirm
def test_booking_holds_rooms_then_payment_confirms_it(client, tok, room, db):
    r = book(client, tok, room)
    assert r.status_code == 201, r.text
    b = r.json()
    assert (
        b["status"] == "pending_payment"
        and b["payment_status"] == "unpaid"
        and b["total_minor"] == 9200 * 100 * 2
        and b["hold_expires_at"]
    )
    assert b["reference"].startswith("RA-") and b["nights"] == 2 and "Free cancellation" in b["cancellation_policy"]
    assert (
        free_rooms(db, room) == 1
        and free_rooms(db, room, CI + timedelta(days=1)) == 1
        and free_rooms(db, room, CO) == 2
    )  # check-out night not held
    paid = pay(client, tok, b["id"])
    assert paid.status_code == 200
    p = paid.json()
    assert (
        p["status"] == "confirmed"
        and p["payment_status"] == "paid"
        and p["hold_expires_at"] is None
        and p["confirmed_at"]
    )
    assert (
        p["payments"][0]["simulated"] is True
        and p["payments"][0]["provider"] == "development"
        and "no real money" in p["payment_note"]
    )
    assert p["refund_if_cancelled_now_minor"] == p["total_minor"]
    notes = client.get(f"{API}/notifications", headers=auth(tok)).json()
    assert (
        notes["total"] == 1
        and notes["items"][0]["type"] == "booking_confirmed"
        and b["reference"] not in ""
        and "confirmed" in notes["items"][0]["title"]
    )
    assert client.get(f"{API}/bookings/{b['id']}", headers=auth(tok)).json()["status"] == "confirmed"


def test_declined_payment_keeps_the_hold_and_can_be_retried(client, tok, room, db):
    b = book(client, tok, room).json()
    r = pay(client, tok, b["id"], "dev_card_declined")
    assert (
        r.status_code == 402
        and r.json()["error"]["code"] == "payment_failed"
        and "declined" in r.json()["error"]["message"]
    )
    cur = client.get(f"{API}/bookings/{b['id']}", headers=auth(tok)).json()
    assert cur["status"] == "pending_payment" and [p["status"] for p in cur["payments"]] == ["failed"]
    assert free_rooms(db, room) == 1  # still held
    assert pay(client, tok, b["id"], "dev_card_ok").json()["status"] == "confirmed"


def test_payment_provider_outage_is_reported_without_confirming(client, tok, room):
    b = book(client, tok, room).json()
    r = pay(client, tok, b["id"], "dev_card_error")
    assert r.status_code == 502 and r.json()["error"]["code"] == "payment_provider_error"
    assert client.get(f"{API}/bookings/{b['id']}", headers=auth(tok)).json()["status"] == "pending_payment"


@pytest.mark.parametrize("token", ["4242424242424242", "4242 4242 4242 4242", "CARD-NUMBER", "x", "dev card"])
def test_card_numbers_and_unknown_tokens_are_never_accepted(client, tok, room, token, db):
    b = book(client, tok, room).json()
    r = pay(client, tok, b["id"], token)
    assert r.status_code in (422, 502)
    assert db.scalar(select(func.count()).select_from(Payment).where(Payment.status == "succeeded")) == 0


def test_validation_and_capacity_rules(client, tok, room):
    for kw in (
        {"guests": 7},
        {"rooms": 0},
        {"rooms": 11},
        {"guest_name": "x"},
        {"check_out": CI.isoformat()},
        {"check_in": (today_local() - timedelta(days=1)).isoformat()},
        {"check_out": (CI + timedelta(days=31)).isoformat()},
    ):
        assert book(client, tok, room, **kw).status_code == 422, kw
    assert book(client, tok, room, itinerary_id=str(uuid.uuid4())).json()["error"]["code"] == "unknown_itinerary"
    assert (
        client.post(f"{API}/bookings", json=body(room), headers=auth(tok)).json()["error"]["code"]
        == "idempotency_key_required"
    )
    assert book(client, tok, room, room_type_id=str(uuid.uuid4())).json()["error"]["code"] == "unknown_room"
    assert client.post(f"{API}/bookings", json=body(room)).status_code == 401


# ------------------------------------------------------------------ idempotency
def test_create_is_idempotent_and_rejects_key_reuse_with_a_different_request(client, tok, room, db):
    key = "idem-create-1"
    a = book(client, tok, room, key=key)
    b = book(client, tok, room, key=key)
    assert (
        a.status_code == 201
        and b.status_code == 200
        and b.headers["Idempotent-Replayed"] == "true"
        and a.json()["id"] == b.json()["id"]
    )
    assert db.scalar(select(func.count()).select_from(Booking)) == 1 and free_rooms(db, room) == 1  # one hold, not two
    other = book(client, tok, room, key=key, guests=1)
    assert other.status_code == 422 and other.json()["error"]["code"] == "idempotency_key_reuse"
    assert book(client, tok, room, key="x" * 81).status_code == 422


def test_idempotency_keys_are_per_user(client, tok, tok2, room):
    assert book(client, tok, room, key="shared").status_code == 201
    r = book(client, tok2, room, key="shared")
    assert r.status_code == 201 and r.headers.get("Idempotent-Replayed") is None


def test_pay_is_idempotent_and_never_double_charges(client, tok, room, db):
    b = book(client, tok, room).json()
    first = pay(client, tok, b["id"], key="pay-1")
    again = pay(client, tok, b["id"], key="pay-1")
    assert first.status_code == again.status_code == 200 and len(again.json()["payments"]) == 1
    assert pay(client, tok, b["id"], key="pay-2").json()["error"]["code"] == "already_paid"
    assert db.scalar(select(func.count()).select_from(Payment).where(Payment.kind == "charge")) == 1
    assert (
        client.post(
            f"{API}/bookings/{b['id']}/pay", json={"payment_method": "dev_card_ok"}, headers=auth(tok)
        ).status_code
        == 422
    )  # key required


def test_a_failed_payment_replay_returns_the_same_failure(client, tok, room):
    b = book(client, tok, room).json()
    assert pay(client, tok, b["id"], "dev_card_declined", key="k1").status_code == 402
    assert pay(client, tok, b["id"], "dev_card_declined", key="k1").status_code == 402


# ------------------------------------------------------------------ inventory consistency
def test_sold_out_then_cancel_releases_exactly_what_was_held(client, tok, tok2, room, db):
    a, b = book(client, tok, room).json(), book(client, tok2, room).json()
    assert free_rooms(db, room) == 0
    third = book(client, tok, room)
    assert third.status_code == 409 and third.json()["error"]["code"] == "sold_out"
    assert free_rooms(db, room) == 0  # the failed attempt left no trace
    sa = client.get(
        f"{API}/hotels/rose-courtyard-haveli/availability",
        params={"check_in": CI.isoformat(), "check_out": CO.isoformat()},
    ).json()
    assert (
        next(o for o in sa["options"] if o["room_type"]["name"] == "Royal Suite")["reason"]
        == "Sold out for these dates"
    )
    assert client.post(f"{API}/bookings/{a['id']}/cancel", json={}, headers=auth(tok)).status_code == 200
    assert free_rooms(db, room) == 1
    assert client.post(f"{API}/bookings/{a['id']}/cancel", json={}, headers=auth(tok)).status_code == 200  # idempotent
    assert free_rooms(db, room) == 1  # not released twice
    assert book(client, tok, room).status_code == 201 and b["id"]


def test_partially_overlapping_stays_check_every_night(client, tok, tok2, room, db):
    book(client, tok, room, rooms=2, guests=2)  # takes both rooms for CI..CO
    shifted = book(
        client,
        tok2,
        room,
        check_in=(CI + timedelta(days=1)).isoformat(),
        check_out=(CO + timedelta(days=1)).isoformat(),
    )
    assert (
        shifted.status_code == 409 and free_rooms(db, room, CO) == 2
    )  # night CI+1 is full, so nothing was taken on CO
    after = book(client, tok2, room, check_in=CO.isoformat(), check_out=(CO + timedelta(days=1)).isoformat())
    assert after.status_code == 201  # back-to-back stays are fine


def test_inventory_never_goes_negative_or_overbooked_at_database_level(db, room):
    db.add(RoomInventory(room_type_id=room.id, day=CI, total=1, booked=0))
    db.commit()
    from sqlalchemy.exc import IntegrityError

    with pytest.raises(IntegrityError):
        db.execute(
            update(RoomInventory).where(RoomInventory.room_type_id == room.id, RoomInventory.day == CI).values(booked=2)
        )
        db.commit()
    db.rollback()


# ------------------------------------------------------------------ concurrency (real competing transactions)
def test_concurrent_bookings_for_the_last_room_never_overbook(client, seeded, room):
    Session = get_sessionmaker()
    with Session() as s:
        users = []
        for i in range(8):
            u = User(email=f"race{i}@example.com", full_name=f"Racer {i}", password_hash="x")
            s.add(u)
            users.append(u)
        s.commit()
        user_ids = [u.id for u in users]
        s.execute(update(RoomType).where(RoomType.id == room.id).values(total_rooms=2))
        s.commit()
    results, barrier = [], threading.Barrier(8)

    def worker(uid):
        with Session() as s:
            svc = BookingService(s)
            user = s.get(User, uid)
            data = BookingCreate(room_type_id=room.id, check_in=CI, check_out=CO, rooms=1, guests=2, guest_name="Racer")
            barrier.wait()
            try:
                svc.create(user, data, f"race-{uid}")
                results.append("ok")
            except Exception as e:  # noqa: BLE001
                results.append(getattr(e, "code", type(e).__name__))

    threads = [threading.Thread(target=worker, args=(u,)) for u in user_ids]
    [t.start() for t in threads]
    [t.join(timeout=60) for t in threads]
    assert sorted(results) == ["ok", "ok"] + ["sold_out"] * 6, results
    with Session() as s:
        inv = s.scalars(select(RoomInventory).where(RoomInventory.room_type_id == room.id)).all()
        assert {(r.total, r.booked) for r in inv} == {(2, 2)} and len(
            inv
        ) == 2  # exactly the 2 nights, fully booked, never more
        assert s.scalar(select(func.count()).select_from(Booking)) == 2


def test_concurrent_identical_requests_with_one_key_create_one_booking(client, seeded, room, tok):
    Session = get_sessionmaker()
    with Session() as s:
        uid = s.scalar(select(User.id).where(User.email == "bk@example.com"))
    results, barrier = [], threading.Barrier(6)

    def worker():
        with Session() as s:
            svc = BookingService(s)
            barrier.wait()
            try:
                b, replayed = svc.create(
                    s.get(User, uid),
                    BookingCreate(
                        room_type_id=room.id, check_in=CI, check_out=CO, rooms=1, guests=2, guest_name="Same Guest"
                    ),
                    "one-key",
                )
                results.append((str(b.id), replayed))
            except Exception as e:  # noqa: BLE001
                results.append(("error", getattr(e, "code", type(e).__name__)))

    threads = [threading.Thread(target=worker) for _ in range(6)]
    [t.start() for t in threads]
    [t.join(timeout=60) for t in threads]
    assert len({r[0] for r in results}) == 1 and "error" not in {r[0] for r in results}, results
    assert sum(1 for _, replayed in results if not replayed) == 1  # exactly one creator, the rest replays
    with Session() as s:
        assert s.scalar(select(func.count()).select_from(Booking)) == 1
        assert {(r.booked) for r in s.scalars(select(RoomInventory).where(RoomInventory.room_type_id == room.id))} == {
            1
        }  # held once, not six times


def test_concurrent_cancel_and_pay_leave_consistent_inventory(client, seeded, room, tok):
    b = book(client, tok, room).json()
    Session = get_sessionmaker()
    with Session() as s:
        uid = s.scalar(select(User.id).where(User.email == "bk@example.com"))
    barrier, out = threading.Barrier(2), []

    def cancel():
        with Session() as s:
            barrier.wait()
            try:
                BookingService(s).cancel(s.get(User, uid), uuid.UUID(b["id"]), "race")
                out.append("cancelled")
            except Exception as e:  # noqa: BLE001
                out.append(getattr(e, "code", type(e).__name__))

    def payit():
        with Session() as s:
            barrier.wait()
            try:
                BookingService(s).pay(s.get(User, uid), uuid.UUID(b["id"]), "dev_card_ok", "race-pay")
                out.append("paid")
            except Exception as e:  # noqa: BLE001
                out.append(getattr(e, "code", type(e).__name__))

    ts = [threading.Thread(target=cancel), threading.Thread(target=payit)]
    [t.start() for t in ts]
    [t.join(timeout=60) for t in ts]
    with Session() as s:
        final = s.get(Booking, uuid.UUID(b["id"]))
        booked = [r.booked for r in s.scalars(select(RoomInventory).where(RoomInventory.room_type_id == room.id))]
        assert final.status == "cancelled" and booked == [0, 0], (
            out,
            final.status,
            booked,
        )  # cancel always ends released; pay either lost or refunded
        if final.payment_status != "unpaid":
            assert final.payment_status == "refunded"


# ------------------------------------------------------------------ cancellation, refunds
def test_refund_policy_is_pure_and_tiered():
    today = date(2030, 1, 10)
    assert (
        refund_amount(1000, date(2030, 1, 12), today) == 1000 and refund_amount(1000, date(2030, 2, 1), today) == 1000
    )
    assert refund_amount(1000, date(2030, 1, 11), today) == 500 and refund_amount(1000, date(2030, 1, 10), today) == 0
    assert (
        refund_amount(1000, date(2030, 1, 10), today, by_admin=True) == 1000
        and refund_amount(1001, date(2030, 1, 11), today) == 500
    )


def test_cancelling_a_confirmed_booking_refunds_and_notifies(client, tok, room, db):
    b = book(client, tok, room).json()
    pay(client, tok, b["id"])
    c = client.post(f"{API}/bookings/{b['id']}/cancel", json={"reason": "plans changed"}, headers=auth(tok)).json()
    assert (
        c["status"] == "cancelled"
        and c["payment_status"] == "refunded"
        and c["refund_amount_minor"] == c["total_minor"]
        and c["cancelled_by"] == "traveler"
    )
    assert [p["kind"] for p in c["payments"]] == ["charge", "refund"] and c["payments"][1]["status"] == "succeeded"
    assert free_rooms(db, room) == 2
    types = [n["type"] for n in client.get(f"{API}/notifications", headers=auth(tok)).json()["items"]]
    assert sorted(types) == ["booking_cancelled", "booking_confirmed"]
    assert db.scalar(select(func.count()).select_from(Payment).where(Payment.kind == "refund")) == 1


def test_late_cancellation_gets_a_partial_or_no_refund(client, tok, room, db):
    soon = today_local() + timedelta(days=1)
    b = book(client, tok, room, check_in=soon.isoformat(), check_out=(soon + timedelta(days=1)).isoformat()).json()
    pay(client, tok, b["id"])
    c = client.post(f"{API}/bookings/{b['id']}/cancel", json={}, headers=auth(tok)).json()
    assert c["refund_amount_minor"] == c["total_minor"] // 2 and c["payment_status"] == "refunded"
    today = today_local()
    b2 = book(client, tok, room, check_in=today.isoformat(), check_out=(today + timedelta(days=1)).isoformat()).json()
    pay(client, tok, b2["id"])
    c2 = client.post(f"{API}/bookings/{b2['id']}/cancel", json={}, headers=auth(tok)).json()
    assert (
        c2["refund_amount_minor"] == 0
        and c2["payment_status"] == "paid"
        and "no refund is due" in client.get(f"{API}/notifications", headers=auth(tok)).json()["items"][0]["body"]
    )


def test_cancelling_before_payment_just_releases_the_hold(client, tok, room, db):
    b = book(client, tok, room).json()
    c = client.post(f"{API}/bookings/{b['id']}/cancel", json={}, headers=auth(tok)).json()
    assert (
        c["status"] == "cancelled"
        and c["payment_status"] == "unpaid"
        and c["payments"] == []
        and free_rooms(db, room) == 2
    )


def test_a_failed_refund_is_marked_pending_and_can_be_retried_by_an_admin(client, tok, room, db, monkeypatch):
    from app.integrations.payments.base import PaymentError

    b = book(client, tok, room).json()
    pay(client, tok, b["id"])
    from app.integrations.payments.providers import DevelopmentPayments

    monkeypatch.setattr(DevelopmentPayments, "refund", lambda *a, **k: (_ for _ in ()).throw(PaymentError("down")))
    c = client.post(f"{API}/bookings/{b['id']}/cancel", json={}, headers=auth(tok)).json()
    assert (
        c["status"] == "cancelled"
        and c["payment_status"] == "refund_pending"
        and c["payments"][-1]["status"] == "failed"
    )
    assert "booking_refund_failed" in [
        n["type"] for n in client.get(f"{API}/notifications", headers=auth(tok)).json()["items"]
    ]
    monkeypatch.undo()
    admin = register(client, "boss@example.com")
    db.execute(update(User).where(User.email == "boss@example.com").values(role="admin"))
    db.commit()
    assert client.post(f"{API}/admin/bookings/{b['id']}/retry-refund", headers=auth(tok)).status_code == 403
    r = client.post(f"{API}/admin/bookings/{b['id']}/retry-refund", headers=auth(admin))
    assert r.status_code == 200 and r.json()["payment_status"] == "refunded"
    assert client.post(f"{API}/admin/bookings/{b['id']}/retry-refund", headers=auth(admin)).status_code == 409


def test_expired_holds_are_released_by_the_job_and_cannot_be_paid(client, tok, room, db):
    b = book(client, tok, room).json()
    db.execute(
        update(Booking)
        .where(Booking.id == uuid.UUID(b["id"]))
        .values(hold_expires_at=datetime.now(UTC) - timedelta(minutes=1))
    )
    db.commit()
    assert BookingService(db).expire_holds() == 1 and BookingService(db).expire_holds() == 0  # idempotent
    cur = client.get(f"{API}/bookings/{b['id']}", headers=auth(tok)).json()
    assert cur["status"] == "expired" and free_rooms(db, room) == 2
    assert pay(client, tok, b["id"]).json()["error"]["code"] == "not_payable"
    assert [n["title"] for n in client.get(f"{API}/notifications", headers=auth(tok)).json()["items"]][0].endswith(
        "expired"
    )
    # paying exactly at expiry also expires it instead of charging
    b2 = book(client, tok, room).json()
    db.execute(
        update(Booking)
        .where(Booking.id == uuid.UUID(b2["id"]))
        .values(hold_expires_at=datetime.now(UTC) - timedelta(seconds=1))
    )
    db.commit()
    r = pay(client, tok, b2["id"])
    assert r.status_code == 409 and r.json()["error"]["code"] == "hold_expired"
    assert free_rooms(db, room) == 2 and db.scalar(select(func.count()).select_from(Payment)) == 0


# ------------------------------------------------------------------ authorization and admin
def test_bookings_are_private_to_their_owner(client, tok, tok2, room):
    b = book(client, tok, room).json()
    h2 = auth(tok2)
    assert client.get(f"{API}/bookings/{b['id']}", headers=h2).status_code == 404
    assert client.get(f"{API}/bookings", headers=h2).json()["total"] == 0
    assert pay(client, tok2, b["id"]).status_code == 404
    assert client.post(f"{API}/bookings/{b['id']}/cancel", json={}, headers=h2).status_code == 404
    assert client.get(f"{API}/bookings/{b['id']}").status_code == 401


def test_listing_filters_and_paginates_my_bookings(client, tok, room):
    for i in range(3):
        book(
            client,
            tok,
            room,
            check_in=(CI + timedelta(days=10 * i)).isoformat(),
            check_out=(CI + timedelta(days=10 * i + 1)).isoformat(),
        )
    assert client.get(f"{API}/bookings", params={"page_size": 2}, headers=auth(tok)).json()["total"] == 3
    assert (
        len(client.get(f"{API}/bookings", params={"page_size": 2, "page": 2}, headers=auth(tok)).json()["items"]) == 1
    )
    assert client.get(f"{API}/bookings", params={"status": "confirmed"}, headers=auth(tok)).json()["total"] == 0
    assert client.get(f"{API}/bookings", params={"status": "bogus"}, headers=auth(tok)).status_code == 422


@pytest.fixture
def admin_tok(client, db):
    t = register(client, "admin-bk@example.com")
    db.execute(update(User).where(User.email == "admin-bk@example.com").values(role="admin"))
    db.commit()
    return t


def test_admin_endpoints_require_the_admin_role(client, tok, room, db):
    h = auth(tok)
    hotel_id = str(room.hotel_id)
    calls = [
        ("get", "/admin/hotels", None),
        ("post", "/admin/hotels", {}),
        ("patch", f"/admin/hotels/{hotel_id}", {}),
        ("delete", f"/admin/hotels/{hotel_id}", None),
        ("post", f"/admin/hotels/{hotel_id}/rooms", {}),
        ("patch", f"/admin/rooms/{room.id}", {}),
        ("put", f"/admin/rooms/{room.id}/inventory", {}),
        ("get", "/admin/bookings", None),
        ("post", f"/admin/bookings/{uuid.uuid4()}/cancel", {}),
        ("get", "/admin/analytics", None),
    ]
    for method, url, jb in calls:
        r1 = getattr(client, method)(f"{API}{url}", headers=h, **({"json": jb} if jb is not None else {}))
        r0 = getattr(client, method)(f"{API}{url}", **({"json": jb} if jb is not None else {}))
        assert r1.status_code == 403 and r0.status_code == 401, (method, url)


def test_admin_hotel_room_and_inventory_management(client, admin_tok, room, tok, db):
    h = auth(admin_tok)
    dest = client.get(f"{API}/destinations?q=jaipur").json()["items"][0]["id"]
    new = client.post(
        f"{API}/admin/hotels",
        json={
            "destination_id": dest,
            "name": "Test Palace",
            "latitude": 26.9,
            "longitude": 75.8,
            "star_rating": 5,
            "is_published": True,
        },
        headers=h,
    )
    assert new.status_code == 201 and new.json()["slug"] == "test-palace"
    hid = new.json()["id"]
    assert (
        client.post(
            f"{API}/admin/hotels",
            json={"destination_id": dest, "name": "Bad", "latitude": 95, "longitude": 0},
            headers=h,
        ).status_code
        == 422
    )
    rt = client.post(
        f"{API}/admin/hotels/{hid}/rooms",
        json={"name": "Deluxe", "capacity": 2, "price_per_night_minor": 500000, "total_rooms": 3},
        headers=h,
    )
    assert rt.status_code == 201
    rid = rt.json()["id"]
    assert client.get(f"{API}/hotels/test-palace").json()["from_price_minor"] == 500000
    assert (
        client.patch(
            f"{API}/admin/rooms/{rid}", json={"price_per_night_minor": 450000, "capacity": 3}, headers=h
        ).json()["price_per_night_minor"]
        == 450000
    )
    assert client.patch(f"{API}/admin/rooms/{rid}", json={"capacity": None}, headers=h).status_code == 422
    # blackout a night, then check availability and booking refuse it
    client.put(
        f"{API}/admin/rooms/{rid}/inventory",
        json={"start": CI.isoformat(), "end": CI.isoformat(), "total": 0},
        headers=h,
    )
    q = {"check_in": CI.isoformat(), "check_out": CO.isoformat()}
    assert client.get(f"{API}/hotels/test-palace/availability", params=q).json()["options"][0]["available_rooms"] == 0
    r = client.post(
        f"{API}/bookings",
        json={
            "room_type_id": rid,
            "check_in": CI.isoformat(),
            "check_out": CO.isoformat(),
            "guests": 2,
            "guest_name": "Tester",
        },
        headers={**auth(tok), "Idempotency-Key": "k"},
    )
    assert r.status_code == 409
    # cannot lower inventory below what is booked
    ok = client.post(
        f"{API}/bookings",
        json={
            "room_type_id": rid,
            "check_in": (CI + timedelta(days=1)).isoformat(),
            "check_out": CO.isoformat(),
            "guests": 2,
            "guest_name": "Tester",
        },
        headers={**auth(tok), "Idempotency-Key": "k2"},
    )
    assert ok.status_code == 201
    low = client.put(
        f"{API}/admin/rooms/{rid}/inventory",
        json={"start": (CI + timedelta(days=1)).isoformat(), "end": (CI + timedelta(days=1)).isoformat(), "total": 0},
        headers=h,
    )
    assert low.status_code == 409 and low.json()["error"]["code"] == "inventory_below_booked"
    assert (
        client.put(
            f"{API}/admin/rooms/{rid}/inventory",
            json={"start": CO.isoformat(), "end": CI.isoformat(), "total": 1},
            headers=h,
        ).status_code
        == 422
    )
    # a hotel with active bookings cannot be deleted
    assert client.delete(f"{API}/admin/hotels/{hid}", headers=h).status_code == 409
    client.post(f"{API}/admin/bookings/{ok.json()['id']}/cancel", json={"reason": "test"}, headers=h)
    assert client.delete(f"{API}/admin/hotels/{hid}", headers=h).status_code == 204
    assert client.get(f"{API}/hotels/test-palace").status_code == 404


def test_admin_can_cancel_any_booking_with_a_full_refund_and_list_with_filters(client, admin_tok, tok, room):
    b = book(client, tok, room).json()
    pay(client, tok, b["id"])
    soon = today_local()
    late = book(client, tok, room, check_in=soon.isoformat(), check_out=(soon + timedelta(days=1)).isoformat()).json()
    pay(client, tok, late["id"])
    h = auth(admin_tok)
    all_ = client.get(f"{API}/admin/bookings", headers=h).json()
    assert all_["total"] == 2 and all_["items"][0]["user_email"] == "bk@example.com"
    assert client.get(f"{API}/admin/bookings", params={"q": b["reference"]}, headers=h).json()["total"] == 1
    assert client.get(f"{API}/admin/bookings", params={"status": "confirmed"}, headers=h).json()["total"] == 2
    c = client.post(
        f"{API}/admin/bookings/{late['id']}/cancel", json={"reason": "overbooked elsewhere"}, headers=h
    ).json()
    assert (
        c["cancelled_by"] == "admin"
        and c["refund_amount_minor"] == c["total_minor"]
        and c["payment_status"] == "refunded"
    )  # admin cancels refund in full


def test_admin_analytics_are_computed_from_real_rows(client, admin_tok, tok, room):
    b = book(client, tok, room).json()
    pay(client, tok, b["id"])
    book(
        client, tok, room, check_in=(CI + timedelta(days=5)).isoformat(), check_out=(CI + timedelta(days=6)).isoformat()
    )  # stays pending
    a = client.get(f"{API}/admin/analytics", headers=auth(admin_tok)).json()
    assert a["bookings_by_status"] == {"confirmed": 1, "pending_payment": 1}
    assert (
        a["confirmed_revenue_minor"] == 9200 * 100 * 2
        and a["refunded_minor"] == 0
        and a["hotels"] == 10
        and a["users"] == 2
    )
    assert a["top_destinations"] == [{"destination": "Jaipur", "bookings": 1}] and a["monthly"][0]["bookings"] == 2
    assert 0 < a["future_occupancy_pct"] < 100 and "simulated" in a["notes"][0]
