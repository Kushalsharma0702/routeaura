"""Constrained multi-day route optimisation with Google OR-Tools.

Problem: given an itinerary's activities, assign them to days and order them to minimise

    Z = alpha * distance_km + beta * time_min + gamma * travel_cost_rupees + delta * preference_penalty

subject to: day start/end, per-activity visit duration, verified opening-hour windows (only where hours are
verified AND dates are set), a lunch break, start location (hotel), required (locked) activities that may not be
dropped, and an activity budget. All weights are configurable (`OptWeights`).

What this is and is not
* It orders stops using a TRAVEL MATRIX. The matrix comes from a routing provider; with no provider it is the
  great-circle estimate and is labelled as such. This is vehicle-routing / TSP-style *ordering*; it is not
  road-network pathfinding (see graph.py for Dijkstra / A*).
* preference_penalty = cost of dropping an optional activity (scaled by its relevance score) + a small penalty for
  visiting high-score activities late in the day + a soft per-day load-balance term.
* The returned plan is re-evaluated by the planner's own scheduler (authoritative), so reported times and
  violations are consistent with the rest of the app.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field

from ortools.constraint_solver import pywrapcp, routing_enums_pb2

from app.integrations.routing.base import TravelMatrix
from app.modules.itinerary import planner as pl

SCALE = 100  # integer cost units per 1.0 of objective (OR-Tools needs integers)
LATE_BOUND_MIN = 14 * 60  # high-score activities are preferred before 14:00


@dataclass(frozen=True)
class OptWeights:
    distance: float = 1.0  # alpha: per km
    time: float = 1.0  # beta: per minute of travel
    cost: float = 0.5  # gamma: per rupee of estimated travel cost
    preference: float = 1.0  # delta: scales drop / lateness / balance penalties
    taxi_rupees_per_km: float = 12.0  # ASSUMPTION used to turn distance into a travel-cost estimate

    def to_dict(self) -> dict:
        return {
            "distance": self.distance,
            "time": self.time,
            "cost": self.cost,
            "preference": self.preference,
            "taxi_rupees_per_km": self.taxi_rupees_per_km,
        }


@dataclass
class OptActivity:
    id: str
    name: str
    lat: float
    lng: float
    duration_min: int
    cost_total_minor: int | None  # for all travelers; None = unknown
    score: float = 0.0
    locked: bool = False  # required: never dropped
    candidate: pl.Candidate | None = None


@dataclass
class OptResult:
    status: str  # optimized | relaxed | infeasible
    days: list[list[str]]  # activity ids per day, in visiting order
    dropped: list[tuple[str, str]] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    solver_ms: float = 0.0
    objective: int | None = None


def leg_from_matrix(points: list[tuple[float, float]], m: TravelMatrix):
    index = {(round(lat, 6), round(lng, 6)): i for i, (lat, lng) in enumerate(points)}

    def leg(a: tuple[float, float], b: tuple[float, float]) -> tuple[int, int]:
        return m.leg(index[(round(a[0], 6), round(a[1], 6))], index[(round(b[0], 6), round(b[1], 6))])

    return leg


def _day_windows(c: pl.Candidate, p: pl.PlanParams) -> tuple[list[int], tuple[int, int] | None, list[str]]:
    """(allowed day indexes, conservative [open, close] window or None, notes)."""
    allowed, wins, notes = [], [], []
    for d in range(p.days):
        from datetime import timedelta

        day_date = p.start_date + timedelta(days=d) if p.start_date else None
        status, windows = pl.hours_window(c, day_date)
        if status == "verified_closed":
            continue
        allowed.append(d)
        if status == "verified_open" and windows:
            wins.append((min(o for o, _ in windows), max(cl for _, cl in windows)))
    if not wins:
        return allowed, None, notes
    lo, hi = max(o for o, _ in wins), min(cl for _, cl in wins)
    if len({w for w in wins}) > 1:
        notes.append(f"{c.name}: opening hours differ between allowed days; the overlapping window was used")
    return allowed, (lo, hi) if lo < hi else None, notes


def _solve(
    acts: list[OptActivity],
    excluded: set[str],
    p: pl.PlanParams,
    matrix: TravelMatrix,
    w: OptWeights,
    *,
    use_windows: bool,
    use_break: bool,
    improve: bool,
    time_limit_ms: int,
):
    """One OR-Tools solve. Returns (days of ids | None, dropped, notes, objective)."""
    live = [a for a in acts if a.id not in excluded]
    n = len(live)
    if n == 0:
        return [[] for _ in range(p.days)], [], [], 0
    mat_index = {a.id: i + 1 for i, a in enumerate(acts)}  # depot = 0
    ids = [a.id for a in live]
    nodes = [0] + [mat_index[i] for i in ids]  # solver node -> matrix index
    service = [0] + [a.duration_min for a in live]
    notes: list[str] = []

    manager = pywrapcp.RoutingIndexManager(n + 1, p.days, 0)
    routing = pywrapcp.RoutingModel(manager)

    def dur(f: int, t: int) -> int:
        return 0 if t == 0 else matrix.duration_min[nodes[f]][nodes[t]]  # the return to the hotel is not scheduled

    def transit_cb(fi, ti):
        f, t = manager.IndexToNode(fi), manager.IndexToNode(ti)
        return service[f] + dur(f, t)

    def arc_cb(fi, ti):
        f, t = manager.IndexToNode(fi), manager.IndexToNode(ti)
        if t == 0 or f == t:
            return 0
        km = matrix.distance_m[nodes[f]][nodes[t]] / 1000.0
        minutes = matrix.duration_min[nodes[f]][nodes[t]]
        rupees = km * w.taxi_rupees_per_km
        return int(round(SCALE * (w.distance * km + w.time * minutes + w.cost * rupees)))

    transit = routing.RegisterTransitCallback(transit_cb)
    routing.SetArcCostEvaluatorOfAllVehicles(routing.RegisterTransitCallback(arc_cb))
    routing.AddDimension(transit, 24 * 60, p.day_end_min, False, "Time")
    time_dim = routing.GetDimensionOrDie("Time")
    for v in range(p.days):
        time_dim.CumulVar(routing.Start(v)).SetRange(p.day_start_min, p.day_start_min)
        time_dim.CumulVar(routing.End(v)).SetRange(p.day_start_min, p.day_end_min)

    # per-activity day permissions and opening windows
    for i, a in enumerate(live, 1):
        cand = a.candidate
        if cand is None or not use_windows:
            continue
        allowed, window, wn = _day_windows(cand, p)
        notes.extend(wn)
        idx = manager.NodeToIndex(i)
        if len(allowed) < p.days:
            # forbid the days on which the activity is verified closed (VehicleVar is stable across OR-Tools versions;
            # the SetAllowedVehiclesForIndex binding is broken in some releases)
            for closed_day in (d for d in range(p.days) if d not in allowed):
                routing.VehicleVar(idx).RemoveValue(closed_day)
        if window:
            time_dim.CumulVar(idx).SetRange(window[0], max(window[0], window[1] - a.duration_min))

    # preference term 1: prefer relevant activities before mid-afternoon
    for i, a in enumerate(live, 1):
        coeff = int(round(SCALE * 0.05 * w.preference * a.score))
        if coeff > 0:
            time_dim.SetCumulVarSoftUpperBound(manager.NodeToIndex(i), LATE_BOUND_MIN, coeff)

    # preference term 2: soft load balancing across days
    routing.AddConstantDimension(1, n + 2, True, "Count")
    count = routing.GetDimensionOrDie("Count")
    target = math.ceil(n / p.days) + 1  # +1: the final arc into the depot also counts
    for v in range(p.days):
        count.SetCumulVarSoftUpperBound(routing.End(v), target, int(round(SCALE * 3 * w.preference)))

    # optional activities may be dropped at a price that grows with their relevance; locked ones may not
    for i, a in enumerate(live, 1):
        if not a.locked:
            routing.AddDisjunction([manager.NodeToIndex(i)], int(round(SCALE * w.preference * (60 + 240 * a.score))))

    if use_break:
        visit_transit = [service[manager.IndexToNode(k)] for k in range(routing.Size())]
        for v in range(p.days):
            iv = routing.solver().FixedDurationIntervalVar(
                p.lunch_start_min, p.lunch_start_min + 120, p.lunch_min, False, f"lunch{v}"
            )
            time_dim.SetBreakIntervalsOfVehicle([iv], v, visit_transit)

    params = pywrapcp.DefaultRoutingSearchParameters()
    params.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    if improve:
        params.local_search_metaheuristic = routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
        params.time_limit.FromMilliseconds(time_limit_ms)
    else:
        params.local_search_metaheuristic = routing_enums_pb2.LocalSearchMetaheuristic.GREEDY_DESCENT  # deterministic
        params.time_limit.FromMilliseconds(max(time_limit_ms, 1000))
    sol = routing.SolveWithParameters(params)
    if sol is None:
        return None, [], notes, None
    days: list[list[str]] = []
    visited: set[str] = set()
    for v in range(p.days):
        idx, seq = routing.Start(v), []
        while not routing.IsEnd(idx):
            node = manager.IndexToNode(idx)
            if node != 0:
                seq.append(ids[node - 1])
                visited.add(ids[node - 1])
            idx = sol.Value(routing.NextVar(idx))
        days.append(seq)
    dropped = [
        (a.id, "dropped by the optimizer: low relevance versus the time/travel it costs")
        for a in live
        if a.id not in visited
    ]
    return days, dropped, notes, sol.ObjectiveValue()


def evaluate(days: list[list[str]], acts: dict[str, OptActivity], p: pl.PlanParams) -> dict:
    """Authoritative evaluation with the app's own scheduler: distance, time, cost, violations."""
    schedules = [pl.schedule_day(d + 1, [acts[i].candidate for i in ids], p) for d, ids in enumerate(days)]
    by_id = {a.candidate.id: a.candidate for a in acts.values()}
    summary, violations = pl.validate(schedules, by_id, p)
    slots = [s for sch in schedules for s in sch.slots]
    travel_cost = sum(s.travel_m for s in slots) / 1000.0
    return {
        "distance_m": sum(s.travel_m for s in slots),
        "travel_min": sum(s.travel_min for s in slots),
        "wait_min": sum(s.wait_min for s in slots),
        "n_activities": len(slots),
        "violations": [{"type": v.type, "day": v.day, "message": v.message} for v in violations],
        "budget": summary,
        "per_day": [
            {
                "day": s.day,
                "n": len(s.slots),
                "travel_min": sum(x.travel_min for x in s.slots),
                "distance_m": sum(x.travel_m for x in s.slots),
                "ends": s.end_min,
            }
            for s in schedules
        ],
        "travel_cost_estimate_minor": int(travel_cost * 1200),
        "utility": sum(acts[i].score for sch in days for i in sch),
    }


