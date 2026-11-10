import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, Timestamps, UUIDPk

BOOKING_STATUSES = ("pending_payment", "confirmed", "cancelled", "expired", "failed")
PAYMENT_STATUSES = ("unpaid", "paid", "refund_pending", "refunded", "failed")


def _in(col: str, values: tuple[str, ...]) -> str:
    return f"{col} IN ({', '.join(repr(v) for v in values)})"


class Hotel(UUIDPk, Timestamps, Base):
    __tablename__ = "hotels"
    __table_args__ = (
        CheckConstraint("latitude BETWEEN -90 AND 90", name="ck_hotels_lat"),
        CheckConstraint("longitude BETWEEN -180 AND 180", name="ck_hotels_lng"),
        CheckConstraint("star_rating IS NULL OR star_rating BETWEEN 1 AND 5", name="ck_hotels_stars"),
    )

    destination_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("destinations.id", ondelete="RESTRICT"), index=True
    )
    slug: Mapped[str] = mapped_column(String(120), unique=True)
    name: Mapped[str] = mapped_column(String(140), index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    address: Mapped[str | None] = mapped_column(String(240))
    latitude: Mapped[float] = mapped_column(Numeric(9, 6))
    longitude: Mapped[float] = mapped_column(Numeric(9, 6))
    star_rating: Mapped[int | None] = mapped_column(Integer)
    amenities: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]")
    images: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]")
    is_published: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    source: Mapped[str] = mapped_column(String(16), default="admin", server_default="admin")
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    room_types: Mapped[list["RoomType"]] = relationship(
        back_populates="hotel", order_by="RoomType.price_per_night_minor"
    )
    destination = relationship("Destination", lazy="joined")


class RoomType(UUIDPk, Timestamps, Base):
    __tablename__ = "room_types"
    __table_args__ = (
        CheckConstraint("capacity BETWEEN 1 AND 12", name="ck_rooms_capacity"),
        CheckConstraint("price_per_night_minor >= 0", name="ck_rooms_price"),
        CheckConstraint("total_rooms >= 0", name="ck_rooms_total"),
    )

    hotel_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("hotels.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(Text, default="")
    capacity: Mapped[int] = mapped_column(Integer)  # guests per room
    price_per_night_minor: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3), default="INR", server_default="INR")
    total_rooms: Mapped[int] = mapped_column(Integer)  # default nightly inventory
    amenities: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")

    hotel: Mapped[Hotel] = relationship(back_populates="room_types")


class RoomInventory(Base):
    """Per-night inventory. Rows are created lazily from `room_types.total_rooms`; admins can override a night.
    `booked <= total` is enforced by the database, so overbooking is impossible even under races."""

    __tablename__ = "room_inventory"
    __table_args__ = (
        CheckConstraint("total >= 0", name="ck_inventory_total"),
        CheckConstraint("booked >= 0", name="ck_inventory_booked"),
        CheckConstraint("booked <= total", name="ck_inventory_not_overbooked"),
    )

    room_type_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("room_types.id", ondelete="CASCADE"), primary_key=True
    )
    day: Mapped[date] = mapped_column(Date, primary_key=True)
    total: Mapped[int] = mapped_column(Integer)
    booked: Mapped[int] = mapped_column(Integer, default=0)


class Booking(UUIDPk, Timestamps, Base):
    __tablename__ = "bookings"
    __table_args__ = (
        CheckConstraint(_in("status", BOOKING_STATUSES), name="ck_bookings_status"),
        CheckConstraint(_in("payment_status", PAYMENT_STATUSES), name="ck_bookings_payment_status"),
        CheckConstraint("check_out > check_in", name="ck_bookings_dates"),
        CheckConstraint("rooms BETWEEN 1 AND 10", name="ck_bookings_rooms"),
        CheckConstraint("guests >= 1", name="ck_bookings_guests"),
        UniqueConstraint("user_id", "idempotency_key", name="uq_bookings_user_idem"),
        Index("ix_bookings_user_created", "user_id", "created_at"),
        Index("ix_bookings_hold", "status", "hold_expires_at"),
    )

    reference: Mapped[str] = mapped_column(String(16), unique=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    hotel_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("hotels.id", ondelete="RESTRICT"))
    room_type_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("room_types.id", ondelete="RESTRICT")
    )
    itinerary_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("itineraries.id", ondelete="SET NULL")
    )
    check_in: Mapped[date] = mapped_column(Date)
    check_out: Mapped[date] = mapped_column(Date)
    nights: Mapped[int] = mapped_column(Integer)
    rooms: Mapped[int] = mapped_column(Integer)
    guests: Mapped[int] = mapped_column(Integer)
    guest_name: Mapped[str] = mapped_column(String(120))
    guest_phone: Mapped[str | None] = mapped_column(String(32))
    total_minor: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3), default="INR")
    status: Mapped[str] = mapped_column(String(16), default="pending_payment")
    payment_status: Mapped[str] = mapped_column(String(16), default="unpaid")
    idempotency_key: Mapped[str] = mapped_column(String(80))
    request_hash: Mapped[str] = mapped_column(String(64))
    hold_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_by: Mapped[str | None] = mapped_column(String(16))  # traveler | admin | system
    cancel_reason: Mapped[str | None] = mapped_column(String(300))
    refund_amount_minor: Mapped[int | None] = mapped_column(Integer)

    hotel: Mapped[Hotel] = relationship(lazy="joined")
    room_type: Mapped[RoomType] = relationship(lazy="joined")
    payments: Mapped[list["Payment"]] = relationship(back_populates="booking", order_by="Payment.created_at")


