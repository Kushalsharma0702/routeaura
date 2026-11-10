"""Context-aware adaptation: freshness, detection, alternatives and proposal simulation. Pure functions.

Rules of the road
* Only configured providers or explicit traveler reports create context. Nothing is inferred or invented.
* Stale context (older than `max_age_min`) is never acted on; it is reported as stale instead.
* Every issue carries its source and fetch time so the UI can show provenance.
* Detection proposes; it never changes a plan. Applying a proposal needs the traveler's approval.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from app.integrations.weather.base import DayForecast
from app.modules.itinerary import planner as pl
from app.modules.spatial.geo import haversine_m


@dataclass(frozen=True)
class Thresholds:
    rain_prob: float = 60.0  # percent
    rain_mm: float = 5.0
    heat_c: float = 40.0
    max_age_min: int = 180


@dataclass
class Stop:
    """An itinerary activity as the engine sees it."""

    id: str
    attraction_id: str
    name: str
    lat: float
    lng: float
    category: str
    is_outdoor: bool
    duration_min: int
    cost_minor: int | None
    score: float
    locked: bool
    candidate: pl.Candidate


@dataclass
class Issue:
    type: str  # rain | heat | closure | delay | over_budget
    day: int
    activity_id: str | None
    evidence: str
    source: str
    fetched_at: str | None
    extra: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "type": self.type,
            "day": self.day,
            "activity_id": self.activity_id,
            "evidence": self.evidence,
            "source": self.source,
            "fetched_at": self.fetched_at,
            **({"extra": self.extra} if self.extra else {}),
        }


def is_fresh(fetched_at: datetime, now: datetime, max_age_min: int) -> bool:
    return timedelta(0) <= now - fetched_at <= timedelta(minutes=max_age_min)


def detect_weather(
    days: dict[int, list[Stop]], forecasts: dict[int, DayForecast], now: datetime, th: Thresholds
) -> tuple[list[Issue], list[int], list[str]]:
    """(issues, stale_days, notes). Unknown forecast values never trigger anything."""
    issues: list[Issue] = []
    stale: list[int] = []
    notes: list[str] = []
    for day, fc in sorted(forecasts.items()):
        if not is_fresh(fc.fetched_at, now, th.max_age_min):
            stale.append(day)
            continue
        if fc.precip_prob is None and fc.precip_mm is None and fc.temp_max_c is None:
            notes.append(
                f"Day {day}: the provider returned no forecast values (probably beyond its forecast horizon); nothing was assumed."
            )
            continue
        stamp = f"{fc.source}, fetched {fc.fetched_at.strftime('%H:%M')} UTC"
        rainy = (fc.precip_prob is not None and fc.precip_prob >= th.rain_prob) or (
            fc.precip_mm is not None and fc.precip_mm >= th.rain_mm
        )
        hot = fc.temp_max_c is not None and fc.temp_max_c >= th.heat_c
        for s in days.get(day, []):
            if not s.is_outdoor:
                continue
            if rainy:
                bits = [
                    x
                    for x in (
                        f"{fc.precip_prob:.0f}% chance of rain" if fc.precip_prob is not None else None,
                        f"{fc.precip_mm:.1f} mm expected" if fc.precip_mm is not None else None,
                    )
                    if x
                ]
                issues.append(
                    Issue("rain", day, s.id, f"{', '.join(bits)} ({stamp})", fc.source, fc.fetched_at.isoformat())
                )
            elif hot:
                issues.append(
                    Issue(
                        "heat",
                        day,
                        s.id,
                        f"forecast high of {fc.temp_max_c:.0f}°C ({stamp})",
                        fc.source,
                        fc.fetched_at.isoformat(),
                    )
                )
    return issues, stale, notes


def detect_verified_closures(days: dict[int, list[Stop]], start_date: date | None) -> list[Issue]:
    """Closures known from ADMIN-VERIFIED weekly hours (never guessed). Needs trip dates."""
    if start_date is None:
        return []
    out = []
    for day, stops in days.items():
        status_date = start_date + timedelta(days=day - 1)
        for s in stops:
            status, _ = pl.hours_window(s.candidate, status_date)
            if status == "verified_closed":
                out.append(
                    Issue(
                        "closure",
                        day,
                        s.id,
                        f"{s.name} is closed on {status_date.strftime('%A')} according to verified opening hours",
                        "verified_hours",
                        None,
                    )
                )
    return out


def distance_m(a: Stop | pl.Candidate, b: Stop | pl.Candidate) -> float:
    return haversine_m(a.lat, a.lng, b.lat, b.lng)


def rank_alternatives(
    replaced: Stop,
    pool: list[Stop],
    *,
    day: int,
    start_date: date | None,
    indoor_only: bool = False,
    max_cost_minor: int | None = None,
    limit: int = 3,
) -> list[tuple[Stop, str]]:
    """Alternatives from published attractions not already in the trip. Verified-closed ones are excluded;
    unknown hours are allowed but flagged. Ranked by (same category, relevance, proximity, name)."""
    day_date = start_date + timedelta(days=day - 1) if start_date else None
    scored = []
    for c in pool:
        if c.attraction_id == replaced.attraction_id:
            continue
        if indoor_only and c.is_outdoor:
            continue
        if max_cost_minor is not None and (c.cost_minor is None or c.cost_minor > max_cost_minor):
            continue
        status, _ = pl.hours_window(c.candidate, day_date)
        if status == "verified_closed":
            continue
        why = []
        if c.category == replaced.category:
            why.append(f"same category ({c.category})")
        why.append(f"{distance_m(replaced, c) / 1000:.1f} km from {replaced.name}")
        if indoor_only:
            why.append("indoor")
        if max_cost_minor is not None:
            why.append("known lower cost")
        why.append("opening hours verified" if status == "verified_open" else "opening hours not verified")
        scored.append(((c.category != replaced.category, -c.score, distance_m(replaced, c), c.name), c, ", ".join(why)))
    scored.sort(key=lambda x: x[0])
    return [(c, w) for _, c, w in scored[:limit]]


def simulate(days: dict[int, list[Stop]], p: pl.PlanParams) -> dict:
    """Schedule the (modified) plan with the app's planner and report violations and budget."""
    scheds = [pl.schedule_day(d, [s.candidate for s in stops], p) for d, stops in sorted(days.items())]
    by_id = {s.candidate.id: s.candidate for stops in days.values() for s in stops}
    summary, viols = pl.validate(scheds, by_id, p)
    return {
        "days": [{"day": d, "stops": [s.name for s in stops]} for d, stops in sorted(days.items())],
        "violations": [{"type": v.type, "day": v.day, "message": v.message} for v in viols],
        "budget": summary,
        "travel_min": sum(sl.travel_min for sch in scheds for sl in sch.slots),
    }


