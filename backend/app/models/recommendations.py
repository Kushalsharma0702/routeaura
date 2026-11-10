import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, Timestamps, UUIDPk

INTERACTION_TYPES = ("view", "click", "save", "unsave", "like", "dislike", "reaction_clear", "dismiss", "restore")
SOURCES = ("browse", "detail", "recommendation", "saved")
RATINGS = ("relevant", "not_relevant")
_in = lambda col, values: f"{col} IN ({', '.join(repr(v) for v in values)})"  # noqa: E731
_one_item = (
    "(destination_id IS NOT NULL AND attraction_id IS NULL) OR (destination_id IS NULL AND attraction_id IS NOT NULL)"
)


class RecommendationRun(UUIDPk, Base):
    """One generation request: what was asked, the effective preference snapshot and the model config used."""

    __tablename__ = "recommendation_runs"
    __table_args__ = (
        CheckConstraint(_in("kind", ("destination", "attraction")), name="ck_reco_runs_kind"),
        Index("ix_reco_runs_user_created", "user_id", "created_at"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(12))
    strategy: Mapped[str] = mapped_column(String(24))
    model_version: Mapped[str] = mapped_column(String(32))
    config: Mapped[dict] = mapped_column(JSONB)
    preferences: Mapped[dict] = mapped_column(JSONB)  # effective preference snapshot (saved prefs + overrides)
    filters: Mapped[dict] = mapped_column(JSONB, default=dict)
    priorities: Mapped[dict] = mapped_column(JSONB, default=dict)
    total_candidates: Mapped[int] = mapped_column(Integer)
    returned_count: Mapped[int] = mapped_column(Integer)
    page: Mapped[int] = mapped_column(Integer, default=1)
    page_size: Mapped[int] = mapped_column(Integer, default=10)
    diversified: Mapped[bool] = mapped_column(Boolean, default=False)
    diversity_lambda: Mapped[float | None] = mapped_column(Float)
    latency_ms: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class RecommendationItem(UUIDPk, Base):
    """An impression: one item shown to the user in one run, with its score and explanation."""

    __tablename__ = "recommendation_items"
    __table_args__ = (
        CheckConstraint(_one_item, name="ck_reco_items_one_target"),
        UniqueConstraint("run_id", "rank", name="uq_reco_items_run_rank"),
        Index("ix_reco_items_run", "run_id"),
    )

    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("recommendation_runs.id", ondelete="CASCADE")
    )
    destination_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("destinations.id", ondelete="CASCADE")
    )
    attraction_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("attractions.id", ondelete="CASCADE")
    )
    rank: Mapped[int] = mapped_column(Integer)
    original_rank: Mapped[int] = mapped_column(Integer)
    score: Mapped[float] = mapped_column(Float)
    confidence: Mapped[float] = mapped_column(Float)
    explanation: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class UserInteraction(UUIDPk, Base):
    """Append-only event log. Current state (saved/liked/dismissed) is derived from the latest event."""

    __tablename__ = "user_interactions"
    __table_args__ = (
        CheckConstraint(_one_item, name="ck_interactions_one_target"),
        CheckConstraint(_in("interaction_type", INTERACTION_TYPES), name="ck_interactions_type"),
        CheckConstraint(_in("source", SOURCES), name="ck_interactions_source"),
        Index("ix_interactions_user_created", "user_id", "created_at"),
        Index("ix_interactions_dest", "destination_id", "interaction_type"),
        Index("ix_interactions_attr", "attraction_id", "interaction_type"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    destination_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("destinations.id", ondelete="CASCADE")
    )
    attraction_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("attractions.id", ondelete="CASCADE")
    )
    interaction_type: Mapped[str] = mapped_column(String(16))
    source: Mapped[str] = mapped_column(String(16), default="browse", server_default="browse")
    recommendation_item_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("recommendation_items.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class RecommendationFeedback(UUIDPk, Timestamps, Base):
    """Latest explicit feedback of a user on one shown recommendation (one row per user+impression)."""

    __tablename__ = "recommendation_feedback"
    __table_args__ = (
        CheckConstraint(_in("rating", RATINGS), name="ck_reco_feedback_rating"),
        UniqueConstraint("user_id", "item_id", name="uq_reco_feedback_user_item"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("recommendation_items.id", ondelete="CASCADE")
    )
    rating: Mapped[str] = mapped_column(String(16))
    reasons: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]")
    comment: Mapped[str | None] = mapped_column(String(500))
