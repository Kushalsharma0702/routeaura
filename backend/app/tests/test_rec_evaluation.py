import csv
import json
import math
import random

import pytest

from app.modules.recommendations.evaluation import metrics as M
from app.modules.recommendations.evaluation.runner import METHODS, SCENARIOS, run_experiment, run_seeds, write_outputs
from app.modules.recommendations.evaluation.synthetic import (
    CATEGORY_WORDS,
    SyntheticConfig,
    TrueItem,
    TrueUser,
    make_world,
    observed_catalogue,
    stated_preferences,
    utility,
)

TINY = SyntheticConfig(seed=7, n_items=40, n_test_users=30, n_train_users=60, train_interactions_per_user=8)


# ------------------------------------------------------------------ metrics (hand-computed)
def test_precision_and_recall_at_k():
    rec, rel = ["a", "b", "c", "d"], {"a", "c", "z"}
    assert M.precision_at_k(rec, rel, 3) == pytest.approx(2 / 3)
    assert M.precision_at_k(rec, rel, 1) == 1.0
    assert M.precision_at_k(["a"], {"a"}, 3) == pytest.approx(1 / 3)  # short lists are penalised
    assert M.recall_at_k(rec, rel, 3) == pytest.approx(2 / 3)
    assert M.recall_at_k(rec, rel, 4) == pytest.approx(2 / 3)
    assert M.recall_at_k(rec, set(), 3) is None
    with pytest.raises(ValueError):
        M.precision_at_k(rec, rel, 0)


def test_ndcg_matches_the_textbook_formula():
    # binary: hits at ranks 1 and 3 -> DCG = 1 + 1/log2(4) = 1.5 ; ideal = 1 + 1/log2(3)
    got = M.ndcg_at_k(["a", "b", "c"], {"a": 1.0, "c": 1.0}, 3)
    assert got == pytest.approx(1.5 / (1 + 1 / math.log2(3)))
    assert M.ndcg_at_k(["a", "c"], {"a": 1.0, "c": 1.0}, 2) == pytest.approx(1.0)  # ideal order
    assert M.ndcg_at_k(["x", "y"], {"a": 1.0}, 2) == 0.0
    assert M.ndcg_at_k(["a"], {}, 3) is None
    # graded relevance: putting the better item first scores higher
    graded = {"a": 3.0, "b": 1.0}
    assert M.ndcg_at_k(["a", "b"], graded, 2) == pytest.approx(1.0)
    assert M.ndcg_at_k(["b", "a"], graded, 2) < 1.0
    # truncation at k: the second relevant item is cut off
    assert M.ndcg_at_k(["a", "b"], {"a": 1.0, "b": 1.0}, 1) == pytest.approx(1.0)


def test_coverage_mean_and_bootstrap():
    assert M.catalog_coverage([["a", "b"], ["b", "c"]], 6) == pytest.approx(0.5)
    with pytest.raises(ValueError):
        M.catalog_coverage([], 0)
    assert M.mean([1.0, None, 3.0]) == 2.0 and M.mean([None]) is None
    rng = random.Random(1)
    vals = [rng.random() for _ in range(50)]
    ci = M.bootstrap_ci(vals, seed=3, n_boot=300)
    assert ci == M.bootstrap_ci(vals, seed=3, n_boot=300)  # seeded => reproducible
    assert ci[0] <= M.mean(vals) <= ci[1] and ci != M.bootstrap_ci(vals, seed=4, n_boot=300)
    assert M.bootstrap_ci([1.0], seed=1) is None
    d = M.paired_bootstrap_diff([0.5, 0.6, 0.7, None], [0.4, 0.4, 0.4, 0.1], seed=1, n_boot=200)
    assert d["n"] == 3 and d["mean"] == pytest.approx(0.2) and d["ci95"][0] > 0


# ------------------------------------------------------------------ synthetic world
def test_world_is_deterministic_and_seed_dependent():
    a, b, c = make_world(TINY), make_world(TINY), make_world(SyntheticConfig(**{**TINY.to_dict(), "seed": 8}))
    assert a.items == b.items and a.test_users == b.test_users and a.new_item_ids == b.new_item_ids
    assert a.items != c.items
    assert len(a.new_item_ids) == round(TINY.new_item_fraction * TINY.n_items)


def test_engine_only_sees_masked_attributes_and_never_the_latent_ones():
    cfg = SyntheticConfig(seed=1, n_items=1000, catalogue_missing_rate=0.2, category_missing_rate=0.1)
    world = make_world(cfg)
    _, records = observed_catalogue(random.Random(1), world.items, cfg)
    n = len(records)
    assert abs(sum(r.cost_per_day_minor is None for r in records) / n - 0.2) < 0.05
    assert abs(sum(r.climate is None for r in records) / n - 0.2) < 0.05
    assert abs(sum(not r.categories for r in records) / n - 0.1) < 0.04
    assert not hasattr(records[0], "pop")  # latent popularity is not exposed
    visible = {r.id: r for r in records}
    assert all(visible[t.id].cost_per_day_minor in (None, t.cost) for t in world.items)  # masked, never altered


