"""Optimisation previews and their (explicit) application to a saved itinerary."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError, not_found
from app.integrations.routing.base import RoutingProvider
from app.integrations.routing.providers import get_routing
from app.models.catalog import Destination
from app.models.itinerary import Itinerary, ItineraryActivity
from app.models.optimization import OptimizationRun
from app.models.user import User
from app.modules.itinerary.service import ItineraryService, _candidate
from app.modules.routing import optimizer as op
from app.modules.routing.explain import explain as explain_changes
from app.modules.routing.explain import pct
from app.schemas.optimization import OptimizationOut, OptimizeRequest, PlanDay, PlanStop, PlanView


class OptimizationService:
    def __init__(self, db: Session, routing: RoutingProvider | None = None):
        self.db = db
        self.routing = routing if routing is not None else get_routing()
        self.itineraries = ItineraryService(db, routing=self.routing)

    def _plan_view(
        self,
        it: Itinerary,
        days: list[list[str]],
        acts: dict[str, ItineraryActivity],
        metrics: dict,
        times: dict[str, ItineraryActivity] | None = None,
    ) -> dict:
        out_days = []
        for d, ids in enumerate(days, 1):
            stops = []
            for i in ids:
                a = acts[i]
                stops.append(
                    {
                        "id": str(a.id),
                        "name": a.attraction.name,
                        "lat": float(a.attraction.latitude),
                        "lng": float(a.attraction.longitude),
                        "start_time": None,
                        "duration_min": a.duration_min,
                        "travel_min": None,
                        "travel_m": None,
                        "locked": a.locked,
                    }
                )
            out_days.append({"day": d, "stops": stops})
        return {"days": out_days, "metrics": metrics}

    def preview(self, user: User, itinerary_id: uuid.UUID, req: OptimizeRequest) -> OptimizationOut:
        it = self.itineraries._own(user, itinerary_id)
        if not it.activities:
            raise AppError(422, "empty_itinerary", "Add activities before optimizing")
        d = self.db.get(Destination, it.destination_id)
        p = self.itineraries._params(it, d)
        acts = sorted(it.activities, key=lambda a: (a.day_number, a.position))
        by_row = {str(a.id): a for a in acts}
        opt = [
            op.OptActivity(
                id=str(a.id),
                name=a.attraction.name,
                lat=float(a.attraction.latitude),
                lng=float(a.attraction.longitude),
                duration_min=a.duration_min,
                cost_total_minor=None if a.cost_minor is None else a.cost_minor * it.traveler_count,
                score=a.score or 0.0,
                locked=a.locked or a.source == "user",
                candidate=_candidate(a.attraction, a.score or 0.0, a.duration_min, a.cost_minor),
            )
            for a in acts
        ]
        # the candidate id must equal the activity id so the scheduler/validator share identifiers
        for o in opt:
            o.candidate.id = o.id
        by_opt = {o.id: o for o in opt}
        pts = [p.start] + [(o.lat, o.lng) for o in opt]
        matrix = self.routing.matrix(pts)
        p.leg = op.leg_from_matrix(pts, matrix)

        before_days = [[str(a.id) for a in acts if a.day_number == day] for day in range(1, it.days + 1)]
        before = op.evaluate(before_days, by_opt, p)
        w = op.OptWeights(**req.weights.model_dump())
        result = op.optimize(opt, p, matrix, w, improve=req.improve, time_limit_ms=req.time_limit_ms)
        names = {o.id: o.name for o in opt}
        notes = list(result.notes) + list(matrix.notes)
        after = None
        changes: list[str] = []
        delta = None
        if result.status != "infeasible":
            after = op.evaluate(result.days, by_opt, p)
            changes = explain_changes(before_days, result.days, names, before, after, result.dropped)
            delta = {
                "distance_m": after["distance_m"] - before["distance_m"],
                "distance_pct": pct(before["distance_m"], after["distance_m"]),
                "travel_min": after["travel_min"] - before["travel_min"],
                "travel_pct": pct(before["travel_min"], after["travel_min"]),
                "violations": len(after["violations"]) - len(before["violations"]),
                "activities": after["n_activities"] - before["n_activities"],
            }
        else:
            changes = [
                "No change was possible: " + (result.notes[-1] if result.notes else "the constraints cannot be met.")
            ]
        run = OptimizationRun(
            itinerary_id=it.id,
            user_id=user.id,
            status=result.status,
            base_version=it.current_version,
            weights=w.to_dict(),
            routing={
                "source": matrix.source,
                "notes": matrix.notes,
                "live_traffic": matrix.live_traffic,
                "fetched_at": matrix.fetched_at.isoformat(),
            },
            before=self._plan_view(it, before_days, by_row, before),
            after=self._plan_view(it, result.days, by_row, after)
            if after is not None and result.status != "infeasible"
            else None,
            changes=changes,
            dropped=[{"id": i, "name": names.get(i, i), "reason": r} for i, r in result.dropped],
            notes=notes,
            solver_ms=round(result.solver_ms, 2),
        )
        self.db.add(run)
        self.db.commit()
        return self._out(run, delta)

    def _out(self, r: OptimizationRun, delta: dict | None = None) -> OptimizationOut:
        if delta is None and r.after:
            b, a = r.before["metrics"], r.after["metrics"]
            delta = {
                "distance_m": a["distance_m"] - b["distance_m"],
                "distance_pct": pct(b["distance_m"], a["distance_m"]),
                "travel_min": a["travel_min"] - b["travel_min"],
                "travel_pct": pct(b["travel_min"], a["travel_min"]),
                "violations": len(a["violations"]) - len(b["violations"]),
                "activities": a["n_activities"] - b["n_activities"],
            }
        return OptimizationOut(
            id=r.id,
            itinerary_id=r.itinerary_id,
            status=r.status,
            applied=r.applied,
            base_version=r.base_version,
            weights=r.weights,
            routing=r.routing,
            before=PlanView(
                days=[PlanDay(day=x["day"], stops=[PlanStop(**s) for s in x["stops"]]) for x in r.before["days"]],
                metrics=r.before["metrics"],
            ),
            after=None
            if r.after is None
            else PlanView(
                days=[PlanDay(day=x["day"], stops=[PlanStop(**s) for s in x["stops"]]) for x in r.after["days"]],
                metrics=r.after["metrics"],
            ),
            delta=delta,
            changes=r.changes,
            dropped=r.dropped,
            notes=r.notes,
            solver_ms=r.solver_ms,
            created_at=r.created_at,
            applied_at=r.applied_at,
        )

    def _run(self, user: User, run_id: uuid.UUID) -> OptimizationRun:
        r = self.db.scalar(
            select(OptimizationRun).where(OptimizationRun.id == run_id, OptimizationRun.user_id == user.id)
        )
        if r is None:
            raise not_found("Optimization")
        return r

    def get(self, user: User, run_id: uuid.UUID) -> OptimizationOut:
        return self._out(self._run(user, run_id))

    def history(self, user: User, itinerary_id: uuid.UUID) -> list[OptimizationOut]:
        it = self.itineraries._own(user, itinerary_id)
        rows = self.db.scalars(
            select(OptimizationRun)
            .where(OptimizationRun.itinerary_id == it.id)
            .order_by(OptimizationRun.created_at.desc())
        )
        return [self._out(r) for r in rows]

    def apply(self, user: User, run_id: uuid.UUID):
        r = self._run(user, run_id)
        it = self.itineraries._own(user, r.itinerary_id)
        if r.applied:
            raise AppError(409, "already_applied", "This optimization was already applied")
        if r.status == "infeasible" or r.after is None:
            raise AppError(409, "nothing_to_apply", "This optimization found no feasible change")
        if it.current_version != r.base_version:
            raise AppError(
                409, "stale_optimization", "The itinerary changed after this preview; run the optimization again"
            )
        rows = {str(a.id): a for a in it.activities}
        keep: set[str] = set()
        for day in r.after["days"]:
            for pos, stop in enumerate(day["stops"], 1):
                a = rows[stop["id"]]
                a.day_number, a.position = day["day"], pos
                keep.add(stop["id"])
        for rid, a in rows.items():
            if rid not in keep:
                self.db.delete(a)  # optional activities the optimizer dropped (listed in the preview)
        self.db.flush()
        self.db.refresh(it)
        self.itineraries._reschedule(it)
        b, a = r.before["metrics"], r.after["metrics"]
        self.itineraries._new_version(
            it,
            user,
            f"Optimized route: {pct(b['distance_m'], a['distance_m'])} distance, {pct(b['travel_min'], a['travel_min'])} travel time",
        )
        r.applied, r.applied_at = True, datetime.now(UTC)
        self.db.commit()
        return self.itineraries.to_out(it)