def plan_delay(
    stops_today: list[Stop], completed: set[str], current_min: int, day: int, next_day_has_room: bool, p: pl.PlanParams
) -> tuple[list[dict], list[str]]:
    """Re-plan the rest of a day starting at `current_min`. Returns (changes, notes). If the remaining plan overruns
    the day or misses opening hours, unlocked low-relevance activities are moved to the next day (if it has room)
    or removed, until the day is feasible. Locked activities are never touched."""
    remaining = [s for s in stops_today if s.id not in completed]
    if not remaining:
        return [], ["Nothing is left to do today."]
    q = pl.PlanParams(**{**p.__dict__, "day_start_min": max(current_min, p.day_start_min)})
    changes: list[dict] = []
    keep = list(remaining)
    while True:
        sched = pl.schedule_day(day, [s.candidate for s in keep], q)
        if not sched.violations:
            break
        victims = sorted((s for s in keep if not s.locked), key=lambda s: (s.score, s.name))
        if not victims:
            return changes, [
                "Locked activities cannot all fit in the remaining time; nothing more can be changed automatically."
            ]
        v = victims[0]
        keep.remove(v)
        if next_day_has_room:
            changes.append(
                {
                    "action": "move",
                    "activity_id": v.id,
                    "name": v.name,
                    "from_day": day,
                    "to_day": day + 1,
                    "reason": "running late: it no longer fits today, moved to the next day",
                }
            )
        else:
            changes.append(
                {
                    "action": "remove",
                    "activity_id": v.id,
                    "name": v.name,
                    "day": day,
                    "reason": "running late: it no longer fits today and the next day has no room",
                }
            )
    return changes, []


def pick_replacement(
    days: dict[int, list[Stop]],
    old: Stop,
    alts: list[tuple[Stop, str]],
    p: pl.PlanParams,
    taken: set[str] | frozenset[str] = frozenset(),
) -> tuple[Stop, str, int] | None:
    """Choose the alternative whose plan has the FEWEST violations (day overrun, opening hours, budget), keeping the
    ranking order as the tie-break. Returns (stop, why, violations_introduced) or None. A proposal that cannot avoid
    violations is still returned (its preview shows them) so the traveler decides with full information."""
    best: tuple[tuple[int, int], Stop, str, int] | None = None
    for rank, (alt, why) in enumerate(alts):
        if alt.attraction_id in taken:
            continue
        new = {d: [alt if s.id == old.id else s for s in ss] for d, ss in days.items()}
        viol = len(simulate(new, p)["violations"])
        if best is None or (viol, rank) < best[0]:
            best = ((viol, rank), alt, why, viol)
    return None if best is None else (best[1], best[2], best[3])
