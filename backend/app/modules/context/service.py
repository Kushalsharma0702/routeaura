"""Context collection, adaptation proposals and the approval workflow."""

from __future__ import annotations

import hashlib
import time
import uuid
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError, not_found
from app.integrations.weather.base import DayForecast, WeatherError, WeatherNotConfigured, WeatherProvider
from app.integrations.weather.providers import get_weather
from app.models.catalog import Attraction, Destination
from app.models.itinerary import Itinerary, ItineraryActivity
from app.models.optimization import AdaptationProposal, ContextSnapshot
from app.models.user import User
from app.modules.context import engine as ce
from app.modules.itinerary.service import ItineraryService, _candidate
from app.modules.notifications.service import NotificationService
from app.modules.recommendations.service import RecommendationService
from app.schemas.context import AdaptResultOut, ContextStatusOut, ProposalOut, ReportIn, SnapshotOut


class ContextService:
    def __init__(self, db: Session, weather: WeatherProvider | None = None, now=None):
        self.db = db
        self.weather = weather if weather is not None else get_weather()
        self.th = ce.Thresholds(max_age_min=get_settings().weather_max_age_minutes)
        self.itineraries = ItineraryService(db)
        self._now = now or (lambda: datetime.now(UTC))

    # ------------------------------------------------------------------ helpers
    def _stops(self, it: Itinerary) -> dict[int, list[ce.Stop]]:
        days: dict[int, list[ce.Stop]] = {d: [] for d in range(1, it.days + 1)}
        for a in sorted(it.activities, key=lambda a: (a.day_number, a.position)):
            days[a.day_number].append(
                self._stop(a, a.attraction, a.score or 0.0, a.duration_min, a.cost_minor, a.locked, str(a.id))
            )
        return days

    @staticmethod
    def _stop(
        a: ItineraryActivity | None,
        att: Attraction,
        score: float,
        duration: int,
        cost: int | None,
        locked: bool,
        sid: str,
    ) -> ce.Stop:
        cand = _candidate(att, score, duration, cost)
        cand.id = sid
        return ce.Stop(
            id=sid,
            attraction_id=str(att.id),
            name=att.name,
            lat=float(att.latitude),
            lng=float(att.longitude),
            category=att.category.slug,
            is_outdoor=att.is_outdoor,
            duration_min=duration,
            cost_minor=cost,
            score=score,
            locked=locked,
            candidate=cand,
        )

    def _pool(self, user: User, it: Itinerary) -> list[ce.Stop]:
        dest = self.db.get(Destination, it.destination_id)
        used = {a.attraction_id for a in it.activities}
        attrs = [
            a
            for a in self.db.scalars(
                select(Attraction).where(
                    Attraction.destination_id == it.destination_id,
                    Attraction.is_published.is_(True),
                    Attraction.deleted_at.is_(None),
                )
            )
            if a.id not in used
        ]
        if not attrs:
            return []
        scored, _ = RecommendationService(self.db).score_attractions(
            user, dest, attrs, interests=it.interests or None, style=it.travel_style
        )
        return [
            self._stop(
                None,
                a,
                scored[str(a.id)].score if str(a.id) in scored else 0.0,
                a.typical_duration_minutes,
                a.estimated_cost_minor,
                False,
                str(a.id),
            )
            for a in attrs
        ]

    def _latest_weather(self, it: Itinerary) -> dict[int, ContextSnapshot]:
        rows = self.db.scalars(
            select(ContextSnapshot)
            .where(ContextSnapshot.itinerary_id == it.id, ContextSnapshot.kind == "weather")
            .order_by(ContextSnapshot.fetched_at.desc())
        )
        latest: dict[int, ContextSnapshot] = {}
        for r in rows:
            latest.setdefault(r.day_number, r)
        return latest

    def _snapshot_out(self, s: ContextSnapshot) -> SnapshotOut:
        age = int((self._now() - s.fetched_at).total_seconds() // 60)
        return SnapshotOut(
            id=s.id,
            kind=s.kind,
            day_number=s.day_number,
            source=s.source,
            payload=s.payload,
            fetched_at=s.fetched_at,
            age_minutes=age,
            fresh=ce.is_fresh(s.fetched_at, self._now(), self.th.max_age_min),
        )

    # ------------------------------------------------------------------ status / refresh / report
    def status(self, user: User, itinerary_id: uuid.UUID) -> ContextStatusOut:
        it = self.itineraries._own(user, itinerary_id)
        weather = self._latest_weather(it)
        reports = list(
            self.db.scalars(
                select(ContextSnapshot)
                .where(ContextSnapshot.itinerary_id == it.id, ContextSnapshot.kind == "report")
                .order_by(ContextSnapshot.fetched_at.desc())
                .limit(20)
            )
        )
        snaps = [self._snapshot_out(s) for _, s in sorted(weather.items())] + [self._snapshot_out(s) for s in reports]
        configured = self.weather.name != "none"
        notes = []
        if not configured:
            notes.append(
                "No weather provider is configured, so no weather is shown or used. You can still report closures, delays and spending yourself."
            )
        if configured and it.start_date is None:
            notes.append("Set trip dates to enable weather checks.")
        return ContextStatusOut(
            weather_provider=self.weather.name,
            weather_configured=configured,
            needs_dates=it.start_date is None,
            max_age_minutes=self.th.max_age_min,
            snapshots=snaps,
            stale_days=[
                d for d, s in weather.items() if not ce.is_fresh(s.fetched_at, self._now(), self.th.max_age_min)
            ],
            notes=notes,
        )

    def refresh(self, user: User, itinerary_id: uuid.UUID) -> ContextStatusOut:
        it = self.itineraries._own(user, itinerary_id)
        if self.weather.name == "none":
            raise AppError(
                409, "provider_not_configured", "No weather provider is configured; weather cannot be fetched"
            )
        if it.start_date is None:
            raise AppError(422, "dates_required", "Set the trip start date to check the weather")
        dest = self.db.get(Destination, it.destination_id)
        end = it.start_date + timedelta(days=it.days - 1)
        try:
            forecasts = self.weather.forecast(float(dest.latitude), float(dest.longitude), it.start_date, end)
        except WeatherNotConfigured as exc:
            raise AppError(409, "provider_not_configured", str(exc)) from exc
        except WeatherError as exc:
            raise AppError(502, "provider_error", f"The weather provider failed: {exc}") from exc
        for fc in forecasts:
            day = (fc.day - it.start_date).days + 1
            if 1 <= day <= it.days:
                self.db.add(
                    ContextSnapshot(
                        itinerary_id=it.id,
                        kind="weather",
                        day_number=day,
                        source=fc.source,
                        payload=fc.to_payload(),
                        fetched_at=fc.fetched_at,
                        valid_until=fc.fetched_at + timedelta(minutes=self.th.max_age_min),
                    )
                )
        self.db.commit()
        return self.status(user, itinerary_id)

    def report(self, user: User, itinerary_id: uuid.UUID, body: ReportIn) -> ContextStatusOut:
        it = self.itineraries._own(user, itinerary_id)
        ids = {a.id for a in it.activities}
        if body.activity_id and body.activity_id not in ids:
            raise not_found("Activity")
        if any(a not in ids for a in body.completed_activity_ids):
            raise AppError(422, "validation_error", "completed_activity_ids must belong to this itinerary")
        if body.day_number and body.day_number > it.days:
            raise AppError(422, "validation_error", "day_number is outside the trip")
        payload = {**body.model_dump(mode="json"), "consumed": False}
        self.db.add(
            ContextSnapshot(
                itinerary_id=it.id,
                kind="report",
                day_number=body.day_number,
                source="user_reported",
                payload=payload,
                fetched_at=self._now(),
            )
        )
        self.db.commit()
        return self.status(user, itinerary_id)

    # ------------------------------------------------------------------ adapt
    def adapt(self, user: User, itinerary_id: uuid.UUID) -> AdaptResultOut:
        started = time.perf_counter()
        it = self.itineraries._own(user, itinerary_id)
        dest = self.db.get(Destination, it.destination_id)
        p = self.itineraries._params(it, dest)
        days = self._stops(it)
        by_id = {s.id: s for stops in days.values() for s in stops}
        now = self._now()
        notes: list[str] = []

        forecasts = {}
        for d, snap in self._latest_weather(it).items():
            pl_ = snap.payload
            forecasts[d] = DayForecast(
                date.fromisoformat(pl_["date"]),
                pl_.get("precip_mm"),
                pl_.get("precip_prob"),
                pl_.get("temp_max_c"),
                pl_.get("temp_min_c"),
                snap.source,
                snap.fetched_at,
            )
        issues, stale, wn = ce.detect_weather(days, forecasts, now, self.th)
        notes.extend(wn)
        if stale:
            notes.append(
                f"Weather for day(s) {', '.join(map(str, stale))} is older than {self.th.max_age_min} minutes and was NOT used. Refresh it first."
            )
        if not forecasts and self.weather.name == "none":
            notes.append("No weather provider is configured, so weather was not considered.")
        issues += ce.detect_verified_closures(days, it.start_date)

        reports = list(
            self.db.scalars(
                select(ContextSnapshot)
                .where(ContextSnapshot.itinerary_id == it.id, ContextSnapshot.kind == "report")
                .order_by(ContextSnapshot.fetched_at)
            )
        )
        pending = [r for r in reports if not r.payload.get("consumed")]
        pool = self._pool(user, it)
        changes_by_issue: list[tuple[ce.Issue, list[dict], dict]] = []
        unresolved: list[dict] = []
        taken: set[str] = set()  # alternatives already proposed (never propose the same replacement twice)

        def replace_change(issue: ce.Issue, alts: list[tuple[ce.Stop, str]]) -> list[dict]:
            old = by_id[issue.activity_id]
            picked = ce.pick_replacement(days, old, alts, p, taken)
            if picked is None:
                return []
            alt, why, viol = picked
            taken.add(alt.attraction_id)
            note = "" if viol == 0 else f" Note: this swap would leave {viol} schedule issue(s); see the preview."
            return [
                {
                    "action": "replace",
                    "activity_id": old.id,
                    "day": issue.day,
                    "from": old.name,
                    "to": alt.name,
                    "to_attraction_id": alt.attraction_id,
                    "to_score": alt.score,
                    "introduces_violations": viol,
                    "reason": f"{issue.type}: {issue.evidence}. Suggested {alt.name}: {why}.{note}",
                }
            ]

        for issue in issues:
            old = by_id.get(issue.activity_id) if issue.activity_id else None
            if old is None:
                continue
            alts = ce.rank_alternatives(
                old, pool, day=issue.day, start_date=it.start_date, indoor_only=issue.type in ("rain", "heat")
            )
            ch = replace_change(issue, alts)
            if ch:
                changes_by_issue.append((issue, ch, {"alternatives": [{"name": a.name, "why": w} for a, w in alts]}))
            else:
                unresolved.append({**issue.to_dict(), "reason": "no suitable published alternative"})

        for r in pending:
            pl_ = r.payload
            if pl_["type"] == "closure":
                old = by_id.get(str(pl_["activity_id"]))
                if old is None:
                    continue
                day = next(d_ for d_, ss in days.items() if old in ss)
                issue = ce.Issue(
                    "closure",
                    day,
                    old.id,
                    f"you reported {old.name} is closed",
                    "user_reported",
                    r.fetched_at.isoformat(),
                )
                alts = ce.rank_alternatives(old, pool, day=day, start_date=it.start_date, limit=6)
                ch = replace_change(issue, alts)
                (
                    changes_by_issue.append(
                        (issue, ch, {"alternatives": [{"name": a.name, "why": w} for a, w in alts]})
                    )
                    if ch
                    else unresolved.append({**issue.to_dict(), "reason": "no suitable published alternative"})
                )
                issues.append(issue)
            elif pl_["type"] == "delay":
                day = pl_["day_number"]
                done = {str(x) for x in pl_["completed_activity_ids"]}
                issue = ce.Issue(
                    "delay",
                    day,
                    None,
                    f"you are on day {day} at {pl_['current_time_min'] // 60:02d}:{pl_['current_time_min'] % 60:02d}",
                    "user_reported",
                    r.fetched_at.isoformat(),
                )
                next_room = day < it.days and len(days[day + 1]) < p.max_per_day
                ch, dn = ce.plan_delay(days[day], done, pl_["current_time_min"], day, next_room, p)
                notes.extend(dn)
                if ch:
                    changes_by_issue.append((issue, ch, {}))
                issues.append(issue)
            elif pl_["type"] == "spent" and it.budget_total_minor is not None:
                left = it.budget_total_minor - pl_["spent_minor"]
                remaining_cost = sum((s.cost_minor or 0) * it.traveler_count for ss in days.values() for s in ss)
                if remaining_cost > left:
                    paid = sorted(
                        (s for ss in days.values() for s in ss if s.cost_minor and not s.locked),
                        key=lambda s: -(s.cost_minor or 0),
                    )
                    day = next((d for d, ss in days.items() if paid and paid[0] in ss), 1)
                    issue = ce.Issue(
                        "over_budget",
                        day,
                        paid[0].id if paid else None,
                        f"you reported spending {pl_['spent_minor'] / 100:,.0f}; planned activities still cost {remaining_cost / 100:,.0f} against {left / 100:,.0f} left",
                        "user_reported",
                        r.fetched_at.isoformat(),
                    )
                    issues.append(issue)
                    if paid:
                        alts = ce.rank_alternatives(
                            paid[0],
                            pool,
                            day=day,
                            start_date=it.start_date,
                            max_cost_minor=(paid[0].cost_minor or 0) // 2,
                            limit=6,
                        )
                        ch = replace_change(issue, alts)
                        (
                            changes_by_issue.append(
                                (issue, ch, {"alternatives": [{"name": a.name, "why": w} for a, w in alts]})
                            )
                            if ch
                            else unresolved.append(
                                {**issue.to_dict(), "reason": "no cheaper published alternative with a known cost"}
                            )
                        )
                    else:
                        unresolved.append({**issue.to_dict(), "reason": "all remaining paid activities are locked"})
            r.payload = {**r.payload, "consumed": True}  # reports are used once; JSONB needs reassignment

        proposals: list[AdaptationProposal] = []
        for issue, changes, extra in changes_by_issue:
            sig = hashlib.sha256(
                f"{it.id}|{it.current_version}|{issue.type}|{issue.day}|{issue.activity_id}|{[c.get('to_attraction_id') or c.get('activity_id') for c in changes]}".encode()
            ).hexdigest()
            existing = self.db.scalar(
                select(AdaptationProposal).where(
                    AdaptationProposal.itinerary_id == it.id,
                    AdaptationProposal.signature == sig,
                    AdaptationProposal.status == "pending",
                )
            )
            if existing:
                proposals.append(existing)  # never create duplicates of a still-pending proposal
                continue
            preview = self._simulate(it, p, days, changes, pool)
            prop = AdaptationProposal(
                itinerary_id=it.id,
                user_id=user.id,
                signature=sig,
                trigger=issue.to_dict(),
                changes=changes,
                preview={**preview, **extra},
                base_version=it.current_version,
                material=True,
            )
            self.db.add(prop)
            self.db.flush()
            proposals.append(prop)
            kind = "weather_alert" if issue.type in ("rain", "heat") else "itinerary_adapted"
            title = (f"Weather alert for {it.title}" if kind == "weather_alert" else f"Suggested change for {it.title}")
            NotificationService(self.db).notify(
                it.user_id, kind if kind == "weather_alert" else "adaptation_proposal", title,
                f"{issue.type.replace('_', ' ').capitalize()} on day {issue.day}: {issue.evidence}. Review the suggested change; nothing is changed until you approve.",
                f"adaptation:proposal:{prop.id}", {"itinerary_id": str(it.id), "proposal_id": str(prop.id)})
        self.db.commit()
        for pr in proposals:
            self.db.refresh(pr)
        return AdaptResultOut(
            issues=[i.to_dict() for i in issues],
            proposals=[self._out(x) for x in proposals],
            unresolved=unresolved,
            stale_days=stale,
            notes=notes,
            latency_ms=round((time.perf_counter() - started) * 1000, 2),
        )

    def _simulate(
        self, it: Itinerary, p, days: dict[int, list[ce.Stop]], changes: list[dict], pool: list[ce.Stop]
    ) -> dict:
        new = {d: list(ss) for d, ss in days.items()}
        pool_by = {s.attraction_id: s for s in pool}
        for c in changes:
            if c["action"] == "replace":
                for ss in new.values():
                    for i, s in enumerate(ss):
                        if s.id == c["activity_id"]:
                            ss[i] = pool_by[c["to_attraction_id"]]
            elif c["action"] == "remove":
                for ss in new.values():
                    ss[:] = [s for s in ss if s.id != c["activity_id"]]
            elif c["action"] == "move":
                moved = next(s for ss in new.values() for s in ss if s.id == c["activity_id"])
                for ss in new.values():
                    ss[:] = [s for s in ss if s.id != moved.id]
                new[c["to_day"]].append(moved)
        return {"after": ce.simulate(new, p), "before": ce.simulate(days, p)}

    # ------------------------------------------------------------------ proposals
    def _out(self, pr: AdaptationProposal) -> ProposalOut:
        return ProposalOut(
            id=pr.id,
            itinerary_id=pr.itinerary_id,
            status=pr.status,
            trigger=pr.trigger,
            changes=pr.changes,
            preview=pr.preview,
            base_version=pr.base_version,
            material=pr.material,
            applied_version=pr.applied_version,
            created_at=pr.created_at,
            decided_at=pr.decided_at,
        )

    def proposals(self, user: User, itinerary_id: uuid.UUID) -> list[ProposalOut]:
        it = self.itineraries._own(user, itinerary_id)
        rows = self.db.scalars(
            select(AdaptationProposal)
            .where(AdaptationProposal.itinerary_id == it.id)
            .order_by(AdaptationProposal.created_at.desc())
        )
        return [self._out(r) for r in rows]

    def _proposal(self, user: User, proposal_id: uuid.UUID) -> AdaptationProposal:
        pr = self.db.scalar(
            select(AdaptationProposal).where(
                AdaptationProposal.id == proposal_id, AdaptationProposal.user_id == user.id
            )
        )
        if pr is None:
            raise not_found("Proposal")
        return pr

    def get(self, user: User, proposal_id: uuid.UUID) -> ProposalOut:
        return self._out(self._proposal(user, proposal_id))

    def reject(self, user: User, proposal_id: uuid.UUID) -> ProposalOut:
        pr = self._proposal(user, proposal_id)
        if pr.status != "pending":
            raise AppError(409, "not_pending", f"This proposal is already {pr.status}")
        pr.status, pr.decided_at = "rejected", self._now()
        self.db.commit()
        return self._out(pr)

    def approve(self, user: User, proposal_id: uuid.UUID):
        pr = self._proposal(user, proposal_id)
        it = self.itineraries._own(user, pr.itinerary_id)
        if pr.status != "pending":
            raise AppError(409, "not_pending", f"This proposal is already {pr.status}")
        if it.current_version != pr.base_version:
            pr.status, pr.decided_at = "superseded", self._now()
            self.db.commit()
            raise AppError(
                409, "stale_proposal", "The itinerary changed after this suggestion was made; check conditions again"
            )
        rows = {str(a.id): a for a in it.activities}
        summary = []
        for c in pr.changes:
            row = rows.get(c["activity_id"])
            if row is None:
                raise AppError(409, "stale_proposal", "An activity in this suggestion no longer exists")
            if c["action"] == "replace":
                att = self.db.get(Attraction, uuid.UUID(c["to_attraction_id"]))
                if att is None or att.deleted_at is not None or not att.is_published:
                    raise AppError(409, "stale_proposal", "The suggested attraction is no longer available")
                row.attraction_id, row.duration_min, row.cost_minor = (
                    att.id,
                    att.typical_duration_minutes,
                    att.estimated_cost_minor,
                )
                row.score, row.source, row.locked, row.notes = c.get("to_score"), "adapted", False, None
                row.explanation = {
                    "reasons": [c["reason"]],
                    "cautions": [],
                    "missing": [],
                    "notes": ["Added by an approved adaptation."],
                }
                summary.append(f"replaced {c['from']} with {c['to']}")
            elif c["action"] == "remove":
                self.db.delete(row)
                summary.append(f"removed {c['name']}")
            elif c["action"] == "move":
                row.day_number = c["to_day"]
                row.position = 10_000
                summary.append(f"moved {c['name']} to day {c['to_day']}")
        self.db.flush()
        self.db.refresh(it)
        for day in {a.day_number for a in it.activities}:
            for i, a in enumerate(
                sorted((x for x in it.activities if x.day_number == day), key=lambda x: x.position), 1
            ):
                a.position = i
        self.itineraries._reschedule(it)
        self.itineraries._new_version(it, user, f"Adapted ({pr.trigger['type']}): " + "; ".join(summary))
        pr.status, pr.decided_at, pr.applied_version = "approved", self._now(), it.current_version
        NotificationService(self.db).notify(
            it.user_id, "itinerary_adapted", f"{it.title} updated", "; ".join(summary).capitalize() + ".",
            f"adaptation:applied:{pr.id}", {"itinerary_id": str(it.id), "proposal_id": str(pr.id)})
        self.db.commit()
        return self.itineraries.to_out(it)
