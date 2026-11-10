"""Itinerary generation, persistence and management. Ownership is enforced on every method: another
user's itinerary is indistinguishable from a missing one (404)."""

from __future__ import annotations

import time
import uuid
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import AppError, not_found
from app.integrations.llm.base import LLMClient, LLMError
from app.integrations.llm.providers import get_llm
from app.models.catalog import Attraction, Destination
from app.models.itinerary import Itinerary, ItineraryActivity, ItineraryVersion
from app.models.user import User
from app.modules.itinerary import llm_planning as lp
from app.modules.itinerary import planner as pl
from app.modules.recommendations.service import RecommendationService
from app.schemas.itinerary import (
    ActivityOut,
    AddActivity,
    AttractionBrief,
    DayOut,
    DestinationBrief,
    ItineraryOut,
    ItinerarySummary,
    ItineraryUpdate,
    RegenerateRequest,
    ReorderRequest,
    TripRequest,
    UpdateActivity,
    VersionDetail,
    VersionOut,
    ViolationOut,
)

LLM_POOL_EXTRA = 4  # candidates offered to the LLM beyond what could fit


def _hhmm(m: int) -> str:
    return f"{m // 60:02d}:{m % 60:02d}"


def _candidate(
    a: Attraction, score: float = 0.0, duration: int | None = None, cost: int | None | str = "attr"
) -> pl.Candidate:
    verified = a.opening_hours if a.opening_hours_source in ("admin", "provider") else None
    return pl.Candidate(
        id=str(a.id),
        name=a.name,
        lat=float(a.latitude),
        lng=float(a.longitude),
        duration_min=duration or a.typical_duration_minutes,
        cost_minor=a.estimated_cost_minor if cost == "attr" else cost,
        score=score,
        category=a.category.slug,
        is_outdoor=a.is_outdoor,
        opening_hours=verified,
    )


