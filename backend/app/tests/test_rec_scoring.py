import pytest

from app.modules.recommendations.engine.config import COSINE_CONFIG, DEFAULT_CONFIG, FEATURES, ScoringConfig
from app.modules.recommendations.engine.scoring import score_item

from .rec_fixtures import items, profile


def by_name():
    return {i.name: i for i in items()[0]}


def comp(scored, feature):
    return next(c for c in scored.components if c.feature == feature)


def test_budget_within_slightly_over_and_far_over():
    its = by_name()
    p = profile(budget_per_day_minor=320000)
    assert comp(score_item(p, its["Jaipur"], DEFAULT_CONFIG), "budget").value == 1.0  # exactly at budget
    slight = comp(score_item(profile(budget_per_day_minor=300000), its["Jaipur"], DEFAULT_CONFIG), "budget")
    assert slight.value == pytest.approx(1 - (20000 / 300000) / 0.5)  # ~6.7% over
    assert 0.8 < slight.value < 1.0
    far = score_item(profile(budget_per_day_minor=200000), its["Jaipur"], DEFAULT_CONFIG)
    assert comp(far, "budget").value == 0.0 and far.multiplier == DEFAULT_CONFIG.budget_incompatible_multiplier
    assert any("Clearly over budget" in c for c in far.cautions)


def test_over_budget_penalty_is_applied_to_the_total_score():
    its = by_name()
    p = profile(budget_per_day_minor=100000, interests=["history"])
    s = score_item(p, its["Jaipur"], DEFAULT_CONFIG)
    unpenalised = sum(c.contribution for c in s.components)
    assert s.score == pytest.approx(unpenalised * DEFAULT_CONFIG.budget_incompatible_multiplier)


def test_unknown_data_gets_no_free_score_under_lower_bound():
    its = by_name()
    p = profile(
        budget_per_day_minor=500000,
        trip_days=4,
        climate="arid",
        season="winter",
        style="comfort",
        interests=["history"],
    )
    mystery = score_item(p, its["Mystery Island"], DEFAULT_CONFIG)
    assert mystery.score == 0.0 and mystery.confidence == 0.0
    assert len(mystery.missing) == 6 and all(c.status == "unknown" for c in mystery.components)
    known = score_item(p, its["Jaipur"], DEFAULT_CONFIG)
    assert known.score > mystery.score and known.confidence == 1.0


def test_renormalize_policy_drops_unknowns_but_confidence_still_reports_them():
    its = by_name()
    cfg = ScoringConfig(missing_policy="renormalize")
    p = profile(budget_per_day_minor=500000, interests=["history"])
    # an item with only a budget known: score comes from that single feature, confidence shows the gap
    partial = by_name()["Jaipur"]
    partial.category_vec = {}  # make interest unknown
    s = score_item(p, partial, cfg)
    assert s.score == pytest.approx(1.0) and s.confidence == pytest.approx(0.20 / 0.55)
    lb = score_item(p, partial, DEFAULT_CONFIG)
    assert lb.score == pytest.approx(0.20 / 0.55)
    assert lb.score < s.score  # lower bound is strictly more conservative
    _ = its


def test_weights_are_normalised_over_applicable_features_only():
    its = by_name()
    s = score_item(profile(budget_per_day_minor=500000, climate="arid"), its["Jaipur"], DEFAULT_CONFIG)
    applicable = [c for c in s.components if c.status != "not_applicable"]
    assert {c.feature for c in applicable} == {"budget", "climate"}
    assert sum(c.weight for c in applicable) == pytest.approx(1.0)
    assert comp(s, "budget").weight == pytest.approx(0.20 / 0.30)
    assert all(
        c.weight == 0 and c.status == "not_applicable"
        for c in s.components
        if c.feature in ("interest", "season", "style", "duration")
    )


def test_contributions_sum_to_score_before_multiplier_and_score_is_bounded():
    its = by_name()
    p = profile(
        budget_per_day_minor=330000,
        trip_days=5,
        climate="tropical",
        season="winter",
        style="relaxed",
        interests=["beach", "nature"],
    )
    for it in its.values():
        s = score_item(p, it, DEFAULT_CONFIG)
        assert s.score == pytest.approx(sum(c.contribution for c in s.components) * s.multiplier)
        assert 0.0 <= s.score <= 1.0 and 0.0 <= s.confidence <= 1.0


def test_no_applicable_preferences_scores_zero_with_zero_confidence():
    s = score_item(profile(), by_name()["Jaipur"], DEFAULT_CONFIG)
    assert s.score == 0.0 and s.confidence == 0.0 and all(c.status == "not_applicable" for c in s.components)


def test_duration_slack_and_ratio():
    its = by_name()
    assert (
        comp(score_item(profile(trip_days=5), its["Jaipur"], DEFAULT_CONFIG), "duration").value == 1.0
    )  # 4 vs 5: within slack
    assert comp(score_item(profile(trip_days=2), its["Ladakh"], DEFAULT_CONFIG), "duration").value == pytest.approx(
        0.25
    )  # 2 vs 8
    assert comp(score_item(profile(trip_days=4), its["Mystery Island"], DEFAULT_CONFIG), "duration").value is None


