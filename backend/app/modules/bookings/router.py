import uuid
from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Header, Query, Response

from app.api.deps import AdminUser, CurrentUser, DbSession
from app.core.errors import AppError
from app.modules.bookings.service import BookingService
from app.schemas.booking import (
    AvailabilityOut,
    BookingCreate,
    BookingOut,
    BookingStatus,
    CancelRequest,
    HotelIn,
    HotelOut,
    HotelUpdate,
    InventoryOverride,
    PayRequest,
    RoomTypeIn,
    RoomTypeOut,
    RoomTypeUpdate,
)
from app.schemas.user import Page

Idem = Annotated[str | None, Header(alias="Idempotency-Key")]
PageNo = Annotated[int, Query(ge=1)]
PageSize = Annotated[int, Query(ge=1, le=100)]

public = APIRouter(tags=["hotels"])
bookings = APIRouter(tags=["bookings"])
admin = APIRouter(prefix="/admin", tags=["bookings-admin"])


# ------------------------------------------------------------------ public hotels
@public.get("/hotels", response_model=Page[HotelOut])
def list_hotels(
    db: DbSession,
    q: Annotated[str | None, Query(max_length=100)] = None,
    destination: Annotated[str | None, Query(max_length=100)] = None,
    min_stars: Annotated[int | None, Query(ge=1, le=5)] = None,
    max_price_minor: Annotated[int | None, Query(ge=0)] = None,
    sort: Literal["name", "stars", "price"] = "name",
    page: PageNo = 1,
    page_size: PageSize = 12,
):
    items, total = BookingService(db).list_hotels(
        published_only=True,
        q=q,
        destination=destination,
        min_stars=min_stars,
        max_price_minor=max_price_minor,
        sort=sort,
        page=page,
        page_size=page_size,
    )
    return Page(items=items, total=total, page=page, page_size=page_size)


@public.get("/hotels/{ref}", response_model=HotelOut)
def get_hotel(ref: str, db: DbSession):
    return BookingService(db).hotel_out(ref, published_only=True)


@public.get("/hotels/{ref}/availability", response_model=AvailabilityOut)
def availability(
    ref: str,
    db: DbSession,
    check_in: date,
    check_out: date,
    guests: Annotated[int, Query(ge=1, le=60)] = 1,
    rooms: Annotated[int, Query(ge=1, le=10)] = 1,
):
    return BookingService(db).availability(ref, check_in, check_out, guests, rooms)


# ------------------------------------------------------------------ traveler bookings
@bookings.post("/bookings", response_model=BookingOut, status_code=201)
def create_booking(
    data: BookingCreate, user: CurrentUser, db: DbSession, response: Response, idempotency_key: Idem = None
):
    booking, replayed = BookingService(db).create(user, data, idempotency_key or "")
    if replayed:
        response.status_code = 200
        response.headers["Idempotent-Replayed"] = "true"
    return booking


@bookings.get("/bookings", response_model=Page[BookingOut])
def list_bookings(
    user: CurrentUser, db: DbSession, status: BookingStatus | None = None, page: PageNo = 1, page_size: PageSize = 20
):
    items, total = BookingService(db).list(user, status, page, page_size)
    return Page(items=items, total=total, page=page, page_size=page_size)


@bookings.get("/bookings/{booking_id}", response_model=BookingOut)
def get_booking(booking_id: uuid.UUID, user: CurrentUser, db: DbSession):
    return BookingService(db).get(user, booking_id)


@bookings.post("/bookings/{booking_id}/pay", response_model=BookingOut)
def pay(booking_id: uuid.UUID, data: PayRequest, user: CurrentUser, db: DbSession, idempotency_key: Idem = None):
    return BookingService(db).pay(user, booking_id, data.payment_method, idempotency_key or "")


@bookings.post("/bookings/{booking_id}/cancel", response_model=BookingOut)
def cancel(booking_id: uuid.UUID, data: CancelRequest, user: CurrentUser, db: DbSession):
    return BookingService(db).cancel(user, booking_id, data.reason)


# ------------------------------------------------------------------ admin
@admin.get("/hotels", response_model=Page[HotelOut])
def admin_hotels(
    _: AdminUser,
    db: DbSession,
    q: Annotated[str | None, Query(max_length=100)] = None,
    page: PageNo = 1,
    page_size: PageSize = 20,
):
    items, total = BookingService(db).list_hotels(
        published_only=False,
        q=q,
        destination=None,
        min_stars=None,
        max_price_minor=None,
        sort="name",
        page=page,
        page_size=page_size,
    )
    return Page(items=items, total=total, page=page, page_size=page_size)


@admin.post("/hotels", response_model=HotelOut, status_code=201)
def admin_create_hotel(data: HotelIn, actor: AdminUser, db: DbSession):
    return BookingService(db).create_hotel(actor, data)


@admin.patch("/hotels/{hotel_id}", response_model=HotelOut)
def admin_update_hotel(hotel_id: uuid.UUID, data: HotelUpdate, actor: AdminUser, db: DbSession):
    return BookingService(db).update_hotel(actor, hotel_id, data)


@admin.delete("/hotels/{hotel_id}", status_code=204)
def admin_delete_hotel(hotel_id: uuid.UUID, actor: AdminUser, db: DbSession):
    BookingService(db).delete_hotel(actor, hotel_id)


@admin.post("/hotels/{hotel_id}/rooms", response_model=RoomTypeOut, status_code=201)
def admin_create_room(hotel_id: uuid.UUID, data: RoomTypeIn, actor: AdminUser, db: DbSession):
    return BookingService(db).create_room(actor, hotel_id, data)


@admin.patch("/rooms/{room_id}", response_model=RoomTypeOut)
def admin_update_room(room_id: uuid.UUID, data: RoomTypeUpdate, actor: AdminUser, db: DbSession):
    return BookingService(db).update_room(actor, room_id, data)


@admin.put("/rooms/{room_id}/inventory")
def admin_inventory(room_id: uuid.UUID, data: InventoryOverride, actor: AdminUser, db: DbSession):
    return BookingService(db).override_inventory(actor, room_id, data)


@admin.get("/bookings", response_model=Page[BookingOut])
def admin_bookings(
    _: AdminUser,
    db: DbSession,
    status: BookingStatus | None = None,
    q: Annotated[str | None, Query(max_length=60)] = None,
    page: PageNo = 1,
    page_size: PageSize = 20,
):
    items, total = BookingService(db).admin_list(status, q, page, page_size)
    return Page(items=items, total=total, page=page, page_size=page_size)


@admin.post("/bookings/{booking_id}/cancel", response_model=BookingOut)
def admin_cancel(booking_id: uuid.UUID, data: CancelRequest, actor: AdminUser, db: DbSession):
    return BookingService(db).cancel(actor, booking_id, data.reason, by_admin=True)


@admin.post("/bookings/{booking_id}/retry-refund", response_model=BookingOut)
def admin_retry_refund(booking_id: uuid.UUID, _: AdminUser, db: DbSession):
    return BookingService(db).retry_refund(booking_id)


@admin.get("/analytics")
def admin_analytics(_: AdminUser, db: DbSession) -> dict:
    return BookingService(db).analytics()


__all__ = ["AppError"]
