"""A small in-process scheduler (no Redis/Celery needed). Use ONE scheduler per deployment: a PostgreSQL advisory
lock makes extra instances skip a tick instead of duplicating work, and every job is idempotent anyway."""

from __future__ import annotations

import logging
import threading

from sqlalchemy import text

from app.database.session import get_engine, get_sessionmaker
from app.workers.jobs import run_all

log = logging.getLogger("routeaura.scheduler")
LOCK_ID = 0x52_41_5F_4A  # "RA_J"


def run_once() -> dict | None:
    """One scheduler tick. Returns job results, or None when another instance holds the lock.

    The advisory lock is bound to a DB *connection*, so it is taken and released on a dedicated connection that
    lives for the whole tick. (A Session may switch pooled connections after each commit, which would leak the lock.)
    """
    with get_engine().connect() as lock_conn:
        if not lock_conn.execute(text("SELECT pg_try_advisory_lock(:id)"), {"id": LOCK_ID}).scalar():
            return None
        try:
            with get_sessionmaker()() as db:
                return run_all(db)
        finally:
            lock_conn.execute(text("SELECT pg_advisory_unlock(:id)"), {"id": LOCK_ID})
            lock_conn.commit()


def start_background(interval_s: int = 60) -> threading.Event:
    stop = threading.Event()

    def loop() -> None:
        while not stop.wait(interval_s):
            try:
                run_once()
            except Exception:  # noqa: BLE001
                log.exception("scheduler tick failed")

    threading.Thread(target=loop, name="routeaura-jobs", daemon=True).start()
    return stop
