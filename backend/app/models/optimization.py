import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, Float, ForeignKey, Index, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, UUIDPk


class OptimizationRun(UUIDPk, Base):
    """One optimisation preview. `applied` flips only when the traveler applies it."""

    __tablename__ = "optimization_runs"
    __table_args__ = (
        CheckConstraint("status IN ('optimized', 'relaxed', 'infeasible')", name="ck_opt_runs_status"),
        Index("ix_opt_runs_itinerary", "itinerary_id", "created_at"),
    )

    itinerary_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("itineraries.id", ondelete="CASCADE")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(String(12))
    base_version: Mapped[int] = mapped_column(Integer)
    weights: Mapped[dict] = mapped_column(JSONB)
    routing: Mapped[dict] = mapped_column(JSONB)  # source, notes, live_traffic, fetched_at
    before: Mapped[dict] = mapped_column(JSONB)
    after: Mapped[dict | None] = mapped_column(JSONB)
    changes: Mapped[list] = mapped_column(JSONB, default=list)
    dropped: Mapped[list] = mapped_column(JSONB, default=list)
    notes: Mapped[list] = mapped_column(JSONB, default=list)
    solver_ms: Mapped[float | None] = mapped_column(Float)
    applied: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ContextSnapshot(UUIDPk, Base):
    """A piece of context with its source and freshness. Weather rows come only from a configured provider;
    `report` rows are traveler-reported (labelled as such). Nothing here is ever invented."""

    __tablename__ = "context_snapshots"
    __table_args__ = (
        CheckConstraint("kind IN ('weather', 'report')", name="ck_context_kind"),
        Index("ix_context_itinerary", "itinerary_id", "kind", "fetched_at"),
    )

    itinerary_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("itineraries.id", ondelete="CASCADE")
    )
    kind: Mapped[str] = mapped_column(String(10))
    day_number: Mapped[int | None] = mapped_column(Integer)
    source: Mapped[str] = mapped_column(String(32))
    payload: Mapped[dict] = mapped_column(JSONB)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AdaptationProposal(UUIDPk, Base):
    """A proposed change to an itinerary. Never applied without the owner's approval."""

    __tablename__ = "adaptation_proposals"
    __table_args__ = (
        CheckConstraint("status IN ('pending', 'approved', 'rejected', 'superseded')", name="ck_adapt_status"),
        Index("ix_adapt_itinerary", "itinerary_id", "created_at"),
    )

    itinerary_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("itineraries.id", ondelete="CASCADE")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(String(12), default="pending", server_default="pending")
    signature: Mapped[str] = mapped_column(String(64))  # dedupes identical pending proposals
    trigger: Mapped[dict] = mapped_column(JSONB)  # type, evidence, source, fetched_at
    changes: Mapped[list] = mapped_column(JSONB)
    preview: Mapped[dict] = mapped_column(JSONB)  # resulting plan summary + violations
    base_version: Mapped[int] = mapped_column(Integer)
    material: Mapped[bool] = mapped_column(Boolean, default=True)
    applied_version: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
