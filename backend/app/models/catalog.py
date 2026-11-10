import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Table,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, Timestamps, UUIDPk

LAT_CHECK = "latitude BETWEEN -90 AND 90"
LNG_CHECK = "longitude BETWEEN -180 AND 180"

destination_categories = Table(
    "destination_categories",
    Base.metadata,
    Column("destination_id", UUID(as_uuid=True), ForeignKey("destinations.id", ondelete="CASCADE"),
           primary_key=True),
    Column("category_id", UUID(as_uuid=True), ForeignKey("attraction_categories.id",
                                                          ondelete="RESTRICT"), primary_key=True),
)


class AttractionCategory(UUIDPk, Timestamps, Base):
    __tablename__ = "attraction_categories"

    slug: Mapped[str] = mapped_column(String(60), unique=True)
    name: Mapped[str] = mapped_column(String(80), unique=True)
    description: Mapped[str | None] = mapped_column(String(300))


class Destination(UUIDPk, Timestamps, Base):
    __tablename__ = "destinations"
    __table_args__ = (
        CheckConstraint(LAT_CHECK, name="ck_destinations_lat"),
        CheckConstraint(LNG_CHECK, name="ck_destinations_lng"),
        CheckConstraint("estimated_cost_per_day_minor IS NULL OR estimated_cost_per_day_minor >= 0",
                        name="ck_destinations_cost"),
        CheckConstraint("recommended_duration_days IS NULL OR recommended_duration_days BETWEEN 1 AND 60",
                        name="ck_destinations_duration"),
        CheckConstraint("(best_season_start_month IS NULL) = (best_season_end_month IS NULL)",
                        name="ck_destinations_season_pair"),
        CheckConstraint("best_season_start_month IS NULL OR best_season_start_month BETWEEN 1 AND 12",
                        name="ck_destinations_season_start"),
        CheckConstraint("best_season_end_month IS NULL OR best_season_end_month BETWEEN 1 AND 12",
                        name="ck_destinations_season_end"),
        Index("ix_destinations_latlng", "latitude", "longitude"),
        Index("ix_destinations_published", "is_published", postgresql_where=text("deleted_at IS NULL")),
    )

    slug: Mapped[str] = mapped_column(String(100), unique=True)
    name: Mapped[str] = mapped_column(String(120), index=True)
    country: Mapped[str] = mapped_column(String(80), index=True)
    region: Mapped[str | None] = mapped_column(String(80))
    description: Mapped[str] = mapped_column(Text, default="")
    latitude: Mapped[float] = mapped_column(Numeric(9, 6))
    longitude: Mapped[float] = mapped_column(Numeric(9, 6))
    estimated_cost_per_day_minor: Mapped[int | None] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3), default="INR", server_default="INR")
    recommended_duration_days: Mapped[int | None] = mapped_column(Integer)
    best_season_start_month: Mapped[int | None] = mapped_column(Integer)
    best_season_end_month: Mapped[int | None] = mapped_column(Integer)
    climate: Mapped[str | None] = mapped_column(String(20))
    climate_notes: Mapped[str | None] = mapped_column(String(300))
    accessibility_notes: Mapped[str | None] = mapped_column(String(500))
    images: Mapped[list[str]] = mapped_column(JSONB, default=list, server_default="[]")
    is_published: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    source: Mapped[str] = mapped_column(String(16), default="admin", server_default="admin")
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    categories: Mapped[list[AttractionCategory]] = relationship(
        secondary=destination_categories, lazy="selectin", order_by=AttractionCategory.name
    )
    attractions: Mapped[list["Attraction"]] = relationship(back_populates="destination")


class Attraction(UUIDPk, Timestamps, Base):
    __tablename__ = "attractions"
    __table_args__ = (
        CheckConstraint(LAT_CHECK, name="ck_attractions_lat"),
        CheckConstraint(LNG_CHECK, name="ck_attractions_lng"),
        CheckConstraint("estimated_cost_minor IS NULL OR estimated_cost_minor >= 0",
                        name="ck_attractions_cost"),
        CheckConstraint("typical_duration_minutes BETWEEN 5 AND 1440", name="ck_attractions_duration"),
        UniqueConstraint("destination_id", "slug", name="uq_attractions_dest_slug"),
        Index("ix_attractions_latlng", "latitude", "longitude"),
        Index("ix_attractions_dest_pub", "destination_id", "is_published"),
    )

    destination_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("destinations.id", ondelete="RESTRICT"), index=True
    )
    category_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("attraction_categories.id", ondelete="RESTRICT"), index=True
    )
    slug: Mapped[str] = mapped_column(String(100))
    name: Mapped[str] = mapped_column(String(140), index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    latitude: Mapped[float] = mapped_column(Numeric(9, 6))
    longitude: Mapped[float] = mapped_column(Numeric(9, 6))
    estimated_cost_minor: Mapped[int | None] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3), default="INR", server_default="INR")
    typical_duration_minutes: Mapped[int] = mapped_column(Integer, default=90, server_default="90")
    opening_hours: Mapped[dict | None] = mapped_column(JSONB)
    opening_hours_source: Mapped[str | None] = mapped_column(String(16))
    is_outdoor: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    accessibility_notes: Mapped[str | None] = mapped_column(String(500))
    images: Mapped[list[str]] = mapped_column(JSONB, default=list, server_default="[]")
    is_published: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    source: Mapped[str] = mapped_column(String(16), default="admin", server_default="admin")
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    destination: Mapped[Destination] = relationship(back_populates="attractions")
    category: Mapped[AttractionCategory] = relationship(lazy="joined")
