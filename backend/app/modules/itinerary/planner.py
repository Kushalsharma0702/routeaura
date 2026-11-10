"""Deterministic itinerary planning: selection, ordering, day packing, time scheduling and validation.

Pure functions, no database or LLM. The LLM may only *suggest groupings*; every time, duration, cost
and constraint here is computed by this module.

Honesty rules
* Travel times/distances are ESTIMATES (great-circle x detour factor / assumed speed). Wave 2 adds
  routing providers; until then every leg is labelled `estimate`.
* Opening hours are used only when the record carries admin-verified hours AND the trip has dates;
  otherwise the activity is `unknown` (never assumed open or closed).
* Unknown costs are excluded from totals and counted in `unknown_cost_items`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

from app.modules.spatial.geo import haversine_m

DAY_KEYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
DETOUR = 1.3  # road distance ~ 1.3 x great-circle: a rule of thumb, not a measurement


@dataclass
class Candidate:
    id: str
    name: str
    lat: float
    lng: float
    duration_min: int
    cost_minor: int | None = None  # per person; None = unknown
    score: float = 0.0  # recommendation relevance 0-1
    category: str = ""
    is_outdoor: bool = False
    opening_hours: dict | None = None  # admin-verified only; None = unknown


@dataclass
class PlanParams:
    days: int
    start_date: date | None = None
    travelers: int = 1
    budget_total_minor: int | None = None
    living_per_day_minor: int | None = None  # destination estimate per person per day
    start: tuple[float, float] | None = None
    day_start_min: int = 9 * 60
    day_end_min: int = 18 * 60
    lunch_start_min: int = 13 * 60
    lunch_min: int = 60
    speed_kmh: float = 30.0
    max_per_day: int = 5


@dataclass
class Slot:
    candidate_id: str
    day: int
    position: int
    start_min: int
    duration_min: int
    travel_min: int
    travel_m: int
    hours_status: str  # verified_open | verified_closed | unknown
    wait_min: int = 0
    notes: list[str] = field(default_factory=list)

    @property
    def end_min(self) -> int:
        return self.start_min + self.duration_min


@dataclass
class Violation:
    type: str  # day_overrun | opening_hours | budget | max_per_day
    day: int | None
    candidate_id: str | None
    message: str


@dataclass
class DaySchedule:
    day: int
    slots: list[Slot]
    lunch_start_min: int | None
    end_min: int
    violations: list[Violation] = field(default_factory=list)


def travel(a: tuple[float, float], b: tuple[float, float], speed_kmh: float) -> tuple[int, int]:
    """(metres, minutes) ESTIMATE between two points."""
    metres = haversine_m(a[0], a[1], b[0], b[1]) * DETOUR
    return int(metres), max(1, round(metres / 1000.0 / speed_kmh * 60)) if metres > 0 else 0


def _hhmm(t: str) -> int:
    return int(t[:2]) * 60 + int(t[3:])


def hours_window(c: Candidate, day_date: date | None) -> tuple[str, list[tuple[int, int]]]:
    """('verified_open'|'verified_closed'|'unknown', windows). Unknown unless verified hours AND a date exist."""
    if c.opening_hours is None or day_date is None:
        return "unknown", []
    spans = c.opening_hours.get(DAY_KEYS[day_date.weekday()])
    if spans is None:
        return "unknown", []  # nothing recorded for that weekday
    if not spans:
        return "verified_closed", []
    return "verified_open", [(_hhmm(a), _hhmm(b)) for a, b in spans]


def schedule_day(day: int, order: list[Candidate], p: PlanParams) -> DaySchedule:
    """Assign times to an ordered list of activities for one day, inserting a lunch break."""
    day_date = p.start_date + timedelta(days=day - 1) if p.start_date else None
    t = p.day_start_min
    pos = p.start
    lunch_at: int | None = None
    slots: list[Slot] = []
    violations: list[Violation] = []
    for c in order:
        metres, minutes = travel(pos, (c.lat, c.lng), p.speed_kmh) if pos else (0, 0)
        t += minutes
        status, windows = hours_window(c, day_date)
        wait = 0
        notes: list[str] = []
        if status == "verified_open":
            fitting = [(o, cl) for o, cl in windows if t + c.duration_min <= cl or max(t, o) + c.duration_min <= cl]
            if fitting:
                o, _ = fitting[0]
                if t < o:
                    wait, t = o - t, o
            else:
                violations.append(
                    Violation(
                        "opening_hours",
                        day,
                        c.id,
                        f"{c.name}: cannot be visited within its verified opening hours that day",
                    )
                )
        elif status == "verified_closed":
            violations.append(Violation("opening_hours", day, c.id, f"{c.name}: verified closed on that weekday"))
        else:
            notes.append("Opening hours not verified" if day_date else "No travel date set: opening hours not checked")
        if lunch_at is None and t < p.lunch_start_min <= t + c.duration_min:
            lunch_at = t + c.duration_min  # lunch after this activity if it straddles the lunch time
            slot_end = lunch_at
            slots.append(Slot(c.id, day, len(slots) + 1, t, c.duration_min, minutes, metres, status, wait, notes))
            t = slot_end + p.lunch_min
            pos = (c.lat, c.lng)
            continue
        if lunch_at is None and t >= p.lunch_start_min:
            lunch_at, t = t, t + p.lunch_min
        slots.append(Slot(c.id, day, len(slots) + 1, t, c.duration_min, minutes, metres, status, wait, notes))
        t += c.duration_min
        pos = (c.lat, c.lng)
    end = t
    if slots and end > p.day_end_min:
        violations.append(
            Violation(
                "day_overrun",
                day,
                None,
                f"Day {day} ends at {end // 60:02d}:{end % 60:02d}, after the {p.day_end_min // 60:02d}:00 day end",
            )
        )
    if len(slots) > p.max_per_day:
        violations.append(
            Violation("max_per_day", day, None, f"Day {day} has {len(slots)} activities (limit {p.max_per_day})")
        )
    return DaySchedule(day, slots, lunch_at, end, violations)


def order_nearest_neighbour(cands: list[Candidate], start: tuple[float, float] | None) -> list[Candidate]:
    """Greedy nearest-neighbour ordering (deterministic: ties broken by -score, id). A heuristic, not optimal."""
    remaining = sorted(cands, key=lambda c: (-c.score, c.name, c.id))
    if not remaining:
        return []
    pos = start or (remaining[0].lat, remaining[0].lng)
    out: list[Candidate] = []
    while remaining:
        nxt = min(remaining, key=lambda c: (haversine_m(pos[0], pos[1], c.lat, c.lng), -c.score, c.name, c.id))
        out.append(nxt)
        remaining.remove(nxt)
        pos = (nxt.lat, nxt.lng)
    return out


def living_cost(p: PlanParams) -> int | None:
    return None if p.living_per_day_minor is None else p.living_per_day_minor * p.days * p.travelers


def activity_budget(p: PlanParams) -> int | None:
    """Money left for paid activities after the estimated daily living cost (None = no budget set)."""
    if p.budget_total_minor is None:
        return None
    return p.budget_total_minor - (living_cost(p) or 0)


def select_candidates(cands: list[Candidate], p: PlanParams) -> tuple[list[Candidate], list[tuple[Candidate, str]]]:
    """Pick the highest-scoring candidates that fit the time capacity and the money left for activities."""
    capacity = p.days * (p.day_end_min - p.day_start_min - p.lunch_min)
    left = activity_budget(p)
    chosen: list[Candidate] = []
    skipped: list[tuple[Candidate, str]] = []
    used = 0
    for c in sorted(cands, key=lambda c: (-c.score, c.name, c.id)):
        cost = (c.cost_minor or 0) * p.travelers
        if len(chosen) >= p.days * p.max_per_day:
            skipped.append((c, "no room left in the itinerary"))
        elif used + c.duration_min + 20 > capacity:  # 20 min average travel allowance (estimate)
            skipped.append((c, "does not fit in the available time"))
        elif left is not None and cost > left:
            skipped.append((c, "would exceed the activity budget"))
        else:
            chosen.append(c)
            used += c.duration_min + 20
            if left is not None:
                left -= cost
    return chosen, skipped


def pack_days(ordered: list[Candidate], p: PlanParams) -> tuple[list[DaySchedule], list[tuple[Candidate, str]]]:
    """Balanced first-fit packing of an ordered list into days.

    Each activity goes to the first day that is below the per-day target (ceil(n / days)) AND where it is
    feasible (time + opening hours). If every under-target day rejects it, any feasible day is used; if none,
    it is dropped with a reason. Following the nearest-neighbour order keeps neighbours on the same day.
    """
    target = max(1, -(-len(ordered) // p.days))
    groups: list[list[Candidate]] = [[] for _ in range(p.days)]
    dropped: list[tuple[Candidate, str]] = []

    def feasible(d: int, c: Candidate) -> bool:
        return len(groups[d]) < p.max_per_day and not schedule_day(d + 1, groups[d] + [c], p).violations

    for c in ordered:
        day = next((d for d in range(p.days) if len(groups[d]) < target and feasible(d, c)), None)
        if day is None:
            day = next((d for d in range(p.days) if feasible(d, c)), None)
        if day is None:
            dropped.append((c, "no day where it fits the schedule and opening hours"))
        else:
            groups[day].append(c)
    return [schedule_day(d + 1, groups[d], p) for d in range(p.days)], dropped


def pack_groups(groups: list[list[Candidate]], p: PlanParams) -> tuple[list[DaySchedule], list[tuple[Candidate, str]]]:
    """Schedule externally proposed day groups (e.g. from an LLM). Infeasible activities are re-packed
    into any later/earlier day that works, or dropped with a reason - the proposal is never trusted."""
    groups = [list(g) for g in groups] + [[] for _ in range(p.days - len(groups))]
    groups = groups[: p.days]
    kept: list[list[Candidate]] = [[] for _ in range(p.days)]
    overflow: list[Candidate] = []
    for d, g in enumerate(groups):
        for c in g:
            trial = schedule_day(d + 1, kept[d] + [c], p)
            (kept[d].append(c) if not trial.violations and len(kept[d]) < p.max_per_day else overflow.append(c))
    dropped: list[tuple[Candidate, str]] = []
    for c in overflow:
        for d in range(p.days):
            if len(kept[d]) < p.max_per_day and not schedule_day(d + 1, kept[d] + [c], p).violations:
                kept[d].append(c)
                break
        else:
            dropped.append((c, "proposed placement was infeasible and no other day fits"))
    return [schedule_day(d + 1, kept[d], p) for d in range(p.days)], dropped


def plan_deterministic(cands: list[Candidate], p: PlanParams):
    chosen, skipped = select_candidates(cands, p)
    schedules, dropped = pack_days(order_nearest_neighbour(chosen, p.start), p)
    return schedules, skipped + dropped


def budget_summary(schedules: list[DaySchedule], by_id: dict[str, Candidate], p: PlanParams) -> dict:
    """Cost breakdown in minor units. Only KNOWN costs are summed; unknown ones are counted separately."""
    acts = unknown = 0
    for s in schedules:
        for sl in s.slots:
            c = by_id[sl.candidate_id]
            if c.cost_minor is None:
                unknown += 1
            else:
                acts += c.cost_minor * p.travelers
    living = living_cost(p)
    total = acts + (living or 0)
    out = {
        "activities_minor": acts,
        "living_estimate_minor": living,
        "total_estimate_minor": total,
        "budget_minor": p.budget_total_minor,
        "unknown_cost_items": unknown,
        "currency": "INR",
        "note": "Totals include only known costs; living cost is the destination's per-day estimate.",
    }
    if p.budget_total_minor:
        out["deviation_pct"] = round((total - p.budget_total_minor) / p.budget_total_minor * 100, 2)
        out["within_budget"] = total <= p.budget_total_minor
    else:
        out["deviation_pct"], out["within_budget"] = None, None
    return out


def validate(schedules: list[DaySchedule], by_id: dict[str, Candidate], p: PlanParams) -> tuple[dict, list[Violation]]:
    summary = budget_summary(schedules, by_id, p)
    violations = [v for s in schedules for v in s.violations]
    if summary["within_budget"] is False:
        violations.append(
            Violation("budget", None, None, f"Estimated total exceeds the budget by {summary['deviation_pct']}%")
        )
    return summary, violations