def test_climate_exact_adjacent_and_opposite():
    its = by_name()
    arid = profile(climate="arid")
    assert comp(score_item(arid, its["Jaipur"], DEFAULT_CONFIG), "climate").value == 1.0
    assert comp(score_item(arid, its["Manali"], DEFAULT_CONFIG), "climate").value == pytest.approx(0.15)
    assert comp(score_item(profile(climate="cold"), its["Kerala"], DEFAULT_CONFIG), "climate").value == 0.0
    assert comp(score_item(arid, its["Mystery Island"], DEFAULT_CONFIG), "climate").status == "unknown"


def test_season_full_partial_none_and_wraparound():
    its = by_name()
    month = lambda m, n: comp(score_item(profile(travel_month=m), its[n], DEFAULT_CONFIG), "season").value  # noqa: E731
    assert month(1, "Jaipur") == 1.0 and month(12, "Jaipur") == 1.0 and month(10, "Jaipur") == 1.0  # Oct-Mar wraps
    assert month(7, "Jaipur") == 0.0 and month(7, "Ladakh") == 1.0
    winter = comp(
        score_item(profile(season="winter"), its["Ladakh"], DEFAULT_CONFIG), "season"
    )  # Nov,Dec,Jan,Feb vs Jun-Sep
    assert winter.value == 0.0
    partial = comp(score_item(profile(season="autumn"), its["Kerala"], DEFAULT_CONFIG), "season")  # Oct,Nov vs Sep-Mar
    assert partial.value == 1.0
    partial2 = comp(
        score_item(profile(season="summer"), its["Manali"], DEFAULT_CONFIG), "season"
    )  # Apr,May,Jun vs Oct-Jun
    assert partial2.value == 1.0
    summer_goa = comp(score_item(profile(season="summer"), its["Goa"], DEFAULT_CONFIG), "season")  # Apr-Jun vs Oct-Mar
    assert summer_goa.value == 0.0
    spring_goa = comp(score_item(profile(season="spring"), its["Goa"], DEFAULT_CONFIG), "season")  # Feb,Mar vs Oct-Mar
    assert spring_goa.value == 1.0
    mix = comp(score_item(profile(season="monsoon"), its["Ladakh"], DEFAULT_CONFIG), "season")  # Jul-Sep vs Jun-Sep
    assert mix.value == 1.0
    half = comp(score_item(profile(season="winter"), its["Kerala"], DEFAULT_CONFIG), "season")  # Nov-Feb vs Sep-Mar
    assert half.value == 1.0
    assert (
        comp(score_item(profile(season="winter"), its["Mystery Island"], DEFAULT_CONFIG), "season").status == "unknown"
    )


def test_partial_season_overlap_gives_fractional_score():
    its = by_name()
    # winter = Nov,Dec,Jan,Feb; Manali best season Oct-Jun covers all; use spring+summer-like mix via month sets
    s = comp(score_item(profile(season="spring"), its["Ladakh"], DEFAULT_CONFIG), "season")  # Feb,Mar vs Jun-Sep -> 0
    assert s.value == 0.0 and s.status == "mismatch"
    from app.modules.recommendations.engine.types import UserProfile

    p = UserProfile(season_months=frozenset({5, 6, 7, 8}), season_label="my window")  # May-Aug vs Jun-Sep -> 3/4
    v = comp(score_item(p, its["Ladakh"], DEFAULT_CONFIG), "season")
    assert v.value == pytest.approx(0.75) and v.status == "matched"


def test_interest_similarity_orders_by_category_overlap():
    its = by_name()
    p = profile(interests=["history"])
    v = {n: comp(score_item(p, it, DEFAULT_CONFIG), "interest").value for n, it in its.items()}
    assert v["Jaipur"] > v["Goa"] > 0 and v["Manali"] == 0.0 and v["Mystery Island"] is None


def test_style_fit_budget_vs_luxury():
    its = by_name()
    cheap = comp(score_item(profile(style="budget"), its["Manali"], DEFAULT_CONFIG), "style").value
    dear = comp(score_item(profile(style="budget"), its["Ladakh"], DEFAULT_CONFIG), "style").value
    assert cheap > dear
    assert (
        comp(score_item(profile(style="luxury"), its["Ladakh"], DEFAULT_CONFIG), "style").value
        > comp(score_item(profile(style="luxury"), its["Manali"], DEFAULT_CONFIG), "style").value
    )


def test_explicit_priorities_change_weights():
    cfg = DEFAULT_CONFIG.with_priorities({"budget": "high", "interest": "ignore", "season": "low"})
    assert cfg.weights["budget"] == pytest.approx(0.40) and cfg.weights["interest"] == 0.0
    assert cfg.weights["season"] == pytest.approx(0.075) and cfg.weights["climate"] == 0.10
    p = profile(budget_per_day_minor=500000, interests=["history"])
    s = score_item(p, by_name()["Jaipur"], cfg)
    assert comp(s, "interest").status == "not_applicable" and comp(s, "budget").weight == pytest.approx(1.0)


