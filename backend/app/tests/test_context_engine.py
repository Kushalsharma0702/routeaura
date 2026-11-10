from datetime import UTC, date, datetime, timedelta

import pytest

from app.integrations.weather.base import DayForecast
from app.modules.context import engine as ce
from app.modules.itinerary import planner as pl

NOW = datetime(2030, 1, 7, 12, 0, tzinfo=UTC)
TH = ce.Thresholds()
HAWA, JANTAR, CITY, AMBER = (26.9239, 75.8267), (26.9247, 75.8246), (26.9258, 75.8237), (26.9855, 75.8513)


def stop(id_, ll, outdoor=False, minutes=60, cost=None, score=0.5, locked=False, cat="history", hours=None):
    cand = pl.Candidate(
        id=id_,
        name=id_.title(),
        lat=ll[0],
        lng=ll[1],
        duration_min=minutes,
        cost_minor=cost,
        score=score,
        opening_hours=hours,
    )
    return ce.Stop(
        id=id_,
        attraction_id=f"att-{id_}",
        name=id_.title(),
        lat=ll[0],
        lng=ll[1],
        category=cat,
        is_outdoor=outdoor,
        duration_min=minutes,
        cost_minor=cost,
        score=score,
        locked=locked,
        candidate=cand,
    )


def fc(day=1, prob=None, mm=None, tmax=None, age_min=10, source="test-weather"):
    return DayForecast(date(2030, 1, 6 + day), mm, prob, tmax, None, source, NOW - timedelta(minutes=age_min))


def test_freshness_boundaries():
    assert ce.is_fresh(NOW - timedelta(minutes=180), NOW, 180) and not ce.is_fresh(
        NOW - timedelta(minutes=181), NOW, 180
    )
    assert not ce.is_fresh(NOW + timedelta(minutes=5), NOW, 180)  # a timestamp from the future is not trusted


@pytest.mark.parametrize(
    "prob,mm,expected",
    [(60, None, True), (59, None, False), (None, 5.0, True), (None, 4.9, False), (10, 7.0, True), (None, None, False)],
)
def test_rain_thresholds(prob, mm, expected):
    days = {1: [stop("fort", AMBER, outdoor=True)]}
    forecasts = {1: fc(prob=prob, mm=mm, tmax=25 if prob is None and mm is None else None)}
    issues, stale, _ = ce.detect_weather(days, forecasts, NOW, TH)
    assert bool(issues) is expected and not stale
    if expected:
        assert issues[0].type == "rain" and "test-weather" in issues[0].evidence and issues[0].fetched_at


def test_only_outdoor_activities_are_flagged_and_evidence_names_the_source():
    days = {1: [stop("palace", CITY, outdoor=False), stop("fort", AMBER, outdoor=True)]}
    issues, _, _ = ce.detect_weather(days, {1: fc(prob=90, mm=12.5)}, NOW, TH)
    assert [i.activity_id for i in issues] == ["fort"]
    assert (
        "90% chance of rain" in issues[0].evidence
        and "12.5 mm" in issues[0].evidence
        and "fetched" in issues[0].evidence
    )


def test_heat_only_when_it_is_not_raining():
    days = {1: [stop("fort", AMBER, outdoor=True)]}
    assert ce.detect_weather(days, {1: fc(tmax=43)}, NOW, TH)[0][0].type == "heat"
    assert ce.detect_weather(days, {1: fc(tmax=39.9)}, NOW, TH)[0] == []
    assert ce.detect_weather(days, {1: fc(tmax=45, prob=80)}, NOW, TH)[0][0].type == "rain"


def test_stale_forecasts_are_never_acted_on_and_unknown_values_are_not_assumed():
    days = {1: [stop("fort", AMBER, outdoor=True)], 2: [stop("fort2", HAWA, outdoor=True)]}
    issues, stale, notes = ce.detect_weather(days, {1: fc(prob=99, age_min=400), 2: fc(day=2)}, NOW, TH)
    assert issues == [] and stale == [1]
    assert any("no forecast values" in n for n in notes)