def optimize(
    acts: list[OptActivity],
    p: pl.PlanParams,
    matrix: TravelMatrix,
    weights: OptWeights | None = None,
    *,
    improve: bool = False,
    time_limit_ms: int = 1500,
) -> OptResult:
    """Optimise day assignment and order. Locked activities are preserved. Budget is enforced by re-solving
    without the lowest-relevance optional activities until the known activity cost fits."""
    weights = weights or OptWeights()
    started = time.perf_counter()
    by_id = {a.id: a for a in acts}
    notes: list[str] = []
    excluded: set[str] = set()
    budget_left = pl.activity_budget(p)
    for _attempt in range(len(acts) + 1):
        days, dropped, n, obj = _solve(
            acts,
            excluded,
            p,
            matrix,
            weights,
            use_windows=True,
            use_break=True,
            improve=improve,
            time_limit_ms=time_limit_ms,
        )
        notes.extend(x for x in n if x not in notes)
        if days is None:
            break
        spent = sum((by_id[i].cost_total_minor or 0) for d in days for i in d)
        if budget_left is None or spent <= budget_left:
            return OptResult(
                "optimized",
                days,
                [(i, r) for i, r in dropped] + [(i, "over the activity budget") for i in excluded],
                notes,
                (time.perf_counter() - started) * 1000,
                obj,
            )
        # over budget: drop the least relevant unlocked visited activity (cheapest relevance per rupee) and re-solve
        victims = sorted(
            (by_id[i] for d in days for i in d if not by_id[i].locked),
            key=lambda a: (a.score, -(a.cost_total_minor or 0), a.id),
        )
        if not victims:
            notes.append("Locked activities alone exceed the activity budget; they were kept.")
            return OptResult(
                "optimized",
                days,
                dropped + [(i, "over the activity budget") for i in excluded],
                notes,
                (time.perf_counter() - started) * 1000,
                obj,
            )
        excluded.add(victims[0].id)
    # infeasible with all constraints: diagnose, then try a relaxed solve (opening hours + lunch ignored)
    need = sum(a.duration_min for a in acts if a.locked)
    capacity = p.days * (p.day_end_min - p.day_start_min)
    if need > capacity:
        notes.append(
            f"Locked activities need {need} min but the trip offers only {capacity} min of daytime: no schedule can satisfy them."
        )
    days, dropped, n, obj = _solve(
        acts,
        excluded,
        p,
        matrix,
        weights,
        use_windows=False,
        use_break=False,
        improve=False,
        time_limit_ms=time_limit_ms,
    )
    if days is not None:
        notes.append(
            "No schedule satisfies every constraint (opening hours, lunch, day length). Returned a relaxed plan that ignores "
            "opening hours and lunch; its violations are listed."
        )
        return OptResult("relaxed", days, dropped, notes, (time.perf_counter() - started) * 1000, obj)
    notes.append(
        "No feasible schedule exists even without opening-hour and lunch constraints; the itinerary was left unchanged."
    )
    return OptResult("infeasible", [], [], notes, (time.perf_counter() - started) * 1000, None)
