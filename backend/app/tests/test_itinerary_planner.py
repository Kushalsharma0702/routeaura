from datetime import date

from app.modules.itinerary import planner as pl

# three stops within ~1 km (central Jaipur) and one ~9 km away
HAWA = (26.9239, 75.8267)
JANTAR = (26.9247, 75.8246)
CITY = (26.9258, 75.8237)
AMBER = (26.9855, 75.8513)


def cand(id_, ll, minutes=60, cost=None, score=0.5, hours=None, outdoor=False):
    return pl.Candidate(
        id=id_,
        name=id_.title(),
        lat=ll[0],
        lng=ll[1],
        duration_min=minutes,
        cost_minor=cost,
        score=score,
        opening_hours=hours,
        is_outdoor=outdoor,
    )


def params(**kw):
    base = dict(days=2, start=HAWA)
    base.update(kw)
    return pl.PlanParams(**base)


def test_travel_estimate_scales_with_distance_and_is_zero_for_same_point():
    assert pl.travel(HAWA, HAWA, 30) == (0, 0)
    m, mins = pl.travel(HAWA, AMBER, 30)
    assert 8000 < m < 12000 and 15 <= mins <= 30  # ~7.5 km great circle x 1.3 detour at 30 km/h
    assert pl.travel(HAWA, JANTAR, 30)[1] == 1  # tiny hops cost at least a minute


def test_schedule_day_orders_times_and_inserts_lunch_after_the_straddling_visit():
    p = params(start=None)
    day = pl.schedule_day(1, [cand("a", HAWA, 120), cand("b", JANTAR, 150), cand("c", CITY, 60)], p)
    s = day.slots
    assert s[0].start_min == 9 * 60 and s[0].end_min == 11 * 60
    assert s[1].start_min == 11 * 60 + 1  # 1-minute travel estimate
    assert day.lunch_start_min == s[1].end_min  # straddles 13:00 -> lunch right after it
    assert s[2].start_min >= s[1].end_min + p.lunch_min
    assert [x.position for x in s] == [1, 2, 3]
    assert not day.violations


def test_day_overrun_and_max_per_day_are_reported_not_hidden():
    p = params(start=None, max_per_day=2)
    day = pl.schedule_day(1, [cand("a", HAWA, 240), cand("b", JANTAR, 240), cand("c", CITY, 240)], p)
    kinds = {v.type for v in day.violations}
    assert kinds == {"day_overrun", "max_per_day"}


def test_opening_hours_only_used_when_verified_and_dated():
    hours = {d: [["10:00", "17:00"]] for d in pl.DAY_KEYS}
    p = params(start_date=date(2030, 1, 7), start=None)  # a Monday
    wait = pl.schedule_day(1, [cand("a", HAWA, 60, hours=hours)], p).slots[0]
    assert (
        wait.hours_status == "verified_open" and wait.start_min == 10 * 60 and wait.wait_min == 60
    )  # waits for opening
    closed = pl.schedule_day(1, [cand("a", HAWA, 60, hours={**hours, "mon": []})], p)
    assert closed.slots[0].hours_status == "verified_closed" and closed.violations[0].type == "opening_hours"
    undated = pl.schedule_day(1, [cand("a", HAWA, 60, hours=hours)], params(start=None)).slots[0]
    assert undated.hours_status == "unknown" and any("No travel date" in n for n in undated.notes)
    unverified = pl.schedule_day(1, [cand("a", HAWA, 60, hours=None)], p).slots[0]
    assert unverified.hours_status == "unknown" and "Opening hours not verified" in unverified.notes
    missing_weekday = pl.schedule_day(1, [cand("a", HAWA, 60, hours={"tue": [["10:00", "12:00"]]})], p).slots[0]
    assert missing_weekday.hours_status == "unknown"  # nothing recorded for Monday: not assumed open or closed


def test_visit_that_cannot_finish_before_closing_is_a_violation():
    hours = {d: [["09:00", "10:00"]] for d in pl.DAY_KEYS}
    day = pl.schedule_day(1, [cand("a", HAWA, 90, hours=hours)], params(start_date=date(2030, 1, 7), start=None))
    assert day.violations and day.violations[0].type == "opening_hours"


def test_nearest_neighbour_is_deterministic_and_geographically_sensible():
    cs = [cand("amber", AMBER), cand("city", CITY), cand("hawa", HAWA), cand("jantar", JANTAR)]
    order = [c.id for c in pl.order_nearest_neighbour(cs, HAWA)]
    assert order == [c.id for c in pl.order_nearest_neighbour(list(reversed(cs)), HAWA)]
    assert order[0] == "hawa" and order[-1] == "amber"  # the far attraction is visited last
    assert pl.order_nearest_neighbour([], None) == []


def test_selection_respects_time_capacity_and_activity_budget():
    cs = [cand(f"x{i}", HAWA, 180, cost=10000, score=1 - i / 10) for i in range(6)]
    chosen, skipped = pl.select_candidates(cs, params(days=1))
    assert len(chosen) == 2 and all("time" in r for _, r in skipped)  # 1 day = ~7h: two 3h visits
    assert [c.id for c in chosen] == ["x0", "x1"]  # highest scores first
    rich = pl.select_candidates(
        [cand("a", HAWA, 60, cost=50000, score=0.9), cand("b", HAWA, 60, cost=1000, score=0.5)],
        params(days=1, travelers=2, budget_total_minor=60000, living_per_day_minor=10000),
    )
    assert [c.id for c in rich[0]] == ["b"] and "budget" in rich[1][0][
        1
    ]  # 2 travelers x 500 would blow the leftover 40,000