def test_priority_flips_ranking_when_preferences_conflict():
    """Cheap adventure vs expensive history: high budget priority must favour the cheaper place."""
    from app.modules.recommendations.engine.ranking import rank_content

    its, _ = items()
    p = profile(budget_per_day_minor=300000, interests=["history"])
    interest_first = rank_content(p, its, DEFAULT_CONFIG.with_priorities({"interest": "high", "budget": "low"}))
    budget_first = rank_content(p, its, DEFAULT_CONFIG.with_priorities({"interest": "low", "budget": "high"}))
    assert interest_first[0].item.name == "Jaipur"
    assert budget_first.index(next(s for s in budget_first if s.item.name == "Manali")) < budget_first.index(
        next(s for s in budget_first if s.item.name == "Goa")
    )


def test_cosine_config_uses_interest_only():
    p = profile(budget_per_day_minor=1, interests=["history"], climate="cold")
    s = score_item(p, by_name()["Jaipur"], COSINE_CONFIG)
    assert [c.feature for c in s.components if c.status != "not_applicable"] == ["interest"]
    assert s.multiplier == 1.0  # budget feature is off, so no budget penalty either


def test_explanations_cover_matches_cautions_and_missing_info():
    its = by_name()
    p = profile(budget_per_day_minor=330000, climate="arid", season="monsoon", interests=["history"], trip_days=4)
    s = score_item(p, its["Jaipur"], DEFAULT_CONFIG)
    assert any("history" in r.lower() for r in s.reasons)  # why it was selected / which interest matched
    assert any("within your" in r for r in s.reasons)  # budget compatibility stated
    assert any("Arid climate matches" in r for r in s.reasons)  # climate compatibility stated
    assert any("outside its best season" in c for c in s.cautions)  # seasonal incompatibility stated
    m = score_item(p, its["Mystery Island"], DEFAULT_CONFIG)
    assert any("could not be assessed" in x for x in m.missing) and m.confidence == 0.0
    d = score_item(p, its["Jaipur"], DEFAULT_CONFIG).components
    assert all(c.to_dict()["detail"] for c in d)


def test_attraction_budget_uses_entry_fee_share_and_unknown_is_unknown():
    from app.modules.recommendations.engine.features import build_attraction_items
    from app.modules.recommendations.engine.types import AttractionRecord

    from .rec_fixtures import HIST

    recs = [
        AttractionRecord("a", "Cheap", "d", HIST, cost_minor=20000),
        AttractionRecord("b", "Dear", "d", HIST, cost_minor=600000),
        AttractionRecord("c", "Mystery", "d", HIST, cost_minor=None),
    ]
    its, _ = build_attraction_items(recs)
    p = profile(budget_per_day_minor=400000)
    vals = {i.name: comp(score_item(p, i, DEFAULT_CONFIG), "budget") for i in its}
    assert vals["Cheap"].value == 1.0 and vals["Dear"].value == 0.0 and vals["Mystery"].status == "unknown"
    assert "Duration" not in "".join(
        c.label
        for c in score_item(profile(trip_days=3), its[0], DEFAULT_CONFIG).components
        if c.status != "not_applicable"
    )


def test_feature_list_is_complete():
    s = score_item(profile(), by_name()["Jaipur"], DEFAULT_CONFIG)
    assert tuple(c.feature for c in s.components) == FEATURES


def test_month_ranges_are_compact_and_wrap_over_the_new_year():
    from app.modules.recommendations.engine.scoring import months_range_text as t

    assert t(frozenset({10, 11, 12, 1, 2, 3})) == "Oct-Mar"
    assert t(frozenset({6, 7, 8, 9})) == "Jun-Sep"
    assert t(frozenset({5})) == "May"
    assert t(frozenset({1, 2, 6})) == "Jan-Feb, Jun"
    assert t(frozenset(range(1, 13))) == "year-round"


def test_explanations_use_full_category_names_month_names_and_honest_partial_wording():
    from app.modules.recommendations.engine.features import build_destination_items

    from .rec_fixtures import CATS, DESTS

    its, _ = build_destination_items(DESTS, DEFAULT_CONFIG, CATS)
    manali = next(i for i in its if i.name == "Manali")
    p = profile(interests=["food", "scenic"], travel_month=1)
    s = score_item(p, manali, DEFAULT_CONFIG)
    interest = comp(s, "interest")
    assert interest.status == "partial" and interest.detail.startswith("Partly matches")
    assert "Food & Markets" in interest.detail  # category known only through attractions keeps its real name
    season = comp(s, "season")
    assert season.detail == "January falls within its best season (Oct-Jun)."
    assert not any(c.startswith("Matches") for c in s.cautions)
