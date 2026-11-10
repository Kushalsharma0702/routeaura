import csv
import json
import random

import pytest

from app.modules.itinerary import evaluation as ev
from app.modules.itinerary import planner as pl

TINY = ev.ItineraryEvalConfig(seed=5, n_trips=40, n_attractions=10)


def strip(r):
    return json.loads(json.dumps(r, sort_keys=True, default=float))


@pytest.fixture(scope="module")
def result():
    return ev.run_experiment(TINY, n_boot=40)


def test_trips_are_deterministic_and_vary_by_seed():
    a = [ev.make_trip(random.Random("1:trips"), TINY) for _ in range(3)]
    b = [ev.make_trip(random.Random("1:trips"), TINY) for _ in range(3)]
    assert [(c[0].lat, p.days) for c, p in a] == [(c[0].lat, p.days) for c, p in b]
    other = ev.make_trip(random.Random("2:trips"), TINY)
    assert other[0][0].lat != a[0][0][0].lat


def test_generated_budgets_always_cover_living_costs():
    rng = random.Random(3)
    for _ in range(200):
        _, p = ev.make_trip(rng, TINY)
        assert p.budget_total_minor >= pl.living_cost(p)


def test_experiment_is_reproducible_apart_from_latency(result):
    def no_latency(r):
        r = strip(r)
        for m in r["methods"].values():
            m.pop("latency_ms")
        return r

    assert no_latency(ev.run_experiment(TINY, n_boot=40)) == no_latency(result)


def test_every_method_is_judged_by_the_same_validator(result):
    assert set(result["methods"]) == set(ev.METHODS) and "SYNTHETIC" in result["label"]
    # naive methods ignore constraints, the validated planner honours them
    m = result["methods"]
    assert m["validated_planner"]["has_violation"]["mean"] == 0.0
    assert m["simple_order"]["has_violation"]["mean"] > 0.3
    assert m["validated_planner"]["over_budget"]["mean"] == 0.0
    assert (
        m["nearest_neighbour"]["travel_min"]["mean"] < m["simple_order"]["travel_min"]["mean"]
    )  # geographic ordering shortens travel
    assert all(v["latency_ms"]["mean"] >= 0 for v in m.values())


def test_limitations_are_recorded_with_the_results(result):
    assert any("own rule set" in x for x in result["limitations"]) and any("LLM" in x for x in result["limitations"])


def test_outputs_written(tmp_path):
    res = ev.run_seeds([5, 6], TINY, n_boot=20)
    paths = ev.write_outputs(res, tmp_path)
    assert {p.name for p in paths} == {"itinerary_results.json", "itinerary_results.csv", "itinerary_summary.md"}
    rows = list(csv.DictReader((tmp_path / "itinerary_results.csv").open()))
    assert {r["seed"] for r in rows} == {"5", "6"} and {r["method"] for r in rows} == set(ev.METHODS)
    assert "SYNTHETIC" in (tmp_path / "itinerary_summary.md").read_text()
