import csv
import json

import pytest

from app.modules.routing import evaluation as ev

TINY = ev.RoutingEvalConfig(seed=3, n_trips=12, n_attractions=10, n_graphs=3, graph_nodes=30, n_context_cases=25)


def strip_latency(r):
    r = json.loads(json.dumps(r, sort_keys=True, default=float))
    for m in r["route_optimization"]["summary"].values():
        m.pop("latency_ms")
    r["shortest_paths"].pop("mean_ms_dijkstra")
    r["shortest_paths"].pop("mean_ms_astar")
    r["context_adaptation"].pop("latency_ms")
    r["route_optimization"]["solver_status_counts"] = None  # solver time limits can change borderline statuses
    return r


@pytest.fixture(scope="module")
def result():
    return ev.run_experiment(TINY)


def test_experiment_is_reproducible_apart_from_timings(result):
    a, b = strip_latency(result), strip_latency(ev.run_experiment(TINY))
    assert a["route_optimization_paired"] == b["route_optimization_paired"]
    assert a["shortest_paths"] == b["shortest_paths"]
    assert a["context_adaptation"] == b["context_adaptation"]
    other = ev.run_experiment(ev.RoutingEvalConfig(**{**TINY.to_dict(), "seed": 4}))
    assert strip_latency(other)["route_optimization_paired"] != a["route_optimization_paired"]


def test_labelled_synthetic_with_limitations(result):
    assert "SYNTHETIC" in result["label"] and len(result["limitations"]) >= 4
    assert any("great-circle" in x for x in result["limitations"])


def test_optimizer_shortens_routes_versus_the_original_and_the_heuristic(result):
    paired = result["route_optimization_paired"]
    assert paired["ortools_locked"]["n"] > 0
    assert (
        paired["ortools_locked"]["distance_reduction_pct"]["mean"]
        > paired["nearest_neighbour"]["distance_reduction_pct"]["mean"]
        > 0
    )
    assert paired["ortools_locked"]["distance_reduction_pct"]["mean"] > 5


def test_locked_runs_keep_the_same_activity_count_and_free_runs_trade_activities_for_feasibility(result):
    s = result["route_optimization"]["summary"]
    assert s["ortools_locked"]["n_activities"]["mean"] == pytest.approx(s["original"]["n_activities"]["mean"], abs=0.3)
    assert s["ortools_free"]["has_violation"]["mean"] < s["original"]["has_violation"]["mean"]
    assert s["ortools_free"]["n_activities"]["mean"] <= s["original"]["n_activities"]["mean"]


def test_astar_matches_dijkstra_everywhere_and_expands_fewer_nodes(result):
    sp = result["shortest_paths"]
    assert sp["paths_with_equal_cost"] == sp["query_pairs"] > 20
    assert sp["expansion_ratio_astar_over_dijkstra"] < 1.0


def test_feasibility_aware_replacement_never_does_worse_than_the_top_ranked_one(result):
    c = result["context_adaptation"]
    assert (
        c["proposals_with_violations_feasibility_aware_choice"]
        <= c["proposals_with_violations_if_top_ranked_alternative_used"]
    )
    assert c["original_plans_with_violations"] == 0 and c["latency_ms"]["max"] >= c["latency_ms"]["p50"] > 0


def test_outputs_written(tmp_path):
    res = ev.run_seeds(
        [3, 4], ev.RoutingEvalConfig(n_trips=6, n_attractions=8, n_graphs=2, graph_nodes=25, n_context_cases=10)
    )
    paths = ev.write_outputs(res, tmp_path)
    assert {p.name for p in paths} == {"routing_results.json", "routing_results.csv", "routing_summary.md"}
    rows = list(csv.DictReader((tmp_path / "routing_results.csv").open()))
    assert {r["seed"] for r in rows} == {"3", "4"} and any(r["metric"].startswith("paired_") for r in rows)
    md = (tmp_path / "routing_summary.md").read_text()
    assert "SYNTHETIC" in md and "Dijkstra vs A*" in md and "Context adaptation" in md
