import itertools
from datetime import date

import httpx
import pytest

from app.integrations.routing.base import RoutingError, TravelMatrix
from app.integrations.routing.providers import EstimateRouting, OsrmRouting, ResilientRouting
from app.modules.itinerary import planner as pl
from app.modules.routing import optimizer as op

DEPOT = (26.90, 75.80)
EST = EstimateRouting()


def line_point(km_east: float) -> tuple[float, float]:
    return (DEPOT[0], DEPOT[1] + km_east / 99.8)  # ~99.8 km per degree of longitude at this latitude


def act(id_, km, minutes=60, cost=None, score=0.5, locked=True, hours=None):
    lat, lng = line_point(km)
    c = pl.Candidate(
        id=id_,
        name=id_.upper(),
        lat=lat,
        lng=lng,
        duration_min=minutes,
        cost_minor=cost,
        score=score,
        opening_hours=hours,
    )
    return op.OptActivity(
        id=id_,
        name=id_.upper(),
        lat=lat,
        lng=lng,
        duration_min=minutes,
        cost_total_minor=cost,
        score=score,
        locked=locked,
        candidate=c,
    )


def setup(acts, **kw):
    pts = [DEPOT] + [(a.lat, a.lng) for a in acts]
    m = EST.matrix(pts)
    p = pl.PlanParams(days=kw.pop("days", 1), start=DEPOT, leg=op.leg_from_matrix(pts, m), **kw)
    return pts, m, p


def total_distance(order, acts, p):
    by = {a.id: a for a in acts}
    return op.evaluate([order], by, p)["distance_m"]


# ------------------------------------------------------------------ ordering quality
def test_optimizer_finds_the_brute_force_optimal_order_on_a_zigzag():
    acts = [act("a", 20), act("b", 2), act("c", 18), act("d", 4), act("e", 12)]  # input order zig-zags along a line
    pts, m, p = setup(acts)
    res = op.optimize(acts, p, m)
    assert res.status == "optimized" and sorted(res.days[0]) == sorted(a.id for a in acts) and not res.dropped
    best = min(total_distance(list(perm), acts, p) for perm in itertools.permutations([a.id for a in acts]))
    assert total_distance(res.days[0], acts, p) == best
    assert total_distance(res.days[0], acts, p) < total_distance(
        [a.id for a in acts], acts, p
    )  # beats the original order
    assert res.days[0] == ["b", "d", "e", "c", "a"]  # sweeps outwards along the line


def test_result_is_deterministic():
    acts = [act("a", 20), act("b", 2), act("c", 18), act("d", 4), act("e", 12), act("f", 9)]
    pts, m, p = setup(acts, days=2)
    assert op.optimize(acts, p, m).days == op.optimize(acts, p, m).days


def test_metrics_come_from_the_authoritative_scheduler():
    acts = [act("a", 5), act("b", 9)]
    pts, m, p = setup(acts)
    ev = op.evaluate([["a", "b"]], {a.id: a for a in acts}, p)
    sched = pl.schedule_day(1, [acts[0].candidate, acts[1].candidate], p)
    assert ev["distance_m"] == sum(s.travel_m for s in sched.slots) and ev["travel_min"] == sum(
        s.travel_min for s in sched.slots
    )
    assert ev["n_activities"] == 2 and ev["violations"] == [] and ev["per_day"][0]["n"] == 2


# ------------------------------------------------------------------ preservation, dropping, weights
def test_locked_activities_are_never_dropped_but_optional_ones_can_be():
    must = [act("m1", 3, 180, locked=True), act("m2", 6, 180, locked=True)]
    extra = [act("o1", 40, 180, score=0.1, locked=False), act("o2", 4, 60, score=0.9, locked=False)]
    acts = must + extra
    pts, m, p = setup(acts)
    res = op.optimize(acts, p, m)
    visited = {i for d in res.days for i in d}
    assert {"m1", "m2"} <= visited  # required activities preserved
    assert "o1" not in visited and any(
        i == "o1" for i, _ in res.dropped
    )  # far, low-relevance optional one is dropped with a reason


def test_preference_weight_keeps_a_relevant_optional_activity():
    must = [act("m1", 3, 120), act("m2", 5, 120)]
    far = act("far", 30, 60, score=0.95, locked=False)
    acts = must + [far]
    pts, m, p = setup(acts)
    assert "far" not in {i for d in op.optimize(acts, p, m, op.OptWeights(preference=0.0)).days for i in d}
    assert "far" in {i for d in op.optimize(acts, p, m, op.OptWeights(preference=50.0)).days for i in d}


