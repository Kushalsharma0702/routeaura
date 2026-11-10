import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.catalog import Attraction, Destination
from app.models.recommendations import (
    RecommendationFeedback,
    RecommendationItem,
    RecommendationRun,
    UserInteraction,
)

ItemKey = tuple[str, str]


def item_key(row) -> ItemKey:
    return ("destination", str(row.destination_id)) if row.destination_id else ("attraction", str(row.attraction_id))


def target_columns(kind: str, item_id: uuid.UUID) -> dict:
    return {"destination_id": item_id} if kind == "destination" else {"attraction_id": item_id}


class InteractionRepository:
    def __init__(self, db: Session):
        self.db = db

    def add(
        self,
        user_id: uuid.UUID,
        kind: str,
        item_id: uuid.UUID,
        interaction_type: str,
        source: str,
        recommendation_item_id: uuid.UUID | None,
    ) -> UserInteraction:
        row = UserInteraction(
            user_id=user_id,
            interaction_type=interaction_type,
            source=source,
            recommendation_item_id=recommendation_item_id,
            **target_columns(kind, item_id),
        )
        self.db.add(row)
        self.db.flush()
        return row

    def events(self, user_id: uuid.UUID, since: datetime | None = None, kind_item: ItemKey | None = None):
        stmt = select(UserInteraction).where(UserInteraction.user_id == user_id)
        if since:
            stmt = stmt.where(UserInteraction.created_at >= since)
        if kind_item:
            col = UserInteraction.destination_id if kind_item[0] == "destination" else UserInteraction.attraction_id
            stmt = stmt.where(col == uuid.UUID(kind_item[1]))
        return self.db.scalars(stmt.order_by(UserInteraction.created_at, UserInteraction.id)).all()

    def recent_view_exists(self, user_id: uuid.UUID, kind: str, item_id: uuid.UUID, minutes: int = 10) -> bool:
        since = datetime.now(UTC) - timedelta(minutes=minutes)
        stmt = (
            select(UserInteraction.id)
            .where(
                UserInteraction.user_id == user_id,
                UserInteraction.interaction_type == "view",
                UserInteraction.created_at >= since,
                *[getattr(UserInteraction, k) == v for k, v in target_columns(kind, item_id).items()],
            )
            .limit(1)
        )
        return self.db.scalar(stmt) is not None

    def popularity_counts(self, kind: str) -> dict[str, dict[str, int]]:
        """Aggregate event counts per item across all users (no per-user data leaves this method)."""
        col = UserInteraction.destination_id if kind == "destination" else UserInteraction.attraction_id
        rows = self.db.execute(
            select(col, UserInteraction.interaction_type, func.count())
            .where(col.is_not(None))
            .group_by(col, UserInteraction.interaction_type)
        ).all()
        out: dict[str, dict[str, int]] = {}
        for item_id, itype, n in rows:
            out.setdefault(str(item_id), {})[itype] = n
        return out


class RunRepository:
    def __init__(self, db: Session):
        self.db = db

    def add_run(self, run: RecommendationRun, items: list[RecommendationItem]) -> None:
        self.db.add(run)
        self.db.flush()
        for it in items:
            it.run_id = run.id
        self.db.add_all(items)
        self.db.flush()

    def list_runs(self, user_id: uuid.UUID, kind: str | None, page: int, page_size: int):
        stmt = select(RecommendationRun).where(RecommendationRun.user_id == user_id)
        if kind:
            stmt = stmt.where(RecommendationRun.kind == kind)
        total = self.db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        rows = self.db.scalars(
            stmt.order_by(RecommendationRun.created_at.desc(), RecommendationRun.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
        return list(rows), total

    def get_run(self, user_id: uuid.UUID, run_id: uuid.UUID) -> RecommendationRun | None:
        """Only returns the caller's own run: other users' runs look exactly like missing ones."""
        return self.db.scalar(
            select(RecommendationRun).where(RecommendationRun.id == run_id, RecommendationRun.user_id == user_id)
        )

    def items(self, run_ids: list[uuid.UUID]) -> list[RecommendationItem]:
        if not run_ids:
            return []
        return list(
            self.db.scalars(
                select(RecommendationItem)
                .where(RecommendationItem.run_id.in_(run_ids))
                .order_by(RecommendationItem.run_id, RecommendationItem.rank)
            )
        )

    def get_item(self, user_id: uuid.UUID, item_id: uuid.UUID) -> RecommendationItem | None:
        return self.db.scalar(
            select(RecommendationItem)
            .join(RecommendationRun, RecommendationRun.id == RecommendationItem.run_id)
            .where(RecommendationItem.id == item_id, RecommendationRun.user_id == user_id)
        )


class FeedbackRepository:
    def __init__(self, db: Session):
        self.db = db

    def upsert(
        self, user_id: uuid.UUID, item_id: uuid.UUID, rating: str, reasons: list[str], comment: str | None
    ) -> RecommendationFeedback:
        row = self.db.scalar(
            select(RecommendationFeedback).where(
                RecommendationFeedback.user_id == user_id, RecommendationFeedback.item_id == item_id
            )
        )
        if row is None:
            row = RecommendationFeedback(
                user_id=user_id, item_id=item_id, rating=rating, reasons=reasons, comment=comment
            )
            self.db.add(row)
        else:
            row.rating, row.reasons, row.comment = rating, reasons, comment
        self.db.flush()
        self.db.refresh(row)
        return row

    def for_items(self, user_id: uuid.UUID, item_ids: list[uuid.UUID]) -> dict[uuid.UUID, str]:
        if not item_ids:
            return {}
        rows = self.db.execute(
            select(RecommendationFeedback.item_id, RecommendationFeedback.rating).where(
                RecommendationFeedback.user_id == user_id, RecommendationFeedback.item_id.in_(item_ids)
            )
        ).all()
        return dict(rows)

    def by_target(self, user_id: uuid.UUID) -> dict[ItemKey, list[str]]:
        """The user's feedback ratings grouped by the destination/attraction they were about."""
        rows = self.db.execute(
            select(RecommendationItem.destination_id, RecommendationItem.attraction_id, RecommendationFeedback.rating)
            .join(RecommendationItem, RecommendationItem.id == RecommendationFeedback.item_id)
            .where(RecommendationFeedback.user_id == user_id)
        ).all()
        out: dict[ItemKey, list[str]] = {}
        for d, a, rating in rows:
            key = ("destination", str(d)) if d else ("attraction", str(a))
            out.setdefault(key, []).append(rating)
        return out


__all__ = ["Attraction", "Destination", "FeedbackRepository", "InteractionRepository", "RunRepository", "item_key"]