def test_verified_closures_need_dates_and_verified_hours():
    closed_mon = {d: [["09:00", "18:00"]] for d in pl.DAY_KEYS} | {"mon": []}
    days = {1: [stop("a", HAWA, hours=closed_mon), stop("b", CITY, hours=None)]}
    assert ce.detect_verified_closures(days, None) == []  # no dates: nothing is claimed
    out = ce.detect_verified_closures(days, date(2030, 1, 7))  # a Monday
    assert [i.activity_id for i in out] == ["a"] and out[0].source == "verified_hours" and "Monday" in out[0].evidence
    assert ce.detect_verified_closures(days, date(2030, 1, 8)) == []  # Tuesday: open


def test_alternatives_are_filtered_ranked_and_explained():
    old = stop("fort", AMBER, outdoor=True, cat="history")
    closed_mon = {d: [["09:00", "18:00"]] for d in pl.DAY_KEYS} | {"mon": []}
    pool = [
        stop("far_out", (27.5, 76.5), outdoor=True, cat="history", score=0.9),
        stop("palace", CITY, cat="history", score=0.4),
        stop("museum", HAWA, cat="culture", score=0.9),
        stop("closed", JANTAR, cat="history", score=0.99, hours=closed_mon),
    ]
    alts = ce.rank_alternatives(old, pool, day=1, start_date=date(2030, 1, 7), indoor_only=True)
    names = [a.name for a, _ in alts]
    assert "Far_Out" not in names and "Closed" not in names  # outdoor and verified-closed are excluded
    assert names == ["Palace", "Museum"]  # same category first, then relevance
    assert "same category" in alts[0][1] and "km from" in alts[0][1] and "opening hours not verified" in alts[0][1]
    cheap = ce.rank_alternatives(
        stop("x", AMBER, cost=100000),
        [stop("p", CITY, cost=40000), stop("q", HAWA, cost=60000), stop("u", JANTAR, cost=None)],
        day=1,
        start_date=None,
        max_cost_minor=50000,
    )
    assert [a.name for a, _ in cheap] == ["P"]  # unknown cost never qualifies as "cheaper"


def test_simulate_reports_violations_and_budget():
    p = pl.PlanParams(days=1, start=HAWA, budget_total_minor=1000, living_per_day_minor=0)
    sim = ce.simulate({1: [stop("a", HAWA, minutes=300, cost=5000), stop("b", AMBER, minutes=300)]}, p)
    assert any(v["type"] == "day_overrun" for v in sim["violations"]) and any(
        v["type"] == "budget" for v in sim["violations"]
    )
    assert sim["days"][0]["stops"] == ["A", "B"]


def test_delay_moves_or_removes_unlocked_low_relevance_stops_and_never_touches_locked_ones():
    p = pl.PlanParams(days=2, start=HAWA)
    today = [
        stop("must", HAWA, minutes=120, locked=True, score=0.1),
        stop("nice", CITY, minutes=120, score=0.9),
        stop("meh", JANTAR, minutes=120, score=0.2),
    ]
    changes, notes = ce.plan_delay(today, set(), 11 * 60, 1, True, p)  # 11:00: 7 h left for 6 h of visits + lunch + hops
    assert (
        [c["name"] for c in changes] == ["Meh"]
        and changes[0]["action"] == "move"
        and changes[0]["to_day"] == 2
        and not notes
    )
    changes, _ = ce.plan_delay(today, set(), 11 * 60, 1, False, p)
    assert changes[0]["action"] == "remove"
    changes, notes = ce.plan_delay([stop("a", HAWA, minutes=300, locked=True)], set(), 15 * 60, 1, True, p)
    assert changes == [] and any("Locked activities cannot all fit" in n for n in notes)
    assert ce.plan_delay(today, {"must", "nice", "meh"}, 10 * 60, 1, True, p) == ([], ["Nothing is left to do today."])
    ok, _ = ce.plan_delay(today, set(), 9 * 60, 1, True, p)
    assert ok == []  # on schedule: no change proposed
