"""Background jobs. Each is idempotent (safe to run twice or concurrently) and returns a small result dict.
Notifications use DB-level idempotency keys; inventory release is guarded by row locks and status transitions."""

from __future__ import annotations

import logging
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.timeutil import today_local
from app.integrations.weather.base import WeatherError
from app.models.booking import Booking
from app.models.itinerary import Itinerary
from app.models.user import User
from app.modules.bookings.service import BookingService
from app.modules.context.service import ContextService
from app.modules.notifications.service import NotificationService

log = logging.getLogger("routeaura.jobs")


def expire_holds(db: Session) -> dict:
    return {"released": BookingService(db).expire_holds()}


def send_trip_reminders(db: Session) -> dict:
    """Reminders for trips starting tomorrow (property time zone): confirmed bookings and itineraries with a start date."""
    tomorrow = today_local() + timedelta(days=1)
    notifier = NotificationService(db)
    created = 0
    for b in db.scalars(select(Booking).where(Booking.status == "confirmed", Booking.check_in == tomorrow)):
        created += notifier.notify(
            b.user_id,
            "trip_reminder",
            f"Check-in tomorrow: {b.hotel.name}",
            f"Your stay {b.reference} starts tomorrow ({b.check_in:%d %b}). Check-out {b.check_out:%d %b}.",
            f"trip_reminder:booking:{b.id}",
            {"booking_id": str(b.id)},
        )
    for it in db.scalars(select(Itinerary).where(Itinerary.start_date == tomorrow, Itinerary.deleted_at.is_(None))):
        n = len(it.activities)
        created += notifier.notify(
            it.user_id,
            "trip_reminder",
            f"Your trip starts tomorrow: {it.title}",
            f"{n} planned activit{'y' if n == 1 else 'ies'} over {it.days} day(s). Open the itinerary to review the plan and conditions.",
            f"trip_reminder:itinerary:{it.id}:{tomorrow.isoformat()}",
            {"itinerary_id": str(it.id)},
        )
    db.commit()
    return {"created": created}


def weather_alerts(db: Session) -> dict:
    """For trips starting within a week, fetch fresh weather (only if a provider is configured) and let the adaptation
    engine create proposals; ContextService notifies the owner once per proposal."""
    from app.integrations.weather.providers import get_weather

    if get_weather().name == "none":
        return {"skipped": "no weather provider configured", "checked": 0}
    today = today_local()
    checked = 0
    for it in db.scalars(
        select(Itinerary).where(
            Itinerary.deleted_at.is_(None),
            Itinerary.start_date >= today,
            Itinerary.start_date <= today + timedelta(days=7),
        )
    ):
        user = db.get(User, it.user_id)
        svc = ContextService(db)
        try:
            svc.refresh(user, it.id)
            svc.adapt(user, it.id)
            checked += 1
        except (AppError, WeatherError) as exc:
            log.warning("weather alert check failed for %s: %s", it.id, exc)
            db.rollback()
    return {"checked": checked}


def deliver_notifications(db: Session) -> dict:
    return NotificationService(db).deliver_pending()


JOBS = {
    "expire_holds": expire_holds,
    "trip_reminders": send_trip_reminders,
    "weather_alerts": weather_alerts,
    "deliver_notifications": deliver_notifications,
}


def run_all(db: Session) -> dict[str, dict]:
    """Runs every job, isolating failures so one broken job cannot stop the others."""
    out: dict[str, dict] = {}
    for name, fn in JOBS.items():
        try:
            out[name] = fn(db)
        except Exception as exc:  # noqa: BLE001
            db.rollback()
            log.exception("job %s failed", name)
            out[name] = {"error": type(exc).__name__}
    return out