def test_distance_and_time_weights_change_the_objective_not_feasibility():
    acts = [act("a", 20), act("b", 2), act("c", 18), act("d", 4)]
    pts, m, p = setup(acts)
    r1 = op.optimize(acts, p, m, op.OptWeights(distance=5, time=0.1, cost=0.1))
    r2 = op.optimize(acts, p, m, op.OptWeights(distance=0.1, time=5, cost=0.1))
    assert r1.status == r2.status == "optimized"
    assert r1.objective != r2.objective


def test_a_custom_matrix_is_respected():
    # a "river" makes b->c very slow; a provider matrix must beat the geometric estimate
    acts = [act("a", 5, 30), act("b", 6, 30), act("c", 7, 30)]
    pts = [DEPOT] + [(x.lat, x.lng) for x in acts]
    n = len(pts)
    dist = [[abs(i - j) * 1000 for j in range(n)] for i in range(n)]
    dur = [[abs(i - j) * 2 for j in range(n)] for i in range(n)]
    dur[2][3] = dur[3][2] = 90  # b <-> c is 90 minutes apart
    m = TravelMatrix(dist, dur, "test-provider")
    p = pl.PlanParams(days=1, start=DEPOT, leg=op.leg_from_matrix(pts, m))
    res = op.optimize(acts, p, m)
    ev = op.evaluate(res.days, {a.id: a for a in acts}, p)
    assert ev["travel_min"] < 90 + 2  # the optimiser avoided the slow b-c leg


# ------------------------------------------------------------------ constraints
def test_opening_windows_are_enforced():
    hours = {d: [["14:00", "17:00"]] for d in pl.DAY_KEYS}
    acts = [act("late", 2, 60, hours=hours), act("any", 4, 60)]
    pts, m, p = setup(acts, start_date=date(2030, 1, 7))
    res = op.optimize(acts, p, m)
    assert res.status == "optimized"
    ev = op.evaluate(res.days, {a.id: a for a in acts}, p)
    assert ev["violations"] == []
    sched = pl.schedule_day(1, [{a.id: a for a in acts}[i].candidate for i in res.days[0]], p)
    late = next(s for s in sched.slots if s.candidate_id == "late")
    assert late.start_min >= 14 * 60  # not visited before it opens


def test_a_verified_closed_day_moves_the_activity_to_another_day():
    closed_mon = {d: [["09:00", "18:00"]] for d in pl.DAY_KEYS} | {"mon": []}
    acts = [act("x", 3, 60, hours=closed_mon), act("y", 4, 60)]
    pts, m, p = setup(acts, days=2, start_date=date(2030, 1, 7))  # day 1 is a Monday
    res = op.optimize(acts, p, m)
    assert res.status == "optimized" and "x" not in res.days[0] and "x" in res.days[1]


def test_unknown_hours_are_not_treated_as_constraints():
    acts = [act("u", 3, 60, hours=None)]
    pts, m, p = setup(acts, start_date=date(2030, 1, 7))
    assert op.optimize(acts, p, m).days == [["u"]]


def test_lunch_break_is_respected_in_the_reevaluated_schedule():
    acts = [act("a", 3, 150), act("b", 5, 150), act("c", 7, 150)]
    pts, m, p = setup(acts)
    res = op.optimize(acts, p, m)
    sched = pl.schedule_day(1, [{a.id: a for a in acts}[i].candidate for i in res.days[0]], p)
    assert sched.lunch_start_min is not None and sched.lunch_start_min >= 13 * 60
    assert all(sched.slots[i + 1].start_min >= sched.slots[i].end_min for i in range(len(sched.slots) - 1))


def test_budget_forces_the_least_relevant_optional_activity_out():
    acts = [
        act("keep", 3, 60, cost=40000, score=0.9, locked=False),
        act("pricey", 5, 60, cost=900000, score=0.2, locked=False),
    ]
    pts, m, p = setup(acts, budget_total_minor=100000, living_per_day_minor=0, travelers=1)
    res = op.optimize(acts, p, m)
    visited = {i for d in res.days for i in d}
    assert visited == {"keep"} and ("pricey", "over the activity budget") in res.dropped
    ev = op.evaluate(res.days, {a.id: a for a in acts}, p)
    assert ev["budget"]["within_budget"] is True