class ItineraryService:
    def __init__(self, db: Session, llm: LLMClient | None = None):
        self.db = db
        self.llm = llm if llm is not None else get_llm()
        self.rec = RecommendationService(db)

    # ------------------------------------------------------------------ access
    def _own(self, user: User, itinerary_id: uuid.UUID) -> Itinerary:
        it = self.db.scalar(
            select(Itinerary).where(
                Itinerary.id == itinerary_id, Itinerary.user_id == user.id, Itinerary.deleted_at.is_(None)
            )
        )
        if it is None:
            raise not_found("Itinerary")
        return it

    def _destination(self, destination_id: uuid.UUID) -> Destination:
        d = self.db.get(Destination, destination_id)
        if d is None or d.deleted_at is not None or not d.is_published:
            raise AppError(422, "unknown_destination", "Destination not found or not published")
        return d

    def _attractions(self, d: Destination) -> list[Attraction]:
        return list(
            self.db.scalars(
                select(Attraction)
                .where(
                    Attraction.destination_id == d.id,
                    Attraction.is_published.is_(True),
                    Attraction.deleted_at.is_(None),
                )
                .order_by(Attraction.name)
            )
        )

    # ------------------------------------------------------------------ params
    def _params(self, it: Itinerary, d: Destination) -> pl.PlanParams:
        start = None
        if it.start_location:
            start = (it.start_location["lat"], it.start_location["lng"])
        else:
            start = (float(d.latitude), float(d.longitude))
        return pl.PlanParams(
            days=it.days,
            start_date=it.start_date,
            travelers=it.traveler_count,
            budget_total_minor=it.budget_total_minor,
            living_per_day_minor=d.estimated_cost_per_day_minor,
            start=start,
        )

    # ------------------------------------------------------------------ generate
    def generate(self, user: User, req: TripRequest) -> ItineraryOut:
        steps: list[dict] = []
        notes: list[str] = []

        def step(name: str, started: float, status: str = "ok", detail: str = "") -> None:
            steps.append(
                {
                    "step": name,
                    "status": status,
                    "ms": round((time.perf_counter() - started) * 1000, 1),
                    "detail": detail,
                }
            )

        t = time.perf_counter()
        d = self._destination(req.destination_id)
        days, budget, travelers = req.days, req.budget_total_minor, req.travelers
        interests, style = req.interests, req.travel_style
        if req.prompt:
            if req.use_llm and self.llm.name != "none":
                try:
                    intent = lp.interpret_intent(self.llm, req.prompt)
                    days = days or intent.days
                    if budget is None and intent.budget_total_inr is not None:
                        budget = int(intent.budget_total_inr * 100)
                    travelers = travelers if travelers != 1 or not intent.travelers else intent.travelers
                    interests = interests if interests is not None else intent.interests
                    style = style or intent.travel_style
                    notes.append(
                        "Trip details were read from your message by an AI model and checked against the form fields."
                    )
                except (LLMError, lp.LLMOutputError) as exc:
                    notes.append(
                        f"Could not interpret the message with the AI model ({type(exc).__name__}); "
                        "only the form fields were used."
                    )
            else:
                notes.append(
                    "A free-text request was given but no AI provider is configured; only the form fields were used."
                )
        if not days:
            raise AppError(422, "validation_error", "Trip length is required: provide days or dates")
        if not 1 <= days <= 14:
            raise AppError(422, "validation_error", "A trip must be between 1 and 14 days")
        attractions = self._attractions(d)
        if not attractions:
            raise AppError(422, "no_attractions", "This destination has no published attractions to plan with")
        step("validate", t, detail=f"{days} days, {travelers} traveler(s)")

        it = Itinerary(
            user_id=user.id,
            destination_id=d.id,
            title=(req.title or f"{days}-day trip to {d.name}").strip(),
            status="draft",
            start_date=req.start_date,
            days=days,
            traveler_count=travelers,
            budget_total_minor=budget,
            interests=list(interests or []),
            travel_style=style,
            accommodation_preference=req.accommodation_preference,
            start_location=req.start_location.model_dump() if req.start_location else None,
            generation_source="deterministic_fallback",
            generation_info={},
        )
        self._plan_into(it, d, attractions, steps, notes, use_llm=req.use_llm and self.llm.name != "none", user=user)
        self.db.add(it)
        self.db.flush()
        self._persist_activities(it)
        self._new_version(it, user, "Generated")
        t = time.perf_counter()
        self.db.commit()
        step("save", t)
        it.generation_info = {**it.generation_info, "steps": steps}
        self.db.commit()
        return self.to_out(it)

    def _plan_into(
        self,
        it: Itinerary,
        d: Destination,
        attractions: list[Attraction],
        steps: list[dict],
        notes: list[str],
        *,
        use_llm: bool,
        user: User,
    ) -> None:
        """Rank, plan and schedule; fills `it` (pending activities in it._pending) and generation_info."""
        p = self._params(it, d)
        t = time.perf_counter()
        per_day = None
        if it.budget_total_minor is not None:
            per_day = int(it.budget_total_minor / (it.days * it.traveler_count))
        scored, rec_notes = self.rec.score_attractions(
            user, d, attractions, interests=it.interests or None, style=it.travel_style, budget_per_day_minor=per_day
        )
        notes.extend(rec_notes)
        cands = [_candidate(a, scored[str(a.id)].score) for a in attractions]
        by_id = {c.id: c for c in cands}
        steps.append(
            {
                "step": "rank_attractions",
                "status": "ok",
                "ms": round((time.perf_counter() - t) * 1000, 1),
                "detail": f"{len(cands)} published attractions scored by the recommendation engine",
            }
        )

        t = time.perf_counter()
        source, schedules, dropped, themes = "deterministic_fallback", None, [], {}
        llm_info: dict = {"provider": self.llm.name, "model": self.llm.model}
        if use_llm:
            pool_size = it.days * p.max_per_day + LLM_POOL_EXTRA
            pool = sorted(cands, key=lambda c: (-c.score, c.id))[:pool_size]
            try:
                plan = lp.propose_plan(self.llm, pool, p, it.interests or [], it.travel_style)
                # keep day numbers aligned: days the model skipped become empty groups
                aligned: list[list[pl.Candidate]] = [[] for _ in range(p.days)]
                for day in plan.days:
                    aligned[day.day - 1] = [by_id[a] for a in day.attraction_ids]
                schedules, dropped = pl.pack_groups(aligned, p)
                themes = {day.day: {"theme": day.theme, "rationale": day.rationale} for day in plan.days}
                source = "llm"
                steps.append(
                    {
                        "step": "llm_plan",
                        "status": "ok",
                        "ms": round((time.perf_counter() - t) * 1000, 1),
                        "detail": "AI proposal validated, then scheduled by deterministic code",
                    }
                )
            except (LLMError, lp.LLMOutputError) as exc:
                msg = (
                    f"AI planning unavailable ({type(exc).__name__}: {str(exc)[:120]}); used the deterministic planner."
                )
                notes.append(msg)
                llm_info["error"] = msg
                steps.append(
                    {
                        "step": "llm_plan",
                        "status": "failed",
                        "ms": round((time.perf_counter() - t) * 1000, 1),
                        "detail": msg,
                    }
                )
        if schedules is None:
            t = time.perf_counter()
            schedules, dropped = pl.plan_deterministic(cands, p)
            steps.append(
                {
                    "step": "deterministic_plan",
                    "status": "ok",
                    "ms": round((time.perf_counter() - t) * 1000, 1),
                    "detail": "nearest-neighbour ordering, first-fit day packing, opening-hour and budget checks",
                }
            )
        else:
            notes.append(
                "Day groupings were suggested by an AI model; times, costs and constraints were computed by the app."
            )
        if source == "deterministic_fallback":
            notes.append("This itinerary was generated by the app's deterministic planner (no AI model was used).")

        it.generation_source = source
        it.generation_info = {
            "llm": llm_info,
            "notes": notes,
            "themes": themes,
            "dropped": [{"attraction": c.name, "reason": r} for c, r in dropped],
            "travel_times": "estimates (great-circle x 1.3 / 30 km/h), not live routing",
            "steps": steps,
        }
        it._pending = (schedules, by_id, scored)  # type: ignore[attr-defined]

    # ------------------------------------------------------------------ persistence of activities
    def _persist_activities(self, it: Itinerary) -> None:
        schedules, by_id, scored = it._pending  # type: ignore[attr-defined]
        attrs = {
            str(a.id): a
            for a in self.db.scalars(select(Attraction).where(Attraction.id.in_([uuid.UUID(k) for k in by_id])))
        }
        themes = (it.generation_info or {}).get("themes", {})
        for s in schedules:
            for sl in s.slots:
                sc = scored.get(sl.candidate_id)
                expl = {
                    "reasons": sc.reasons if sc else [],
                    "cautions": sc.cautions if sc else [],
                    "missing": sc.missing if sc else [],
                    "notes": sl.notes,
                }
                th = themes.get(s.day) or themes.get(str(s.day))
                if th:
                    expl["llm"] = th
                c = by_id[sl.candidate_id]
                self.db.add(
                    ItineraryActivity(
                        itinerary_id=it.id,
                        attraction_id=uuid.UUID(sl.candidate_id),
                        day_number=s.day,
                        position=sl.position,
                        start_min=sl.start_min,
                        duration_min=sl.duration_min,
                        travel_min=sl.travel_min,
                        travel_m=sl.travel_m,
                        wait_min=sl.wait_min,
                        cost_minor=c.cost_minor,
                        hours_status=sl.hours_status,
                        source="generated",
                        score=round(sc.score, 4) if sc else None,
                        explanation=expl,
                    )
                )
        del attrs
        self.db.flush()
        self.db.refresh(it)
        del it._pending  # type: ignore[attr-defined]

    def _reschedule(self, it: Itinerary) -> None:
        """Recompute start times/travel for every day from the current activity order (user order is kept)."""
        d = self.db.get(Destination, it.destination_id)
        p = self._params(it, d)
        by_day: dict[int, list[ItineraryActivity]] = {}
        for a in sorted(it.activities, key=lambda a: (a.day_number, a.position)):
            by_day.setdefault(a.day_number, []).append(a)
        for day, acts in by_day.items():
            cands = [_candidate(a.attraction, a.score or 0.0, a.duration_min, a.cost_minor) for a in acts]
            sched = pl.schedule_day(day, cands, p)
            for pos, (a, sl) in enumerate(zip(acts, sched.slots, strict=True), 1):
                a.position, a.start_min, a.travel_min, a.travel_m = pos, sl.start_min, sl.travel_min, sl.travel_m
                a.wait_min, a.hours_status = sl.wait_min, sl.hours_status
        self.db.flush()

    # ------------------------------------------------------------------ versions
    def _snapshot(self, it: Itinerary) -> dict:
        return {
            "title": it.title,
            "status": it.status,
            "start_date": it.start_date.isoformat() if it.start_date else None,
            "days": it.days,
            "traveler_count": it.traveler_count,
            "budget_total_minor": it.budget_total_minor,
            "activities": [
                {
                    "attraction_id": str(a.attraction_id),
                    "day_number": a.day_number,
                    "position": a.position,
                    "duration_min": a.duration_min,
                    "cost_minor": a.cost_minor,
                    "source": a.source,
                    "score": a.score,
                    "explanation": a.explanation,
                    "notes": a.notes,
                }
                for a in sorted(it.activities, key=lambda a: (a.day_number, a.position))
            ],
        }

    def _new_version(self, it: Itinerary, user: User, summary: str) -> None:
        nxt = (
            self.db.scalar(select(func.max(ItineraryVersion.version)).where(ItineraryVersion.itinerary_id == it.id))
            or 0
        ) + 1
        it.current_version = nxt
        self.db.add(
            ItineraryVersion(
                itinerary_id=it.id, version=nxt, summary=summary[:200], snapshot=self._snapshot(it), created_by=user.id
            )
        )
        self.db.flush()

    def versions(self, user: User, itinerary_id: uuid.UUID) -> list[VersionOut]:
        it = self._own(user, itinerary_id)
        rows = self.db.scalars(
            select(ItineraryVersion)
            .where(ItineraryVersion.itinerary_id == it.id)
            .order_by(ItineraryVersion.version.desc())
        )
        return [VersionOut(version=v.version, summary=v.summary, created_at=v.created_at) for v in rows]

    def version_detail(self, user: User, itinerary_id: uuid.UUID, version: int) -> VersionDetail:
        it = self._own(user, itinerary_id)
        v = self.db.scalar(
            select(ItineraryVersion).where(ItineraryVersion.itinerary_id == it.id, ItineraryVersion.version == version)
        )
        if v is None:
            raise not_found("Version")
        return VersionDetail(version=v.version, summary=v.summary, created_at=v.created_at, snapshot=v.snapshot)

    def restore(self, user: User, itinerary_id: uuid.UUID, version: int) -> ItineraryOut:
        it = self._own(user, itinerary_id)
        v = self.version_detail(user, itinerary_id, version)
        snap = v.snapshot
        valid = {
            str(a.id)
            for a in self.db.scalars(
                select(Attraction).where(
                    Attraction.id.in_([uuid.UUID(x["attraction_id"]) for x in snap["activities"]]),
                    Attraction.deleted_at.is_(None),
                )
            )
        }
        for a in list(it.activities):
            self.db.delete(a)
        self.db.flush()
        it.title, it.status, it.days = snap["title"], snap["status"], snap["days"]
        it.traveler_count, it.budget_total_minor = snap["traveler_count"], snap["budget_total_minor"]
        it.start_date = date.fromisoformat(snap["start_date"]) if snap["start_date"] else None
        skipped = 0
        for x in snap["activities"]:
            if x["attraction_id"] not in valid:
                skipped += 1
                continue
            self.db.add(
                ItineraryActivity(
                    itinerary_id=it.id,
                    attraction_id=uuid.UUID(x["attraction_id"]),
                    day_number=x["day_number"],
                    position=x["position"],
                    start_min=540,
                    duration_min=x["duration_min"],
                    cost_minor=x["cost_minor"],
                    source=x["source"],
                    score=x["score"],
                    explanation=x["explanation"],
                    notes=x["notes"],
                )
            )
        self.db.flush()
        self.db.refresh(it)
        self._reschedule(it)
        self._new_version(
            it, user, f"Restored version {version}" + (f" ({skipped} removed attractions skipped)" if skipped else "")
        )
        self.db.commit()
        return self.to_out(it)

    # ------------------------------------------------------------------ management
    def list(self, user: User, page: int, page_size: int) -> tuple[list[ItinerarySummary], int]:
        base = select(Itinerary).where(Itinerary.user_id == user.id, Itinerary.deleted_at.is_(None))
        total = self.db.scalar(select(func.count()).select_from(base.subquery())) or 0
        rows = self.db.scalars(
            base.order_by(Itinerary.updated_at.desc(), Itinerary.id).offset((page - 1) * page_size).limit(page_size)
        ).all()
        out = []
        for it in rows:
            dest = self.db.get(Destination, it.destination_id)
            out.append(
                ItinerarySummary(
                    id=it.id,
                    title=it.title,
                    status=it.status,
                    destination_name=dest.name,
                    start_date=it.start_date,
                    days=it.days,
                    traveler_count=it.traveler_count,
                    activity_count=len(it.activities),
                    generation_source=it.generation_source,
                    current_version=it.current_version,
                    updated_at=it.updated_at,
                )
            )
        return out, total

    def get(self, user: User, itinerary_id: uuid.UUID) -> ItineraryOut:
        return self.to_out(self._own(user, itinerary_id))

    def update(self, user: User, itinerary_id: uuid.UUID, data: ItineraryUpdate) -> ItineraryOut:
        it = self._own(user, itinerary_id)
        changes = data.model_dump(exclude_unset=True)
        if "title" in changes and changes["title"] is None:
            raise AppError(422, "validation_error", "title cannot be null")
        for k in ("status", "traveler_count"):
            if k in changes and changes[k] is None:
                raise AppError(422, "validation_error", f"{k} cannot be null")
        if changes.get("start_date") and changes["start_date"] < date.today():
            raise AppError(422, "validation_error", "start_date cannot be in the past")
        for k, v in changes.items():
            setattr(it, k, v)
        if {"start_date", "traveler_count"} & set(changes):
            self._reschedule(it)
        self._new_version(it, user, "Updated trip details: " + ", ".join(sorted(changes)) if changes else "No changes")
        self.db.commit()
        return self.to_out(it)

    def delete(self, user: User, itinerary_id: uuid.UUID) -> None:
        from datetime import UTC, datetime

        it = self._own(user, itinerary_id)
        it.deleted_at = datetime.now(UTC)
        self.db.commit()

    def regenerate(self, user: User, itinerary_id: uuid.UUID, req: RegenerateRequest) -> ItineraryOut:
        it = self._own(user, itinerary_id)
        d = self._destination(it.destination_id)
        for a in list(it.activities):
            self.db.delete(a)
        self.db.flush()
        if req.interests is not None:
            it.interests = req.interests
        if req.travel_style is not None:
            it.travel_style = req.travel_style
        if req.budget_total_minor is not None:
            it.budget_total_minor = req.budget_total_minor
        steps: list[dict] = []
        notes: list[str] = []
        self._plan_into(
            it, d, self._attractions(d), steps, notes, use_llm=req.use_llm and self.llm.name != "none", user=user
        )
        self._persist_activities(it)
        self._new_version(it, user, "Regenerated")
        self.db.commit()
        it.generation_info = {**it.generation_info, "steps": steps}
        self.db.commit()
        return self.to_out(it)

    def add_activity(self, user: User, itinerary_id: uuid.UUID, data: AddActivity) -> ItineraryOut:
        it = self._own(user, itinerary_id)
        if data.day_number > it.days:
            raise AppError(422, "validation_error", f"day_number must be within the {it.days}-day trip")
        a = self.db.get(Attraction, data.attraction_id)
        if a is None or a.deleted_at is not None or not a.is_published or a.destination_id != it.destination_id:
            raise AppError(422, "unknown_attraction", "Attraction not found in this trip's destination")
        if any(x.attraction_id == a.id for x in it.activities):
            raise AppError(409, "already_in_itinerary", "This attraction is already in the itinerary")
        day_acts = sorted((x for x in it.activities if x.day_number == data.day_number), key=lambda x: x.position)
        pos = min(data.position or len(day_acts) + 1, len(day_acts) + 1)
        for x in day_acts[pos - 1 :]:
            x.position += 1
        self.db.add(
            ItineraryActivity(
                itinerary_id=it.id,
                attraction_id=a.id,
                day_number=data.day_number,
                position=pos,
                start_min=540,
                duration_min=data.duration_min or a.typical_duration_minutes,
                cost_minor=a.estimated_cost_minor,
                source="user",
                explanation={"reasons": ["Added by you."], "cautions": [], "missing": [], "notes": []},
            )
        )
        self.db.flush()
        self.db.refresh(it)
        self._reschedule(it)
        self._new_version(it, user, f"Added {a.name} to day {data.day_number}")
        self.db.commit()
        return self.to_out(it)

    def _activity(self, it: Itinerary, activity_id: uuid.UUID) -> ItineraryActivity:
        a = next((x for x in it.activities if x.id == activity_id), None)
        if a is None:
            raise not_found("Activity")
        return a

    def remove_activity(self, user: User, itinerary_id: uuid.UUID, activity_id: uuid.UUID) -> ItineraryOut:
        it = self._own(user, itinerary_id)
        a = self._activity(it, activity_id)
        name = a.attraction.name
        self.db.delete(a)
        self.db.flush()
        self.db.refresh(it)
        for day in {x.day_number for x in it.activities}:
            for i, x in enumerate(
                sorted((x for x in it.activities if x.day_number == day), key=lambda x: x.position), 1
            ):
                x.position = i
        self._reschedule(it)
        self._new_version(it, user, f"Removed {name}")
        self.db.commit()
        return self.to_out(it)

    def update_activity(
        self, user: User, itinerary_id: uuid.UUID, activity_id: uuid.UUID, data: UpdateActivity
    ) -> ItineraryOut:
        it = self._own(user, itinerary_id)
        a = self._activity(it, activity_id)
        changes = data.model_dump(exclude_unset=True)
        if changes.get("duration_min") is None and "duration_min" in changes:
            raise AppError(422, "validation_error", "duration_min cannot be null")
        for k, v in changes.items():
            setattr(a, k, v)
        self._reschedule(it)
        self._new_version(it, user, f"Edited {a.attraction.name}")
        self.db.commit()
        return self.to_out(it)

    def reorder(self, user: User, itinerary_id: uuid.UUID, data: ReorderRequest) -> ItineraryOut:
        it = self._own(user, itinerary_id)
        existing = {x.id: x for x in it.activities}
        sent = [aid for d in data.days for aid in d.activity_ids]
        if len(sent) != len(set(sent)) or set(sent) != set(existing):
            raise AppError(422, "validation_error", "reorder must list every activity exactly once")
        if any(d.day_number > it.days for d in data.days) or len({d.day_number for d in data.days}) != len(data.days):
            raise AppError(422, "validation_error", "day numbers must be unique and within the trip")
        for d in data.days:
            for pos, aid in enumerate(d.activity_ids, 1):
                existing[aid].day_number, existing[aid].position = d.day_number, pos
        self._reschedule(it)
        self._new_version(it, user, "Reordered activities")
        self.db.commit()
        return self.to_out(it)

    # ------------------------------------------------------------------ output
    def to_out(self, it: Itinerary) -> ItineraryOut:
        d = self.db.get(Destination, it.destination_id)
        p = self._params(it, d)
        acts = sorted(it.activities, key=lambda a: (a.day_number, a.position))
        cands = {
            str(a.attraction_id): _candidate(a.attraction, a.score or 0.0, a.duration_min, a.cost_minor) for a in acts
        }
        scheds = []
        warn: dict[uuid.UUID, list[str]] = {}
        for day in range(1, it.days + 1):
            day_acts = [a for a in acts if a.day_number == day]
            sched = pl.schedule_day(day, [cands[str(a.attraction_id)] for a in day_acts], p)
            scheds.append(sched)
            for a, sl in zip(day_acts, sched.slots, strict=True):
                if sl.notes:
                    warn[a.id] = list(sl.notes)
        id_for = {str(a.attraction_id): a.id for a in acts}
        summary, viols = pl.validate(scheds, cands, p)
        day_outs = []
        for sched, day in zip(scheds, range(1, it.days + 1), strict=True):
            outs = []
            for a in (x for x in acts if x.day_number == day):
                end = a.start_min + a.duration_min
                outs.append(
                    ActivityOut(
                        id=a.id,
                        attraction=AttractionBrief(
                            id=a.attraction.id,
                            name=a.attraction.name,
                            category=a.attraction.category.name,
                            latitude=float(a.attraction.latitude),
                            longitude=float(a.attraction.longitude),
                            is_outdoor=a.attraction.is_outdoor,
                        ),
                        day_number=day,
                        position=a.position,
                        start_min=a.start_min,
                        end_min=end,
                        start_time=_hhmm(a.start_min),
                        end_time=_hhmm(end),
                        duration_min=a.duration_min,
                        travel_min=a.travel_min,
                        travel_m=a.travel_m,
                        wait_min=a.wait_min,
                        cost_minor=a.cost_minor,
                        cost_total_minor=None if a.cost_minor is None else a.cost_minor * it.traveler_count,
                        hours_status=a.hours_status,
                        source=a.source,
                        score=a.score,
                        explanation=a.explanation or {},
                        notes=a.notes,
                        warnings=warn.get(a.id, []),
                    )
                )
            day_outs.append(
                DayOut(
                    day_number=day,
                    date=(it.start_date + timedelta(days=day - 1)) if it.start_date else None,
                    activities=outs,
                    lunch_start_min=sched.lunch_start_min,
                    ends_at=_hhmm(sched.end_min) if outs else None,
                )
            )
        return ItineraryOut(
            id=it.id,
            title=it.title,
            status=it.status,
            destination=DestinationBrief(
                id=d.id, slug=d.slug, name=d.name, latitude=float(d.latitude), longitude=float(d.longitude)
            ),
            start_date=it.start_date,
            days=it.days,
            traveler_count=it.traveler_count,
            budget_total_minor=it.budget_total_minor,
            currency=it.currency,
            interests=list(it.interests or []),
            travel_style=it.travel_style,
            accommodation_preference=it.accommodation_preference,
            start_location=it.start_location,
            generation_source=it.generation_source,
            generation_info=it.generation_info or {},
            current_version=it.current_version,
            day_plans=day_outs,
            budget=summary,
            violations=[
                ViolationOut(
                    type=v.type,
                    day=v.day,
                    activity_id=id_for.get(v.candidate_id) if v.candidate_id else None,
                    message=v.message,
                )
                for v in viols
            ],
            created_at=it.created_at,
            updated_at=it.updated_at,
        )
