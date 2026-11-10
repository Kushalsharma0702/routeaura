"""Hotels, availability and bookings.

Concurrency model (PostgreSQL, READ COMMITTED):
* Inventory rows (room_type, night) are locked with SELECT ... FOR UPDATE in date order, so concurrent bookings
  for overlapping nights serialise and never deadlock; `booked <= total` is also a database CHECK constraint.
* Create/pay/cancel/expire lock the booking row first, so concurrent transitions cannot double-release inventory.
* Idempotency: a unique (user, idempotency_key) on bookings and (booking, key) on payments; replays return the
  original result, key reuse with a different payload is rejected.
"""

from __future__ import annotations

import hashlib
import json
import secrets
import uuid
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError, not_found
from app.core.timeutil import today_local
from app.integrations.payments.base import PaymentError, PaymentProvider
from app.integrations.payments.providers import get_payments
from app.models.booking import Booking, Hotel, Payment, RoomInventory, RoomType
from app.models.catalog import Destination
from app.models.itinerary import Itinerary
from app.models.user import User
from app.modules.catalog.slugs import unique_slug
from app.modules.notifications.service import NotificationService
from app.schemas.booking import (
    AvailabilityOut,
    BookingCreate,
    BookingOut,
    HotelIn,
    HotelOut,
    HotelUpdate,
    InventoryOverride,
    PaymentOut,
    RoomAvailability,
    RoomTypeIn,
    RoomTypeOut,
    RoomTypeUpdate,
)

POLICY = "Free cancellation up to 2 days before check-in (100% refund); 1 day before: 50% refund; later: no refund."


def refund_amount(total_minor: int, check_in: date, today: date, by_admin: bool = False) -> int:
    """Pure cancellation policy. Admin cancellations always refund in full."""
    if by_admin:
        return total_minor
    days = (check_in - today).days
    if days >= 2:
        return total_minor
    if days == 1:
        return total_minor // 2
    return 0