def test_stated_preferences_are_noisy_partial_and_can_be_absent():
    cfg = SyntheticConfig(seed=2)
    world = make_world(cfg)
    prefs = [stated_preferences(random.Random(i), u, cfg) for i, u in enumerate(world.test_users)]
    assert any(p["budget_per_day_minor"] is None for p in prefs) and any(p["climate"] is None for p in prefs)
    exact = [
        p["budget_per_day_minor"] == u.budget
        for p, u in zip(prefs, world.test_users, strict=True)
        if p["budget_per_day_minor"]
    ]
    assert not any(exact)  # budgets carry noise
    none = stated_preferences(random.Random(0), world.test_users[0], cfg, any_stated=False)
    assert none == {
        "interests": [],
        "budget_per_day_minor": None,
        "climate": None,
        "travel_month": None,
        "trip_days": None,
    }
    assert all(i in CATEGORY_WORDS for p in prefs for i in p["interests"])


def test_ground_truth_utility_behaves_sensibly():
    base = dict(cost=350000, days=5, season_start=1, season_end=12, climate="arid", pop=0.5)
    user = TrueUser("u", [1.0] + [0.0] * 7, 350000, "arid", 6, 5)
    liked = TrueItem("a", [0], **base)
    other = TrueItem("b", [3], **base)
    assert utility(user, liked) > utility(user, other)
    pricey = TrueItem("c", [0], **{**base, "cost": 900000})
    assert utility(user, liked) > utility(user, pricey)
    wrong_season = TrueItem("d", [0], **{**base, "season_start": 11, "season_end": 12})
    assert utility(user, liked) > utility(user, wrong_season)


# ------------------------------------------------------------------ experiment runner
def strip_runtime(r):
    return json.loads(json.dumps({**r, "runtime_seconds": 0}, sort_keys=True))


@pytest.fixture(scope="module")
def tiny_result():
    return run_experiment(TINY, k=5, n_boot=50)


def test_experiment_is_reproducible(tiny_result):
    assert strip_runtime(run_experiment(TINY, k=5, n_boot=50)) == strip_runtime(tiny_result)
    other = run_experiment(SyntheticConfig(**{**TINY.to_dict(), "seed": 8}), k=5, n_boot=50)
    assert strip_runtime(other) != strip_runtime(tiny_result)


def test_result_structure_is_complete_and_labelled_synthetic(tiny_result):
    assert "SYNTHETIC" in tiny_result["label"] and tiny_result["dataset"]["seed"] == 7
    assert set(tiny_result["scenarios"]) == set(SCENARIOS)
    for sc in tiny_result["scenarios"].values():
        assert set(sc["methods"]) == set(METHODS)
        for row in sc["methods"].values():
            assert {"precision@5", "recall@5", "ndcg@5", "intra_list_diversity", "cold_item_recall@5"} <= set(row)
            assert 0 <= row["precision@5"]["mean"] <= 1 and 0 <= row["catalog_coverage"] <= 1
            assert 0 <= row["ndcg@5"]["mean"] <= 1 and 0 <= row["intra_list_diversity"]["mean"] <= 1
    assert tiny_result["catalogue"]["n_cold_items_in_training"] >= round(TINY.new_item_fraction * TINY.n_items)


def test_personalised_methods_beat_random_and_popularity_cannot_reach_new_items(tiny_result):
    m = tiny_result["scenarios"]["cold_start_stated"]["methods"]
    assert m["weighted"]["precision@5"]["mean"] > m["random"]["precision@5"]["mean"]
    assert m["weighted"]["ndcg@5"]["mean"] > m["popularity"]["ndcg@5"]["mean"]
    assert m["popularity"]["cold_item_recall@5"]["mean"] == 0.0  # items with no interactions are never popular
    assert m["weighted"]["cold_item_recall@5"]["mean"] > 0.0
    assert m["popularity"]["catalog_coverage"] < m["weighted"]["catalog_coverage"]


def test_without_any_signal_personalised_methods_fall_back_to_popularity_exactly(tiny_result):
    m = tiny_result["scenarios"]["no_signal"]["methods"]
    for method in ("weighted", "cosine", "weighted_renormalize", "weighted_mmr"):
        assert m[method] == m["popularity"]


def test_mmr_trades_a_little_relevance_for_diversity(tiny_result):
    m = tiny_result["scenarios"]["cold_start_stated"]["methods"]
    assert m["weighted_mmr"]["intra_list_diversity"]["mean"] > m["weighted"]["intra_list_diversity"]["mean"]
    assert m["weighted_mmr"]["catalog_coverage"] >= m["weighted"]["catalog_coverage"] - 0.05


def test_outputs_are_written_as_json_csv_and_markdown(tmp_path):
    result = run_seeds([7, 8], TINY, k=5, n_boot=30)
    paths = write_outputs(result, tmp_path)
    assert {p.name for p in paths} == {"results.json", "results.csv", "summary.md"}
    data = json.loads((tmp_path / "results.json").read_text())
    assert data["seeds"] == [7, 8] and len(data["runs"]) == 2
    rows = list(csv.DictReader((tmp_path / "results.csv").open()))
    assert rows and set(rows[0]) == {"seed", "scenario", "method", "metric", "mean", "ci95_low", "ci95_high"}
    assert {r["seed"] for r in rows} == {"7", "8"}
    md = (tmp_path / "summary.md").read_text()
    assert "SYNTHETIC" in md and "cold_start_stated" in md and "Paired differences" in md and "Run parameters" in md