def test_pack_days_moves_a_closed_attraction_to_a_day_it_is_open():
    mon_closed = {d: [["09:00", "18:00"]] for d in pl.DAY_KEYS} | {"mon": []}
    p = params(start_date=date(2030, 1, 7), start=None)  # day 1 = Monday, day 2 = Tuesday
    schedules, dropped = pl.pack_days([cand("a", HAWA, 60, hours=mon_closed), cand("b", JANTAR, 60)], p)
    assert [s.candidate_id for s in schedules[0].slots] == ["b"] and [s.candidate_id for s in schedules[1].slots] == [
        "a"
    ]
    assert not dropped and not any(s.violations for s in schedules)


def test_pack_days_drops_what_cannot_fit_with_a_reason():
    p = params(days=1, start=None, max_per_day=2)
    schedules, dropped = pl.pack_days([cand("a", HAWA, 300), cand("b", JANTAR, 300)], p)
    assert len(schedules[0].slots) == 1 and dropped[0][1].startswith("no day where it fits")


def test_pack_groups_never_trusts_a_proposed_grouping():
    p = params(start=None, max_per_day=3)
    hours = {d: [["09:00", "18:00"]] for d in pl.DAY_KEYS} | {"mon": []}
    p.start_date = date(2030, 1, 7)
    groups = [[cand("a", HAWA, 60, hours=hours), cand("b", JANTAR, 60)], []]  # proposes a closed place on Monday
    schedules, dropped = pl.pack_groups(groups, p)
    assert [s.candidate_id for s in schedules[1].slots] == ["a"] and not dropped
    big = [[cand("x", HAWA, 400), cand("y", JANTAR, 400)], [cand("z", CITY, 400), cand("w", AMBER, 400)]]
    _, dropped2 = pl.pack_groups(big, params(start=None))
    assert dropped2 and all("infeasible" in r for _, r in dropped2)


def test_budget_summary_counts_known_costs_only_and_flags_deviation():
    cs = {"a": cand("a", HAWA, 60, cost=20000), "b": cand("b", JANTAR, 60, cost=None)}
    p = params(days=1, travelers=2, budget_total_minor=100000, living_per_day_minor=30000, start=None)
    sched = [pl.schedule_day(1, [cs["a"], cs["b"]], p)]
    summary, viols = pl.validate(sched, cs, p)
    assert summary["activities_minor"] == 40000 and summary["living_estimate_minor"] == 60000
    assert summary["total_estimate_minor"] == 100000 and summary["unknown_cost_items"] == 1
    assert summary["within_budget"] is True and summary["deviation_pct"] == 0 and not viols
    tight = pl.validate(
        sched, cs, params(days=1, travelers=2, budget_total_minor=80000, living_per_day_minor=30000, start=None)
    )
    assert tight[0]["within_budget"] is False and tight[0]["deviation_pct"] == 25.0
    assert [v.type for v in tight[1]] == ["budget"]
    nobudget = pl.validate(sched, cs, params(days=1, start=None))
    assert nobudget[0]["within_budget"] is None and nobudget[0]["deviation_pct"] is None


def test_deterministic_plan_is_reproducible_and_valid():
    cs = [
        cand(f"p{i}", (26.90 + i * 0.004, 75.80 + i * 0.003), 90, cost=5000 * (i % 3), score=1 - i * 0.07)
        for i in range(10)
    ]
    p = params(days=2, budget_total_minor=500000, living_per_day_minor=100000)
    a, _ = pl.plan_deterministic(cs, p)
    b, _ = pl.plan_deterministic(list(reversed(cs)), p)
    assert [[s.candidate_id for s in d.slots] for d in a] == [[s.candidate_id for s in d.slots] for d in b]
    assert not any(d.violations for d in a)
    assert all(s.start_min >= p.day_start_min for d in a for s in d.slots)


def test_packing_balances_days_instead_of_filling_the_first_one():
    cs = [cand(f"p{i}", (26.90 + i * 0.002, 75.80), 60, score=1 - i * 0.1) for i in range(6)]
    schedules, dropped = pl.pack_days(cs, params(days=3, start=None))
    counts = [len(s.slots) for s in schedules]
    assert counts == [2, 2, 2] and not dropped
    # neighbours stay together: each day holds consecutive stops of the ordered route
    assert [[s.candidate_id for s in d.slots] for d in schedules] == [["p0", "p1"], ["p2", "p3"], ["p4", "p5"]]


def test_balancing_never_overrides_feasibility():
    mon_closed = {d: [["09:00", "18:00"]] for d in pl.DAY_KEYS} | {"mon": []}
    p = params(days=2, start_date=date(2030, 1, 7), start=None)
    schedules, _ = pl.pack_days([cand("a", HAWA, 60, hours=mon_closed), cand("b", JANTAR, 60), cand("c", CITY, 60)], p)
    assert "a" not in [s.candidate_id for s in schedules[0].slots]
    assert not any(s.violations for s in schedules)