class Payment(UUIDPk, Base):
    """Money movements. The `development` provider is a labelled simulator: no real charge is ever made.
    Card numbers are never accepted or stored; only an opaque payment-method token."""

    __tablename__ = "payments"
    __table_args__ = (
        CheckConstraint("kind IN ('charge', 'refund')", name="ck_payments_kind"),
        CheckConstraint("status IN ('succeeded', 'failed')", name="ck_payments_status"),
        UniqueConstraint("booking_id", "idempotency_key", name="uq_payments_booking_idem"),
    )

    booking_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("bookings.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(10))
    provider: Mapped[str] = mapped_column(String(24))
    provider_ref: Mapped[str | None] = mapped_column(String(80))
    amount_minor: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3), default="INR")
    status: Mapped[str] = mapped_column(String(10))
    idempotency_key: Mapped[str] = mapped_column(String(80))
    failure_reason: Mapped[str | None] = mapped_column(String(200))
    simulated: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    booking: Mapped[Booking] = relationship(back_populates="payments")


class Notification(UUIDPk, Base):
    __tablename__ = "notifications"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_notifications_idem"),
        Index("ix_notifications_user", "user_id", "read_at", "created_at"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    type: Mapped[str] = mapped_column(String(32))
    title: Mapped[str] = mapped_column(String(160))
    body: Mapped[str] = mapped_column(String(600))
    data: Mapped[dict] = mapped_column(JSONB, default=dict)
    idempotency_key: Mapped[str] = mapped_column(String(160))
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class NotificationDelivery(UUIDPk, Base):
    """External-channel delivery attempts (email now; SMS needs a configured provider). In-app delivery is the
    notification row itself."""

    __tablename__ = "notification_deliveries"
    __table_args__ = (
        CheckConstraint("channel IN ('email', 'sms')", name="ck_deliveries_channel"),
        CheckConstraint("status IN ('pending', 'sent', 'skipped', 'failed')", name="ck_deliveries_status"),
        UniqueConstraint("notification_id", "channel", name="uq_delivery_channel"),
    )

    notification_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("notifications.id", ondelete="CASCADE"), index=True
    )
    channel: Mapped[str] = mapped_column(String(8))
    status: Mapped[str] = mapped_column(String(10), default="pending")
    provider: Mapped[str | None] = mapped_column(String(24))
    detail: Mapped[str | None] = mapped_column(String(300))
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AssistantConversation(UUIDPk, Timestamps, Base):
    __tablename__ = "assistant_conversations"
    __table_args__ = (
        CheckConstraint("language IN ('en', 'hi')", name="ck_conv_language"),
        Index("ix_conv_user", "user_id", "updated_at"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(120), default="New conversation")
    language: Mapped[str] = mapped_column(String(2), default="en")
    state: Mapped[dict] = mapped_column(
        JSONB, default=dict
    )  # context: last destination/itinerary, pending slots/actions

    messages: Mapped[list["AssistantMessage"]] = relationship(
        back_populates="conversation", order_by="AssistantMessage.created_at", cascade="all, delete-orphan"
    )


class AssistantMessage(UUIDPk, Base):
    __tablename__ = "assistant_messages"
    __table_args__ = (
        CheckConstraint("role IN ('user', 'assistant')", name="ck_msg_role"),
        CheckConstraint("input_mode IN ('text', 'voice')", name="ck_msg_mode"),
        Index("ix_msg_conv", "conversation_id", "created_at"),
    )

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("assistant_conversations.id", ondelete="CASCADE")
    )
    role: Mapped[str] = mapped_column(String(10))
    content: Mapped[str] = mapped_column(Text)
    language: Mapped[str] = mapped_column(String(2))
    input_mode: Mapped[str] = mapped_column(String(6), default="text")
    actions: Mapped[list] = mapped_column(JSONB, default=list)
    cards: Mapped[list] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    conversation: Mapped[AssistantConversation] = relationship(back_populates="messages")
