import pytest

from app.modules.recommendations.engine.features import (
    CatalogStats,
    build_attraction_items,
    cosine,
    l1_normalize,
    match_interests,
    season_months,
)
from app.modules.recommendations.engine.types import AttractionRecord, HistoryItem

from .rec_fixtures import ADV, BEACH, CATS, HIST, items, profile


def test_l1_normalize_and_cosine():
    assert l1_normalize({"a": 2, "b": 2}) == {"a": 0.5, "b": 0.5}
    assert l1_normalize({}) == {} and l1_normalize({"a": 0}) == {}
    assert cosine({"a": 1}, {"a": 5}) == pytest.approx(1.0)
    assert cosine({"a": 1}, {"b": 1}) == 0.0
    assert cosine({}, {"a": 1}) == 0.0 and cosine({"a": 1}, {}) == 0.0
    assert cosine({"a": 1, "b": 1}, {"a": 1}) == pytest.approx(2**-0.5)


def test_season_months_wraps_over_new_year_and_unknown_is_none():
    assert season_months(10, 3) == frozenset({10, 11, 12, 1, 2, 3})
    assert season_months(6, 9) == frozenset({6, 7, 8, 9})
    assert season_months(5, 5) == frozenset({5})
    assert season_months(None, 3) is None and season_months(3, None) is None


def test_catalog_stats_normalisation_and_missing():
    s = CatalogStats([100, 200, 300, None])
    assert (s.min, s.max) == (100, 300)
    assert s.minmax(100) == 0.0 and s.minmax(300) == 1.0 and s.minmax(200) == 0.5
    assert s.minmax(None) is None
    assert s.percentile(100) < s.percentile(200) < s.percentile(300)
    assert s.percentile(None) is None
    # identical costs: min-max is undefined -> neutral 0.5, not a misleading extreme
    assert CatalogStats([5, 5]).minmax(5) == 0.5
    # a single known cost cannot define a percentile; empty catalogue is all-unknown
    assert CatalogStats([5, None]).percentile(5) is None
    assert CatalogStats([None]).minmax(5) is None


def test_tied_costs_share_a_mid_rank_percentile():
    s = CatalogStats([100, 200, 200, 300])
    assert s.percentile(200) == pytest.approx(0.5)


def test_interest_matching_tokens_synonyms_and_unmatched():
    matched, unmatched = match_interests(["History", "forts", "street food", "Beaches", "kayaking", "Markets"], CATS)
    assert matched["History"] == ["history-heritage"]
    assert matched["forts"] == ["history-heritage"]
    assert matched["street food"] == ["food-markets"]
    assert matched["Beaches"] == ["beach"]
    assert matched["Markets"] == ["food-markets"]
    assert unmatched == ["kayaking"]


def test_destination_items_encode_categories_and_leave_unknowns_unknown():
    its, _ = items()
    by = {i.name: i for i in its}
    jaipur, mystery = by["Jaipur"], by["Mystery Island"]
    assert sum(jaipur.category_vec.values()) == pytest.approx(1.0)
    assert (
        jaipur.category_vec["history-heritage"] > jaipur.category_vec["food-markets"]
    )  # attractions reinforce history
    assert mystery.category_vec == {} and mystery.season_months is None and mystery.climate is None
    assert mystery.cost_norm is None and all(v is None for v in mystery.styles.values())  # nothing invented
    assert by["Manali"].cost_norm == 0.0 and by["Ladakh"].cost_norm == 1.0  # min-max over known costs
    assert by["Manali"].styles["budget"] > by["Ladakh"].styles["budget"]
    assert by["Ladakh"].styles["luxury"] > by["Manali"].styles["luxury"]
    assert by["Manali"].styles["adventure"] > by["Kerala"].styles["adventure"]
    assert by["Kerala"].styles["relaxed"] > by["Manali"].styles["relaxed"]


def test_attraction_items_unknown_cost_stays_unknown():
    recs = [
        AttractionRecord("a1", "Fort", "d", HIST, cost_minor=None, is_outdoor=True),
        AttractionRecord("a2", "Beach Walk", "d", BEACH, cost_minor=0, is_outdoor=True),
        AttractionRecord("a3", "Rafting", "d", ADV, cost_minor=100000, is_outdoor=True),
    ]
    its, stats = build_attraction_items(recs)
    assert its[0].cost_norm is None and its[0].styles["budget"] is None
    assert its[1].cost_norm == 0.0 and its[2].cost_norm == 1.0
    assert (
        its[2].styles["adventure"] == 1.0 and its[0].styles["adventure"] == 0.5 * 1.0
    )  # outdoor, not adventure category
    assert its[0].category_vec == {"history-heritage": 1.0}


def test_profile_ignores_any_and_unrecognised_values_with_notes():
    p = profile(climate="any", style="wild", season="blue moon", interests=["kayaking"])
    assert p.climate is None and p.style is None and p.season_months is None and not p.interest_vec
    assert not any(p.applicable.values())
    assert len(p.notes) == 3  # 'any' climate is a valid 'no preference', so it adds no note


def test_travel_month_beats_named_season():
    p = profile(season="winter", travel_month=7)
    assert p.season_months == frozenset({7}) and p.season_label == "July"
    assert profile(season="monsoon").season_months == frozenset({7, 8, 9})


def test_history_alone_creates_interest_and_blends_with_stated():
    hist = [HistoryItem(1.0, {"adventure": 1.0})]
    only_hist = profile(history=hist)
    assert only_hist.interest_vec == {"adventure": 1.0} and only_hist.has_history
    assert any("inferred" in n for n in only_hist.notes)
    blended = profile(interests=["history"], history=hist)
    assert blended.interest_vec["history-heritage"] == pytest.approx(0.7)
    assert blended.interest_vec["adventure"] == pytest.approx(0.3)


def test_negative_history_reduces_a_category_but_cannot_go_below_zero():
    p = profile(interests=["history", "beach"], history=[HistoryItem(-1.0, {"beach": 1.0})])
    assert p.interest_vec["history-heritage"] > p.interest_vec["beach"]
    only_neg = profile(history=[HistoryItem(-1.0, {"beach": 1.0})])
    assert only_neg.interest_vec == {} and only_neg.has_history
