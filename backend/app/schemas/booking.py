import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.timeutil import today_local
from app.schemas.catalog import Lat, Lng, _images


class RoomTypeIn(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    description: str = Field(default="", max_length=2000)
    capacity: int = Field(ge=1, le=12)
    price_per_night_minor: int = Field(ge=0, le=10**8)
    total_rooms: int = Field(ge=0, le=1000)
    amenities: list[str] = Field(default_factory=list, max_length=30)
    is_active: bool = True


class RoomTypeUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=100)
    description: str | None = Field(default=None, max_length=2000)
    capacity: int | None = Field(default=None, ge=1, le=12)
    price_per_night_minor: int | None = Field(default=None, ge=0, le=10**8)
    total_rooms: int | None = Field(default=None, ge=0, le=1000)
    amenities: list[str] | None = Field(default=None, max_length=30)
    is_active: bool | None = None


class RoomTypeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    hotel_id: uuid.UUID
    name: str
    description: str
    capacity: int
    price_per_night_minor: int
    currency: str
    total_rooms: int
    amenities: list
    is_active: bool


class HotelIn(BaseModel):
    destination_id: uuid.UUID
    name: str = Field(min_length=2, max_length=140)
    description: str = Field(default="", max_length=5000)
    address: str | None = Field(default=None, max_length=240)
    latitude: Lat
    longitude: Lng
    star_rating: int | None = Field(default=None, ge=1, le=5)
    amenities: list[str] = Field(default_factory=list, max_length=30)
    images: list[str] = Field(default_factory=list)
    is_published: bool = False

    _img = field_validator("images")(_images)


class HotelUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=140)
    description: str | None = Field(default=None, max_length=5000)
    address: str | None = Field(default=None, max_length=240)
    latitude: Lat | None = None
    longitude: Lng | None = None
    star_rating: int | None = Field(default=None, ge=1, le=5)
    amenities: list[str] | None = Field(default=None, max_length=30)
    images: list[str] | None = None
    is_published: bool | None = None

    @field_validator("images")
    @classmethod
    def _img(cls, v):
        return None if v is None else _images(v)


class HotelOut(BaseModel):
    id: uuid.UUID
    slug: str
    name: str
    description: str
    address: str | None
    latitude: float
    longitude: float
    star_rating: int | None
    amenities: list
    images: list
    is_published: bool
    source: str
    destination_id: uuid.UUID
    destination_name: str
    room_types: list[RoomTypeOut]
    from_price_minor: int | None
    currency: str = "INR"


class InventoryOverride(BaseModel):
    start: date
    end: date
    total: int = Field(ge=0, le=1000)

    @model_validator(mode="after")
    def _range(self):
        if self.end < self.start or (self.end - self.start).days > 366:
            raise ValueError("end must be on or after start, within 366 days")
        return self


class RoomAvailability(BaseModel):
    room_type: RoomTypeOut
    nights: int
    available_rooms: int  # minimum over the nights
    price_per_night_minor: int
    total_minor: int  # for the requested number of rooms
    can_book: bool
    reason: str | None = None


class AvailabilityOut(BaseModel):
    hotel_id: uuid.UUID
    check_in: date
    check_out: date
    guests: int
    rooms: int
    options: list[RoomAvailability]


class BookingCreate(BaseModel):
    room_type_id: uuid.UUID
    check_in: date
    check_out: date
    rooms: int = Field(default=1, ge=1, le=10)
    guests: int = Field(default=1, ge=1, le=60)
    guest_name: str = Field(min_length=2, max_length=120)
    guest_phone: str | None = Field(default=None, max_length=32)
    itinerary_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def _dates(self):
        n = (self.check_out - self.check_in).days
        if n < 1:
            raise ValueError("check_out must be after check_in")
        if n > 30:
            raise ValueError("A stay can be at most 30 nights")
        if self.check_in < today_local():
            raise ValueError("check_in cannot be in the past")
        return self


class PayRequest(BaseModel):
    payment_method: str = Field(
        min_length=3, max_length=40, pattern=r"^[a-z0-9_]+$"
    )  # opaque token; card numbers are rejected


class CancelRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=300)


class PaymentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    kind: str
    provider: str
    amount_minor: int
    currency: str
    status: str
    failure_reason: str | None
    simulated: bool
    created_at: datetime


class BookingOut(BaseModel):
    id: uuid.UUID
    reference: str
    status: str
    payment_status: str
    hotel_id: uuid.UUID
    hotel_name: str
    hotel_slug: str
    destination_name: str
    room_type_id: uuid.UUID
    room_type_name: str
    check_in: date
    check_out: date
    nights: int
    rooms: int
    guests: int
    guest_name: str
    guest_phone: str | None
    total_minor: int
    currency: str
    hold_expires_at: datetime | None
    confirmed_at: datetime | None
    cancelled_at: datetime | None
    cancelled_by: str | None
    cancel_reason: str | None
    refund_amount_minor: int | None
    itinerary_id: uuid.UUID | None
    created_at: datetime
    payments: list[PaymentOut]
    refund_if_cancelled_now_minor: int | None = None
    cancellation_policy: str
    payment_note: str | None = None
    user_email: str | None = None  # admin views only


BookingStatus = Literal["pending_payment", "confirmed", "cancelled", "expired", "failed"]
