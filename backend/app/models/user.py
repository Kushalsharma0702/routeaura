import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    ARRAY,
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, Timestamps, UUIDPk


class Role(enum.StrEnum):
    TRAVELER = "traveler"
    ADMIN = "admin"


class User(UUIDPk, Timestamps, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)  # stored lowercase
    full_name: Mapped[str] = mapped_column(String(120))
    phone: Mapped[str | None] = mapped_column(String(32))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[Role] = mapped_column(
        Enum(
            Role, name="user_role", native_enum=False, create_constraint=True, length=16,
            values_callable=lambda e: [m.value for m in e]),
        default=Role.TRAVELER,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")

    preferences: Mapped["UserPreference | None"] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )


class UserPreference(Timestamps, Base):
    __tablename__ = "user_preferences"
    __table_args__ = (
        CheckConstraint("budget_per_day_minor IS NULL OR budget_per_day_minor >= 0"),
        CheckConstraint("group_size IS NULL OR group_size BETWEEN 1 AND 50"),
        CheckConstraint("trip_duration_days IS NULL OR trip_duration_days BETWEEN 1 AND 60"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    budget_per_day_minor: Mapped[int | None] = mapped_column(Integer)  # INR paise
    currency: Mapped[str] = mapped_column(String(3), default="INR", server_default="INR")
    trip_duration_days: Mapped[int | None] = mapped_column(Integer)
    interests: Mapped[list[str]] = mapped_column(
        ARRAY(String(40)), default=list, server_default="{}"
    )
    preferred_climate: Mapped[str | None] = mapped_column(String(20))
    preferred_season: Mapped[str | None] = mapped_column(String(20))
    group_size: Mapped[int | None] = mapped_column(Integer)
    travel_style: Mapped[str | None] = mapped_column(String(20))
    accommodation_preference: Mapped[str | None] = mapped_column(String(20))
    language: Mapped[str] = mapped_column(String(8), default="en", server_default="en")

    user: Mapped[User] = relationship(back_populates="preferences")


class RefreshToken(UUIDPk, Base):
    """Opaque refresh tokens, stored only as SHA-256 hashes. A family is one login session."""

    __tablename__ = "refresh_tokens"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    family_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AuditLog(UUIDPk, Base):
    __tablename__ = "audit_logs"

    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    action: Mapped[str] = mapped_column(String(64), index=True)
    entity_type: Mapped[str] = mapped_column(String(40))
    entity_id: Mapped[str | None] = mapped_column(String(64))
    detail: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