def test_locked_activities_over_budget_are_kept_and_reported():
    acts = [act("must", 3, 60, cost=900000, locked=True)]
    pts, m, p = setup(acts, budget_total_minor=100000, living_per_day_minor=0)
    res = op.optimize(acts, p, m)
    assert res.days == [["must"]] and any("Locked activities alone exceed" in n for n in res.notes)


def test_infeasible_locked_set_is_diagnosed_and_leaves_the_plan_unchanged():
    acts = [act("a", 2, 500), act("b", 4, 500)]  # 1000 min of visits in a 540-min day
    pts, m, p = setup(acts)
    res = op.optimize(acts, p, m)
    assert res.status == "infeasible" and res.days == []
    assert any("need 1000 min" in n for n in res.notes) and any("left unchanged" in n for n in res.notes)


def test_conflicting_windows_fall_back_to_a_relaxed_plan_with_visible_violations():
    morning = {d: [["09:00", "10:00"]] for d in pl.DAY_KEYS}
    acts = [
        act("m1", 2, 60, hours=morning),
        act("m2", 30, 60, hours=morning),
    ]  # both only open 09:00-10:00, 30 km apart
    pts, m, p = setup(acts, start_date=date(2030, 1, 7))
    res = op.optimize(acts, p, m)
    assert res.status == "relaxed" and any("relaxed plan" in n for n in res.notes)
    ev = op.evaluate(res.days, {a.id: a for a in acts}, p)
    assert any(v["type"] == "opening_hours" for v in ev["violations"])


def test_optimizer_handles_an_empty_problem():
    pts, m, p = setup([])
    assert op.optimize([], p, m).days == [[]]


# ------------------------------------------------------------------ routing providers
def test_estimate_provider_is_labelled_symmetric_and_zero_on_the_diagonal():
    m = EST.matrix([DEPOT, line_point(5), line_point(10)])
    assert m.source == "estimate" and m.live_traffic is False and "not road routing" in m.notes[0]
    assert all(m.distance_m[i][i] == 0 and m.duration_min[i][i] == 0 for i in range(3))
    assert m.distance_m[0][1] == m.distance_m[1][0] and m.distance_m[0][2] > m.distance_m[0][1]


def _osrm(handler):
    return OsrmRouting("http://osrm.test", client=httpx.Client(transport=httpx.MockTransport(handler)))


def test_osrm_adapter_parses_the_table_response_and_labels_the_source():
    seen = {}

    def handler(req: httpx.Request):
        seen["url"] = str(req.url)
        return httpx.Response(
            200, json={"code": "Ok", "durations": [[0, 600], [660, 0]], "distances": [[0, 4200], [4300, 0]]}
        )

    m = _osrm(handler).matrix([DEPOT, line_point(5)])
    assert m.source == "osrm" and m.duration_min == [[0, 10], [11, 0]] and m.distance_m == [[0, 4200], [4300, 0]]
    assert m.live_traffic is False and "no live traffic" in m.notes[0]
    assert "/table/v1/driving/75.800000,26.900000;" in seen["url"] and "annotations=duration" in seen["url"]


@pytest.mark.parametrize(
    "handler",
    [
        lambda r: httpx.Response(500),
        lambda r: httpx.Response(200, json={"code": "NoRoute"}),
        lambda r: httpx.Response(
            200, json={"code": "Ok", "durations": [[0, None], [None, 0]], "distances": [[0, 1], [1, 0]]}
        ),
        lambda r: httpx.Response(200, text="not json"),
    ],
)
def test_osrm_failures_raise_routing_error(handler):
    with pytest.raises(RoutingError):
        _osrm(handler).matrix([DEPOT, line_point(5)])


def test_resilient_provider_falls_back_to_the_labelled_estimate():
    bad = _osrm(lambda r: httpx.Response(503))
    m = ResilientRouting(bad, EST).matrix([DEPOT, line_point(5)])
    assert m.source == "estimate" and any("osrm unavailable" in n for n in m.notes)
    ok = ResilientRouting(
        _osrm(
            lambda r: httpx.Response(
                200, json={"code": "Ok", "durations": [[0, 60], [60, 0]], "distances": [[0, 1], [1, 0]]}
            )
        ),
        EST,
    )
    assert ok.matrix([DEPOT, line_point(5)]).source == "osrm"