def request_hash(data: BookingCreate) -> str:
    payload = json.dumps({**data.model_dump(mode="json")}, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()


def new_reference() -> str:
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "RA-" + "".join(secrets.choice(alphabet) for _ in range(8))


class BookingService:
    def __init__(self, db: Session, payments: PaymentProvider | None = None, now=None):
        self.db = db
        self.payments = payments if payments is not None else get_payments()
        self.notifier = NotificationService(db)
        self._now = now or (lambda: datetime.now(UTC))

    # ================================================================== catalogue (public)
    def _hotel_out(self, h: Hotel, published_only: bool = True) -> HotelOut:
        rooms = [r for r in h.room_types if r.is_active or not published_only]
        prices = [r.price_per_night_minor for r in rooms if r.is_active]
        return HotelOut(
            id=h.id,
            slug=h.slug,
            name=h.name,
            description=h.description,
            address=h.address,
            latitude=float(h.latitude),
            longitude=float(h.longitude),
            star_rating=h.star_rating,
            amenities=h.amenities,
            images=h.images,
            is_published=h.is_published,
            source=h.source,
            destination_id=h.destination_id,
            destination_name=h.destination.name,
            room_types=[RoomTypeOut.model_validate(r) for r in rooms],
            from_price_minor=min(prices) if prices else None,
        )

    def list_hotels(
        self,
        *,
        published_only: bool,
        q: str | None,
        destination: str | None,
        min_stars: int | None,
        max_price_minor: int | None,
        sort: str,
        page: int,
        page_size: int,
    ):
        stmt = select(Hotel).where(Hotel.deleted_at.is_(None))
        if published_only:
            stmt = stmt.where(Hotel.is_published.is_(True), Hotel.destination.has(Destination.is_published.is_(True)))
        if q:
            like = "%" + q.replace("\\", "\\\\").replace("%", r"\%").replace("_", r"\_") + "%"
            stmt = stmt.where(Hotel.name.ilike(like) | Hotel.description.ilike(like))
        if destination:
            try:
                stmt = stmt.where(Hotel.destination_id == uuid.UUID(destination))
            except ValueError:
                stmt = stmt.where(Hotel.destination.has(Destination.slug == destination))
        if min_stars:
            stmt = stmt.where(Hotel.star_rating >= min_stars)
        if max_price_minor is not None:
            stmt = stmt.where(
                Hotel.room_types.any(
                    (RoomType.is_active.is_(True)) & (RoomType.price_per_night_minor <= max_price_minor)
                )
            )
        hotels = list(self.db.scalars(stmt))
        key = {
            "name": lambda h: h.name.lower(),
            "stars": lambda h: (-(h.star_rating or 0), h.name.lower()),
            "price": lambda h: (
                min((r.price_per_night_minor for r in h.room_types if r.is_active), default=10**12),
                h.name.lower(),
            ),
        }[sort]
        hotels.sort(key=key)
        total = len(hotels)
        window = hotels[(page - 1) * page_size : page * page_size]
        return [self._hotel_out(h, published_only) for h in window], total

    def get_hotel(self, ref: str, *, published_only: bool) -> Hotel:
        try:
            h = self.db.get(Hotel, uuid.UUID(ref))
        except ValueError:
            h = self.db.scalar(select(Hotel).where(Hotel.slug == ref))
        if (
            h is None
            or h.deleted_at is not None
            or (published_only and not (h.is_published and h.destination.is_published))
        ):
            raise not_found("Hotel")
        return h

    def hotel_out(self, ref: str, *, published_only: bool) -> HotelOut:
        return self._hotel_out(self.get_hotel(ref, published_only=published_only), published_only)

    # ================================================================== availability
    @staticmethod
    def _validate_stay(check_in: date, check_out: date, today: date) -> int:
        nights = (check_out - check_in).days
        if nights < 1 or nights > 30:
            raise AppError(422, "validation_error", "Stay must be between 1 and 30 nights")
        if check_in < today:
            raise AppError(422, "validation_error", "check_in cannot be in the past")
        return nights

    def _available(self, rt: RoomType, check_in: date, check_out: date) -> int:
        """Rooms free on every night of the stay (read-only; no rows are created)."""
        nights = (check_out - check_in).days
        rows = {
            r.day: r
            for r in self.db.scalars(
                select(RoomInventory).where(
                    RoomInventory.room_type_id == rt.id, RoomInventory.day >= check_in, RoomInventory.day < check_out
                )
            )
        }
        free = []
        for i in range(nights):
            r = rows.get(check_in + timedelta(days=i))
            free.append((r.total - r.booked) if r else rt.total_rooms)
        return min(free) if free else 0

    def availability(self, ref: str, check_in: date, check_out: date, guests: int, rooms: int) -> AvailabilityOut:
        hotel = self.get_hotel(ref, published_only=True)
        nights = self._validate_stay(check_in, check_out, today_local())
        options = []
        for rt in hotel.room_types:
            if not rt.is_active:
                continue
            free = self._available(rt, check_in, check_out)
            reason = None
            if guests > rooms * rt.capacity:
                reason = f"{rooms} room(s) of this type sleep at most {rooms * rt.capacity} guests"
            elif free < rooms:
                reason = "Sold out for these dates" if free == 0 else f"Only {free} room(s) left for these dates"
            options.append(
                RoomAvailability(
                    room_type=RoomTypeOut.model_validate(rt),
                    nights=nights,
                    available_rooms=free,
                    price_per_night_minor=rt.price_per_night_minor,
                    total_minor=rt.price_per_night_minor * nights * rooms,
                    can_book=reason is None,
                    reason=reason,
                )
            )
        return AvailabilityOut(
            hotel_id=hotel.id, check_in=check_in, check_out=check_out, guests=guests, rooms=rooms, options=options
        )

    # ================================================================== inventory locking
    def _lock_inventory(self, rt: RoomType, check_in: date, check_out: date) -> list[RoomInventory]:
        self.db.execute(
            text(
                "INSERT INTO room_inventory (room_type_id, day, total, booked) "
                "SELECT :rt, d::date, :total, 0 FROM generate_series(CAST(:first AS date), CAST(:last AS date), interval '1 day') d "
                "ON CONFLICT (room_type_id, day) DO NOTHING"
            ),
            {"rt": rt.id, "total": rt.total_rooms, "first": check_in, "last": check_out - timedelta(days=1)},
        )
        return list(
            self.db.scalars(
                select(RoomInventory)
                .where(
                    RoomInventory.room_type_id == rt.id, RoomInventory.day >= check_in, RoomInventory.day < check_out
                )
                .order_by(RoomInventory.day)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
        )

    def _reserve(self, rt: RoomType, check_in: date, check_out: date, rooms: int) -> None:
        rows = self._lock_inventory(rt, check_in, check_out)
        if any(r.booked + rooms > r.total for r in rows):
            raise AppError(409, "sold_out", "Not enough rooms are available for these dates")
        for r in rows:
            r.booked += rooms

    def _release(self, rt: RoomType, check_in: date, check_out: date, rooms: int) -> None:
        for r in self._lock_inventory(rt, check_in, check_out):
            r.booked = max(0, r.booked - rooms)

    # ================================================================== booking lifecycle
    def _own(self, user: User, booking_id: uuid.UUID, *, lock: bool = False) -> Booking:
        stmt = select(Booking).where(Booking.id == booking_id, Booking.user_id == user.id)
        if lock:
            stmt = stmt.with_for_update(of=Booking).execution_options(populate_existing=True)
        b = self.db.scalar(stmt)
        if b is None:
            raise not_found("Booking")
        return b

    def create(self, user: User, data: BookingCreate, key: str) -> tuple[BookingOut, bool]:
        """Returns (booking, replayed). The booking is created in `pending_payment` with the rooms HELD until paid
        or until the hold expires."""
        if not key or len(key) > 80:
            raise AppError(422, "idempotency_key_required", "An Idempotency-Key header (max 80 chars) is required")
        h = request_hash(data)
        existing = self.db.scalar(select(Booking).where(Booking.user_id == user.id, Booking.idempotency_key == key))
        if existing:
            return self._replay(existing, h)
        rt = self.db.get(RoomType, data.room_type_id)
        if (
            rt is None
            or not rt.is_active
            or rt.hotel.deleted_at is not None
            or not rt.hotel.is_published
            or not rt.hotel.destination.is_published
        ):
            raise AppError(422, "unknown_room", "Room type not found or not available for booking")
        nights = self._validate_stay(data.check_in, data.check_out, today_local())
        if data.guests > data.rooms * rt.capacity:
            raise AppError(
                422,
                "too_many_guests",
                f"{data.rooms} room(s) of this type sleep at most {data.rooms * rt.capacity} guests",
            )
        if data.itinerary_id is not None:
            it = self.db.scalar(
                select(Itinerary).where(
                    Itinerary.id == data.itinerary_id, Itinerary.user_id == user.id, Itinerary.deleted_at.is_(None)
                )
            )
            if it is None:
                raise AppError(422, "unknown_itinerary", "itinerary_id does not belong to you")
        try:
            self._reserve(rt, data.check_in, data.check_out, data.rooms)
            b = Booking(
                reference=new_reference(),
                user_id=user.id,
                hotel_id=rt.hotel_id,
                room_type_id=rt.id,
                itinerary_id=data.itinerary_id,
                check_in=data.check_in,
                check_out=data.check_out,
                nights=nights,
                rooms=data.rooms,
                guests=data.guests,
                guest_name=data.guest_name.strip(),
                guest_phone=data.guest_phone,
                total_minor=rt.price_per_night_minor * nights * data.rooms,
                currency=rt.currency,
                status="pending_payment",
                payment_status="unpaid",
                idempotency_key=key,
                request_hash=h,
                hold_expires_at=self._now() + timedelta(minutes=get_settings().booking_hold_minutes),
            )
            self.db.add(b)
            self.db.flush()
            self.db.commit()
        except IntegrityError:
            self.db.rollback()  # also undoes the inventory reservation of the losing request
            existing = self.db.scalar(select(Booking).where(Booking.user_id == user.id, Booking.idempotency_key == key))
            if existing is None:
                raise AppError(409, "conflict", "Could not create the booking; please retry") from None
            return self._replay(existing, h)
        return self.out(b), False

    def _replay(self, existing: Booking, h: str) -> tuple[BookingOut, bool]:
        if existing.request_hash != h:
            raise AppError(
                422, "idempotency_key_reuse", "This Idempotency-Key was already used with a different request"
            )
        return self.out(existing), True

    def pay(self, user: User, booking_id: uuid.UUID, method: str, key: str) -> BookingOut:
        if not key or len(key) > 80:
            raise AppError(422, "idempotency_key_required", "An Idempotency-Key header (max 80 chars) is required")
        b = self._own(user, booking_id, lock=True)
        prior = next((p for p in b.payments if p.kind == "charge" and p.idempotency_key == key), None)
        if prior is not None:
            if prior.status == "succeeded":
                return self.out(b)
            raise AppError(
                402, "payment_failed", prior.failure_reason or "The payment failed; start a new attempt with a new key"
            )
        if b.status == "confirmed":
            raise AppError(409, "already_paid", "This booking is already confirmed and paid")
        if b.status != "pending_payment":
            raise AppError(409, "not_payable", f"A {b.status} booking cannot be paid")
        if b.hold_expires_at and b.hold_expires_at <= self._now():
            self._expire(b)
            self.db.commit()
            raise AppError(409, "hold_expired", "The room hold expired; please book again")
        try:
            res = self.payments.charge(b.total_minor, b.currency, key, method, b.reference)
        except PaymentError as exc:
            self.db.add(
                Payment(
                    booking_id=b.id,
                    kind="charge",
                    provider=self.payments.name,
                    amount_minor=b.total_minor,
                    currency=b.currency,
                    status="failed",
                    idempotency_key=key,
                    failure_reason=str(exc)[:200],
                    simulated=True,
                )
            )
            self.db.commit()
            raise AppError(
                502, "payment_provider_error", "The payment provider could not process the payment. Try again."
            ) from exc
        self.db.add(
            Payment(
                booking_id=b.id,
                kind="charge",
                provider=res.provider,
                provider_ref=res.provider_ref,
                amount_minor=b.total_minor,
                currency=b.currency,
                status="succeeded" if res.succeeded else "failed",
                idempotency_key=key,
                failure_reason=res.failure_reason,
                simulated=res.simulated,
            )
        )
        if not res.succeeded:
            self.db.commit()
            raise AppError(402, "payment_failed", res.failure_reason or "The payment was declined")
        b.status, b.payment_status, b.confirmed_at, b.hold_expires_at = "confirmed", "paid", self._now(), None
        self.notifier.notify(
            b.user_id,
            "booking_confirmed",
            f"Booking {b.reference} confirmed",
            f"{b.hotel.name}, {b.check_in:%d %b} to {b.check_out:%d %b %Y} ({b.nights} night{'s' if b.nights != 1 else ''}). "
            f"Total {b.total_minor / 100:,.0f} {b.currency}.",
            f"booking:{b.id}:confirmed",
            {"booking_id": str(b.id)},
        )
        self.db.commit()
        return self.out(b)

    def cancel(self, actor: User, booking_id: uuid.UUID, reason: str | None, *, by_admin: bool = False) -> BookingOut:
        stmt = (
            select(Booking)
            .where(Booking.id == booking_id)
            .with_for_update(of=Booking)
            .execution_options(populate_existing=True)
        )
        b = self.db.scalar(stmt)
        if b is None or (not by_admin and b.user_id != actor.id):
            raise not_found("Booking")
        if b.status == "cancelled":
            return self.out(b)  # idempotent
        if b.status not in ("pending_payment", "confirmed"):
            raise AppError(409, "not_cancellable", f"A {b.status} booking cannot be cancelled")
        was_confirmed = b.status == "confirmed"
        self._release(b.room_type, b.check_in, b.check_out, b.rooms)
        b.status, b.cancelled_at, b.cancelled_by, b.cancel_reason = (
            "cancelled",
            self._now(),
            "admin" if by_admin else "traveler",
            (reason or None),
        )
        b.hold_expires_at = None
        body = f"Booking {b.reference} at {b.hotel.name} was cancelled."
        if was_confirmed:
            amount = refund_amount(b.total_minor, b.check_in, today_local(), by_admin)
            b.refund_amount_minor = amount
            if amount > 0:
                body += self._refund(b, amount, "cancel")
            else:
                body += " This cancellation is outside the free-cancellation window, so no refund is due."
        self.notifier.notify(
            b.user_id,
            "booking_cancelled",
            f"Booking {b.reference} cancelled",
            body,
            f"booking:{b.id}:cancelled",
            {"booking_id": str(b.id)},
        )
        self.db.commit()
        return self.out(b)

    def _refund(self, b: Booking, amount: int, attempt: str) -> str:
        charge = next((p for p in b.payments if p.kind == "charge" and p.status == "succeeded"), None)
        key = f"refund:{b.id}:{attempt}"
        try:
            res = self.payments.refund(amount, b.currency, key, charge.provider_ref if charge else None, b.reference)
        except PaymentError:
            res = None
        ok = bool(res and res.succeeded)
        self.db.add(
            Payment(
                booking_id=b.id,
                kind="refund",
                provider=self.payments.name,
                provider_ref=res.provider_ref if res else None,
                amount_minor=amount,
                currency=b.currency,
                status="succeeded" if ok else "failed",
                idempotency_key=key,
                failure_reason=None if ok else "refund could not be processed",
                simulated=True,
            )
        )
        if ok:
            b.payment_status = "refunded"
            return f" A refund of {amount / 100:,.0f} {b.currency} was issued (development payment simulator: no real money moved)."
        b.payment_status = "refund_pending"
        self.notifier.notify(
            b.user_id,
            "booking_refund_failed",
            f"Refund pending for {b.reference}",
            "We could not process your refund automatically; our team has been notified and will retry.",
            f"booking:{b.id}:refund_failed:{attempt}",
            {"booking_id": str(b.id)},
        )
        return " The refund could not be processed automatically and is pending."

    def retry_refund(self, booking_id: uuid.UUID) -> BookingOut:
        b = self.db.scalar(
            select(Booking)
            .where(Booking.id == booking_id)
            .with_for_update(of=Booking)
            .execution_options(populate_existing=True)
        )
        if b is None:
            raise not_found("Booking")
        if b.payment_status != "refund_pending" or not b.refund_amount_minor:
            raise AppError(409, "no_pending_refund", "This booking has no pending refund")
        attempts = sum(1 for p in b.payments if p.kind == "refund")
        self._refund(b, b.refund_amount_minor, f"retry{attempts}")
        self.db.commit()
        return self.out(b)

    def _expire(self, b: Booking) -> None:
        self._release(b.room_type, b.check_in, b.check_out, b.rooms)
        b.status, b.hold_expires_at = "expired", None
        self.notifier.notify(
            b.user_id,
            "booking_cancelled",
            f"Booking {b.reference} expired",
            "The room hold expired before payment, so the rooms were released.",
            f"booking:{b.id}:expired",
            {"booking_id": str(b.id)},
        )

    def expire_holds(self, limit: int = 100) -> int:
        """Background job: release rooms held by unpaid bookings. Safe to run concurrently (SKIP LOCKED)."""
        rows = self.db.scalars(
            select(Booking)
            .where(Booking.status == "pending_payment", Booking.hold_expires_at <= self._now())
            .order_by(Booking.hold_expires_at)
            .limit(limit)
            .with_for_update(skip_locked=True, of=Booking)
            .execution_options(populate_existing=True)
        ).all()
        for b in rows:
            self._expire(b)
        self.db.commit()
        return len(rows)

    # ================================================================== reading
    def out(self, b: Booking, *, admin: bool = False) -> BookingOut:
        payments = list(
            self.db.scalars(select(Payment).where(Payment.booking_id == b.id).order_by(Payment.created_at, Payment.id))
        )
        refundable = None
        if b.status == "confirmed":
            refundable = refund_amount(b.total_minor, b.check_in, today_local())
        note = (
            "Development payment simulator: no real money was charged." if any(p.simulated for p in payments) else None
        )
        return BookingOut(
            id=b.id,
            reference=b.reference,
            status=b.status,
            payment_status=b.payment_status,
            hotel_id=b.hotel_id,
            hotel_name=b.hotel.name,
            hotel_slug=b.hotel.slug,
            destination_name=b.hotel.destination.name,
            room_type_id=b.room_type_id,
            room_type_name=b.room_type.name,
            check_in=b.check_in,
            check_out=b.check_out,
            nights=b.nights,
            rooms=b.rooms,
            guests=b.guests,
            guest_name=b.guest_name,
            guest_phone=b.guest_phone,
            total_minor=b.total_minor,
            currency=b.currency,
            hold_expires_at=b.hold_expires_at,
            confirmed_at=b.confirmed_at,
            cancelled_at=b.cancelled_at,
            cancelled_by=b.cancelled_by,
            cancel_reason=b.cancel_reason,
            refund_amount_minor=b.refund_amount_minor,
            itinerary_id=b.itinerary_id,
            created_at=b.created_at,
            payments=[PaymentOut.model_validate(p) for p in payments],
            refund_if_cancelled_now_minor=refundable,
            cancellation_policy=POLICY,
            payment_note=note,
            user_email=self.db.get(User, b.user_id).email if admin else None,
        )

    def list(self, user: User, status: str | None, page: int, page_size: int):
        stmt = select(Booking).where(Booking.user_id == user.id)
        if status:
            stmt = stmt.where(Booking.status == status)
        total = self.db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        rows = self.db.scalars(
            stmt.order_by(Booking.created_at.desc(), Booking.id).offset((page - 1) * page_size).limit(page_size)
        ).all()
        return [self.out(b) for b in rows], total

    def get(self, user: User, booking_id: uuid.UUID) -> BookingOut:
        return self.out(self._own(user, booking_id))

    # ================================================================== admin
    def admin_list(self, status: str | None, q: str | None, page: int, page_size: int):
        stmt = select(Booking)
        if status:
            stmt = stmt.where(Booking.status == status)
        if q:
            like = f"%{q}%"
            stmt = stmt.where(Booking.reference.ilike(like) | Booking.guest_name.ilike(like))
        total = self.db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        rows = self.db.scalars(
            stmt.order_by(Booking.created_at.desc(), Booking.id).offset((page - 1) * page_size).limit(page_size)
        ).all()
        return [self.out(b, admin=True) for b in rows], total

    def create_hotel(self, actor: User, data: HotelIn) -> HotelOut:
        if self.db.get(Destination, data.destination_id) is None:
            raise AppError(422, "unknown_destination", "destination_id does not exist")
        h = Hotel(
            **data.model_dump(),
            slug=unique_slug(data.name, lambda s: self.db.scalar(select(Hotel.id).where(Hotel.slug == s)) is not None),
            source="admin",
        )
        self.db.add(h)
        self.db.commit()
        self.db.refresh(h)
        return self._hotel_out(h, published_only=False)

    def update_hotel(self, actor: User, hotel_id: uuid.UUID, data: HotelUpdate) -> HotelOut:
        h = self.get_hotel(str(hotel_id), published_only=False)
        changes = data.model_dump(exclude_unset=True)
        for k in ("name", "latitude", "longitude", "is_published"):
            if k in changes and changes[k] is None:
                raise AppError(422, "validation_error", f"{k} cannot be null")
        for k, v in changes.items():
            setattr(h, k, v)
        self.db.commit()
        return self._hotel_out(h, published_only=False)

    def delete_hotel(self, actor: User, hotel_id: uuid.UUID) -> None:
        h = self.get_hotel(str(hotel_id), published_only=False)
        active = self.db.scalar(
            select(func.count())
            .select_from(Booking)
            .where(
                Booking.hotel_id == h.id,
                Booking.status.in_(("pending_payment", "confirmed")),
                Booking.check_out >= today_local(),
            )
        )
        if active:
            raise AppError(
                409, "hotel_has_bookings", f"{active} active booking(s) exist for this hotel; cancel them first"
            )
        h.deleted_at, h.is_published = self._now(), False
        self.db.commit()

    def create_room(self, actor: User, hotel_id: uuid.UUID, data: RoomTypeIn) -> RoomTypeOut:
        h = self.get_hotel(str(hotel_id), published_only=False)
        rt = RoomType(hotel_id=h.id, **data.model_dump())
        self.db.add(rt)
        self.db.commit()
        return RoomTypeOut.model_validate(rt)

    def update_room(self, actor: User, room_id: uuid.UUID, data: RoomTypeUpdate) -> RoomTypeOut:
        rt = self.db.get(RoomType, room_id)
        if rt is None:
            raise not_found("Room type")
        for k, v in data.model_dump(exclude_unset=True).items():
            if v is None and k not in ("description",):
                raise AppError(422, "validation_error", f"{k} cannot be null")
            setattr(rt, k, v)
        self.db.commit()
        return RoomTypeOut.model_validate(rt)

    def override_inventory(self, actor: User, room_id: uuid.UUID, data: InventoryOverride) -> dict:
        rt = self.db.get(RoomType, room_id)
        if rt is None:
            raise not_found("Room type")
        end_excl = data.end + timedelta(days=1)
        rows = self._lock_inventory(rt, data.start, end_excl)
        if any(r.booked > data.total for r in rows):
            worst = max(r.booked for r in rows)
            raise AppError(
                409,
                "inventory_below_booked",
                f"Some nights already have {worst} room(s) booked; cancel bookings before lowering inventory below that",
            )
        for r in rows:
            r.total = data.total
        self.db.commit()
        return {"nights": len(rows), "total": data.total}

    def analytics(self) -> dict:
        today = today_local()
        by_status = dict(self.db.execute(select(Booking.status, func.count()).group_by(Booking.status)).all())
        revenue = (
            self.db.scalar(
                select(func.coalesce(func.sum(Booking.total_minor), 0)).where(
                    Booking.status == "confirmed", Booking.payment_status == "paid"
                )
            )
            or 0
        )
        refunded = (
            self.db.scalar(
                select(func.coalesce(func.sum(Payment.amount_minor), 0)).where(
                    Payment.kind == "refund", Payment.status == "succeeded"
                )
            )
            or 0
        )
        monthly = [
            {"month": m.strftime("%Y-%m"), "bookings": n, "revenue_minor": int(r)}
            for m, n, r in self.db.execute(
                select(
                    func.date_trunc("month", Booking.created_at).label("month"),
                    func.count(),
                    func.coalesce(func.sum(Booking.total_minor).filter(Booking.status == "confirmed"), 0),
                )
                .group_by(text("month"))
                .order_by(text("month"))
                .limit(12)
            )
        ]
        top = [
            {"destination": d, "bookings": n}
            for d, n in self.db.execute(
                select(Destination.name, func.count(Booking.id))
                .join(Hotel, Hotel.destination_id == Destination.id)
                .join(Booking, Booking.hotel_id == Hotel.id)
                .where(Booking.status == "confirmed")
                .group_by(Destination.name)
                .order_by(func.count(Booking.id).desc(), Destination.name)
                .limit(5)
            )
        ]
        booked_nights = (
            self.db.scalar(select(func.coalesce(func.sum(RoomInventory.booked), 0)).where(RoomInventory.day >= today))
            or 0
        )
        total_nights = (
            self.db.scalar(select(func.coalesce(func.sum(RoomInventory.total), 0)).where(RoomInventory.day >= today))
            or 0
        )
        users = self.db.scalar(select(func.count()).select_from(User)) or 0
        itineraries = (
            self.db.scalar(select(func.count()).select_from(Itinerary).where(Itinerary.deleted_at.is_(None))) or 0
        )
        return {
            "bookings_by_status": by_status,
            "confirmed_revenue_minor": int(revenue),
            "refunded_minor": int(refunded),
            "monthly": monthly,
            "top_destinations": top,
            "future_occupancy_pct": round(100 * booked_nights / total_nights, 1) if total_nights else None,
            "users": users,
            "itineraries": itineraries,
            "hotels": self.db.scalar(select(func.count()).select_from(Hotel).where(Hotel.deleted_at.is_(None))) or 0,
            "currency": "INR",
            "notes": [
                "All figures are computed from the database. Revenue counts confirmed, paid bookings (development payments are simulated, so no real money is involved)."
            ],
        }
