import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, Timestamps, UUIDPk


class Itinerary(UUIDPk, Timestamps, Base):
    __tablename__ = "itineraries"
    __table_args__ = (
        CheckConstraint("days BETWEEN 1 AND 14", name="ck_itineraries_days"),
        CheckConstraint("traveler_count BETWEEN 1 AND 20", name="ck_itineraries_travelers"),
        CheckConstraint("budget_total_minor IS NULL OR budget_total_minor >= 0", name="ck_itineraries_budget"),
        CheckConstraint("status IN ('draft', 'saved')", name="ck_itineraries_status"),
        Index("ix_itineraries_user", "user_id", "deleted_at"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    destination_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("destinations.id", ondelete="RESTRICT")
    )
    title: Mapped[str] = mapped_column(String(160))
    status: Mapped[str] = mapped_column(String(10), default="draft", server_default="draft")
    start_date: Mapped[date | None] = mapped_column(Date)
    days: Mapped[int] = mapped_column(Integer)
    traveler_count: Mapped[int] = mapped_column(Integer, default=1)
    budget_total_minor: Mapped[int | None] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3), default="INR", server_default="INR")
    interests: Mapped[list] = mapped_column(JSONB, default=list)
    travel_style: Mapped[str | None] = mapped_column(String(20))
    accommodation_preference: Mapped[str | None] = mapped_column(String(20))
    start_location: Mapped[dict | None] = mapped_column(JSONB)  # {"name":..., "lat":..., "lng":...}
    generation_source: Mapped[str] = mapped_column(String(32))  # llm | deterministic_fallback | manual
    generation_info: Mapped[dict] = mapped_column(JSONB, default=dict)  # steps, llm provider/model, notes, dropped
    current_version: Mapped[int] = mapped_column(Integer, default=1)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    activities: Mapped[list["ItineraryActivity"]] = relationship(
        back_populates="itinerary",
        cascade="all, delete-orphan",
        order_by="ItineraryActivity.day_number, ItineraryActivity.position",
    )
    versions: Mapped[list["ItineraryVersion"]] = relationship(back_populates="itinerary", cascade="all, delete-orphan")


class ItineraryActivity(UUIDPk, Timestamps, Base):
    __tablename__ = "itinerary_activities"
    __table_args__ = (
        CheckConstraint("day_number >= 1", name="ck_activities_day"),
        CheckConstraint("duration_min BETWEEN 5 AND 1440", name="ck_activities_duration"),
        CheckConstraint("hours_status IN ('verified_open', 'verified_closed', 'unknown')", name="ck_activities_hours"),
        Index("ix_activities_itinerary", "itinerary_id", "day_number", "position"),
    )

    itinerary_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("itineraries.id", ondelete="CASCADE")
    )
    attraction_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("attractions.id", ondelete="RESTRICT")
    )
    day_number: Mapped[int] = mapped_column(Integer)
    position: Mapped[int] = mapped_column(Integer)
    start_min: Mapped[int] = mapped_column(Integer)  # minutes from midnight
    duration_min: Mapped[int] = mapped_column(Integer)
    travel_min: Mapped[int] = mapped_column(Integer, default=0)  # ESTIMATE from the previous stop
    travel_m: Mapped[int] = mapped_column(Integer, default=0)  # ESTIMATE
    wait_min: Mapped[int] = mapped_column(Integer, default=0)
    cost_minor: Mapped[int | None] = mapped_column(Integer)  # per person; null = unknown
    hours_status: Mapped[str] = mapped_column(String(16), default="unknown")
    source: Mapped[str] = mapped_column(String(16), default="generated")  # generated | user
    score: Mapped[float | None] = mapped_column(Float)
    explanation: Mapped[dict] = mapped_column(JSONB, default=dict)  # reasons, notes, llm rationale
    notes: Mapped[str | None] = mapped_column(Text)
    locked: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")   # required: never dropped

    itinerary: Mapped[Itinerary] = relationship(back_populates="activities")
    attraction = relationship("Attraction", lazy="joined")


class ItineraryVersion(UUIDPk, Base):
    __tablename__ = "itinerary_versions"
    __table_args__ = (UniqueConstraint("itinerary_id", "version", name="uq_itinerary_version"),)

    itinerary_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("itineraries.id", ondelete="CASCADE"), index=True
    )
    version: Mapped[int] = mapped_column(Integer)
    summary: Mapped[str] = mapped_column(String(200))
    snapshot: Mapped[dict] = mapped_column(JSONB)  # full activity list + params at that version
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    itinerary: Mapped[Itinerary] = relationship(back_populates="versions")
