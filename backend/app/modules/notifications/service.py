"""In-app notifications with DB-level idempotency, plus optional email delivery through a provider."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.core.errors import not_found
from app.integrations.email.base import EmailError, EmailNotConfigured, EmailProvider
from app.integrations.email.providers import get_email
from app.models.booking import Notification, NotificationDelivery
from app.models.user import User

EMAIL_TYPES = {"booking_confirmed", "booking_cancelled", "booking_refund_failed", "trip_reminder", "weather_alert"}


class NotificationService:
    def __init__(self, db: Session, email: EmailProvider | None = None):
        self.db = db
        self.email = email if email is not None else get_email()

    def notify(self, user_id: uuid.UUID, type_: str, title: str, body: str, key: str, data: dict | None = None) -> bool:
        """Creates the notification unless one with this idempotency key already exists. Returns True when created.
        Safe to call repeatedly and concurrently; does not commit (caller owns the transaction)."""
        stmt = (
            pg_insert(Notification)
            .values(
                user_id=user_id, type=type_, title=title[:160], body=body[:600], data=data or {}, idempotency_key=key
            )
            .on_conflict_do_nothing(index_elements=["idempotency_key"])
            .returning(Notification.id)
        )
        return self.db.execute(stmt).scalar_one_or_none() is not None

    # ------------------------------------------------------------------ reading (owner-scoped)
    def list(self, user: User, unread_only: bool, page: int, page_size: int):
        base = select(Notification).where(Notification.user_id == user.id)
        if unread_only:
            base = base.where(Notification.read_at.is_(None))
        total = self.db.scalar(select(func.count()).select_from(base.subquery())) or 0
        rows = self.db.scalars(
            base.order_by(Notification.created_at.desc(), Notification.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
        return list(rows), total

    def unread_count(self, user: User) -> int:
        return (
            self.db.scalar(
                select(func.count())
                .select_from(Notification)
                .where(Notification.user_id == user.id, Notification.read_at.is_(None))
            )
            or 0
        )

    def mark_read(self, user: User, notification_id: uuid.UUID) -> Notification:
        n = self.db.scalar(
            select(Notification).where(Notification.id == notification_id, Notification.user_id == user.id)
        )
        if n is None:
            raise not_found("Notification")
        if n.read_at is None:
            n.read_at = datetime.now(UTC)
            self.db.commit()
        return n

    def read_all(self, user: User) -> int:
        res = self.db.execute(
            update(Notification)
            .where(Notification.user_id == user.id, Notification.read_at.is_(None))
            .values(read_at=datetime.now(UTC))
        )
        self.db.commit()
        return res.rowcount or 0

    # ------------------------------------------------------------------ external delivery (background job)
    MAX_ATTEMPTS = 3

    def deliver_pending(self, limit: int = 100) -> dict[str, int]:
        """Email delivery for eligible notifications. Without a configured provider rows are marked `skipped`
        (recorded, never pretended as sent). One delivery row per notification+channel, so nothing is sent twice;
        failed deliveries are retried on later runs, up to MAX_ATTEMPTS."""
        out = {"sent": 0, "skipped": 0, "failed": 0}
        has_row = select(NotificationDelivery.id).where(
            NotificationDelivery.notification_id == Notification.id, NotificationDelivery.channel == "email"
        )
        fresh = self.db.scalars(
            select(Notification)
            .where(Notification.type.in_(EMAIL_TYPES), ~has_row.exists())
            .order_by(Notification.created_at)
            .limit(limit)
        ).all()
        for n in fresh:
            ins = (
                pg_insert(NotificationDelivery)
                .values(notification_id=n.id, channel="email", status="pending")
                .on_conflict_do_nothing(index_elements=["notification_id", "channel"])
                .returning(NotificationDelivery.id)
            )
            if self.db.execute(ins).scalar_one_or_none() is None:
                continue  # another worker took it
        self.db.flush()
        todo = self.db.scalars(
            select(NotificationDelivery)
            .where(
                NotificationDelivery.channel == "email",
                (NotificationDelivery.status == "pending")
                | ((NotificationDelivery.status == "failed") & (NotificationDelivery.attempts < self.MAX_ATTEMPTS)),
            )
            .order_by(NotificationDelivery.updated_at)
            .limit(limit)
            .with_for_update(skip_locked=True)
        ).all()
        for d in todo:
            n = self.db.get(Notification, d.notification_id)
            user = self.db.get(User, n.user_id)
            d.attempts += 1
            d.provider = self.email.name
            d.updated_at = datetime.now(UTC)
            try:
                self.email.send(user.email, n.title, n.body)
                d.status, d.detail = "sent", None
                out["sent"] += 1
            except EmailNotConfigured as exc:
                d.status, d.detail = "skipped", str(exc)[:300]
                out["skipped"] += 1
            except EmailError as exc:
                d.status, d.detail = "failed", str(exc)[:300]
                out["failed"] += 1
        self.db.commit()
        return out
