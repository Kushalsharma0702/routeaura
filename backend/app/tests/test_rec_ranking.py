import pytest

from app.modules.recommendations.engine.config import DEFAULT_CONFIG
from app.modules.recommendations.engine.ranking import intra_list_diversity, mmr_rerank, rank_content, rank_popularity

from .rec_fixtures import items, names, profile


def rank(**kw):
    its, _ = items()
    return rank_content(profile(**kw), its, DEFAULT_CONFIG)


def test_preference_changes_produce_logical_ranking_changes():
    assert names(rank(interests=["history"]))[0] == "Jaipur"
    assert names(rank(interests=["adventure"]))[0] in ("Manali", "Ladakh")
    assert names(rank(interests=["beach", "nature"]))[0] == "Kerala"
    # same interests, different season: monsoon travellers should see the Jun-Sep destination move up
    winter = names(rank(interests=["adventure"], travel_month=1))
    july = names(rank(interests=["adventure"], travel_month=7))
    assert winter.index("Ladakh") > july.index("Ladakh") and july[0] == "Ladakh" and winter[0] == "Manali"


def test_budget_changes_reorder_results():
    rich = names(rank(budget_per_day_minor=1_000_000, interests=["adventure"]))
    poor = names(rank(budget_per_day_minor=300000, interests=["adventure"]))
    assert rich[:2] == ["Ladakh", "Manali"] or rich[0] in ("Ladakh", "Manali")
    assert poor[0] == "Manali"  # the only adventure destination inside a ₹3,000/day budget
    ranked_poor = rank(budget_per_day_minor=300000, interests=["adventure"])
    ladakh = next(s for s in ranked_poor if s.item.name == "Ladakh")
    manali = next(s for s in ranked_poor if s.item.name == "Manali")
    assert ladakh.score < manali.score
    # 40% over budget is only partly penalised (zero starts at 50% over), so no hard multiplier yet
    assert ladakh.multiplier == 1.0 and next(
        c for c in ladakh.components if c.feature == "budget"
    ).value == pytest.approx(0.2)
    clearly_over = next(
        s for s in rank(budget_per_day_minor=250000, interests=["adventure"]) if s.item.name == "Ladakh"
    )
    assert clearly_over.multiplier < 1.0


def test_climate_preference_moves_matching_destinations_up():
    cold = names(rank(climate="cold"))
    tropical = names(rank(climate="tropical"))
    assert set(cold[:2]) == {"Manali", "Ladakh"} and set(tropical[:2]) == {"Goa", "Kerala"}


def test_trip_length_preference():
    # +-1 day is a perfect match, so 7- and 8-day places tie at the top for an 8-day trip
    assert set(names(rank(trip_days=8))[:2]) == {"Kerala", "Ladakh"}
    assert names(rank(trip_days=3))[0] == "Jaipur" and names(rank(trip_days=3))[-1] == "Mystery Island"


def test_ranking_is_deterministic_and_ties_break_by_name():
    a, b = (
        rank(interests=["history"], budget_per_day_minor=400000),
        rank(interests=["history"], budget_per_day_minor=400000),
    )
    assert names(a) == names(b)
    tied = rank()  # no preferences: every score is 0 -> alphabetical
    assert names(tied) == sorted(names(tied), key=str.lower)
    assert [s.rank for s in a] == list(range(1, len(a) + 1)) and [s.original_rank for s in a] == [s.rank for s in a]


def test_missing_information_never_outranks_a_fully_known_match():
    ranked = rank(
        budget_per_day_minor=500000,
        interests=["history"],
        climate="arid",
        season="winter",
        trip_days=4,
        style="comfort",
    )
    assert names(ranked)[0] == "Jaipur" and names(ranked)[-1] == "Mystery Island"
    assert ranked[-1].confidence == 0.0 and ranked[0].confidence == 1.0


def test_popularity_baseline_orders_by_interactions_and_flags_missing_data():
    its, _ = items()
    ranked = rank_popularity(its, {"goa": 10, "jaipur": 4})
    assert names(ranked)[:2] == ["Goa", "Jaipur"] and ranked[0].score == 1.0 and ranked[1].score == pytest.approx(0.4)
    assert "Popular with other travelers." in ranked[0].reasons and ranked[-1].missing
    empty = rank_popularity(its, {})
    assert all(s.score == 0 for s in empty) and names(empty) == sorted(names(empty), key=str.lower)


def test_mmr_lambda_one_reproduces_the_relevance_ranking():
    base = rank(interests=["adventure", "beach", "history"])
    assert names(mmr_rerank(list(base), 5, 1.0)) == names(base)[:5]


def test_mmr_increases_diversity_and_keeps_the_top_item():
    base = rank(interests=["adventure"])
    top_k = base[:3]
    div = mmr_rerank(list(base), 3, 0.3)
    assert div[0].item.id == base[0].item.id  # relevance preserved at the top
    assert intra_list_diversity([s.item for s in div]) >= intra_list_diversity([s.item for s in top_k]) - 1e-12
    assert [s.rank for s in div] == [1, 2, 3]
    assert len({s.item.id for s in div}) == 3  # no duplicates


def test_mmr_demotes_a_near_duplicate_in_favour_of_a_different_item():
    from app.modules.recommendations.engine.features import build_destination_items
    from app.modules.recommendations.engine.types import ScoredItem

    from .rec_fixtures import ADV, HIST, dest

    recs = [
        dest("a", "A", [ADV], 300000, 5, 1, 12, "cold"),
        dest("b", "B", [ADV], 300000, 5, 1, 12, "cold"),
        dest("c", "C", [HIST], 300000, 5, 1, 12, "arid"),
    ]
    its, _ = build_destination_items(recs, DEFAULT_CONFIG)
    scored = [ScoredItem(item=i, score=s, confidence=1.0, components=[]) for i, s in zip(its, (0.90, 0.88, 0.80), strict=True)]
    assert [s.item.name for s in mmr_rerank(scored, 3, 1.0)] == ["A", "B", "C"]
    assert [s.item.name for s in mmr_rerank(scored, 3, 0.5)] == ["A", "C", "B"]  # near-duplicate B pushed down


def test_mmr_rejects_invalid_lambda_and_handles_small_inputs():
    with pytest.raises(ValueError):
        mmr_rerank(rank(interests=["history"]), 3, 1.5)
    assert mmr_rerank([], 3, 0.5) == []
    assert len(mmr_rerank(rank(interests=["history"]), 50, 0.7)) == 6


def test_intra_list_diversity_bounds():
    its, _ = items()
    assert intra_list_diversity(its[:1]) == 0.0
    d = intra_list_diversity(its)
    assert 0.0 < d <= 1.0
    assert intra_list_diversity([its[0], its[0]]) == pytest.approx(0.0)
