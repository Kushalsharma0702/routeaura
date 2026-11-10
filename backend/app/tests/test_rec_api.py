import pytest
from sqlalchemy import func, select

from app.models.catalog import Destination
from app.models.recommendations import RecommendationFeedback, RecommendationItem, RecommendationRun, UserInteraction

from .conftest import auth

API = "/api/v1"
REC_D, REC_A = f"{API}/recommendations/destinations", f"{API}/recommendations/attractions"


def register(client, email):
    r = client.post(
        f"{API}/auth/register", json={"email": email, "password": "Passw0rdOK", "full_name": email.split("@")[0]}
    )
    assert r.status_code == 201, r.text
    return r.json()["access_token"]


@pytest.fixture
def tok(client, seeded):
    return register(client, "ava@example.com")


@pytest.fixture
def tok2(client, seeded):
    return register(client, "ben@example.com")


def setprefs(client, token, **kw):
    r = client.put(f"{API}/users/me/preferences", json=kw, headers=auth(token))
    assert r.status_code == 200, r.text


def rec(client, token, kind=REC_D, **body):
    r = client.post(kind, json=body, headers=auth(token))
    assert r.status_code == 200, r.text
    return r.json()


def names(resp):
    return [(i["destination"] or i["attraction"])["name"] for i in resp["items"]]


def find(resp, name):
    return next(i for i in resp["items"] if (i["destination"] or i["attraction"])["name"] == name)


def interact(client, token, kind, item_id, t, **extra):
    r = client.post(
        f"{API}/interactions",
        json={"item_type": kind, "item_id": item_id, "interaction_type": t, **extra},
        headers=auth(token),
    )
    return r


def dest_id(client, token, name):
    return find(rec(client, token, page_size=50, strategy="popularity"), name)["destination"]["id"]


# ------------------------------------------------------------------ authentication & validation
def test_all_endpoints_require_authentication(client, seeded):
    for method, url in [
        ("post", REC_D),
        ("post", REC_A),
        ("get", f"{API}/recommendations/history"),
        ("post", f"{API}/recommendations/feedback"),
        ("post", f"{API}/interactions"),
        ("get", f"{API}/interactions/saved"),
        ("get", f"{API}/recommendations/history/00000000-0000-0000-0000-000000000000"),
    ]:
        assert getattr(client, method)(url).status_code == 401, url


@pytest.mark.parametrize(
    "body",
    [
        {"page_size": 51},
        {"page": 0},
        {"strategy": "magic"},
        {"diversity_lambda": 1.5},
        {"priorities": {"weather": "high"}},
        {"priorities": {"budget": "extreme"}},
        {"priorities": {f: "ignore" for f in ("interest", "budget", "duration", "climate", "season", "style")}},
        {"overrides": {"travel_month": 13}},
        {"overrides": {"trip_duration_days": 0}},
        {"overrides": {"preferred_climate": "lava"}},
        {"overrides": {"travel_style": "wild"}},
        {"overrides": {"budget_per_day_minor": -1}},
        {"filters": {"destination_id": "00000000-0000-0000-0000-000000000000"}},
        {"filters": {"outdoor": True}},
    ],
)
def test_invalid_destination_requests_are_rejected(client, tok, body):
    assert client.post(REC_D, json=body, headers=auth(tok)).status_code == 422


def test_destination_only_filters_rejected_for_attractions(client, tok):
    for f in ({"country": "India"}, {"climate": "cold"}, {"max_cost_minor": 1}):
        assert client.post(REC_A, json={"filters": f}, headers=auth(tok)).status_code == 422


# ------------------------------------------------------------------ personalised ranking with explanations
def test_saved_preferences_drive_the_ranking_and_every_item_is_explained(client, tok):
    setprefs(
        client,
        tok,
        interests=["history", "food"],
        budget_per_day_minor=400000,
        preferred_climate="arid",
        trip_duration_days=4,
        preferred_season="winter",
        travel_style="comfort",
    )
    r = rec(client, tok)
    assert names(r)[0] == "Jaipur" and r["strategy"] == "weighted" and r["model_version"] == "content-v1"
    top = r["items"][0]
    assert top["confidence"] == 1.0 and 0.0 < top["score"] <= 1.0 and top["rank"] == 1
    assert "not probabilities" in r["disclaimer"]
    feats = {c["feature"]: c for c in top["components"]}
    assert all(feats[f]["status"] == "matched" for f in ("interest", "budget", "climate", "season", "duration"))
    assert any("history" in x.lower() for x in top["reasons"])  # why selected / matched interests
    assert any("within your" in x for x in top["reasons"])  # budget compatibility
    assert any("Arid climate" in x for x in top["reasons"])  # climate compatibility
    assert any("best season" in x for x in top["reasons"])  # seasonal compatibility
    assert sum(c["weight"] for c in top["components"]) == pytest.approx(1.0)
    last = r["items"][-1]
    assert last["cautions"]  # mismatches are stated, not hidden
    assert (
        r["applied_preferences"]["interests"] == ["food", "history"]
        and r["applied_preferences"]["sources"]["interests"] == "saved"
    )
    assert r["total_candidates"] == 5 and r["effective_weights"]["interest"] == 0.35


def test_changing_saved_preferences_changes_the_ranking(client, tok):
    setprefs(client, tok, interests=["history"])
    assert names(rec(client, tok))[0] == "Jaipur"
    setprefs(client, tok, interests=["beach", "nature"], preferred_climate="tropical")
    assert names(rec(client, tok))[0] == "Kerala"
    setprefs(client, tok, interests=["adventure"], preferred_season="monsoon")
    assert names(rec(client, tok, diversify=False))[0] == "Ladakh"  # Jun-Sep is Ladakh's best season


def test_request_overrides_beat_saved_preferences_and_are_labelled(client, tok):
    setprefs(client, tok, interests=["history"], budget_per_day_minor=400000)
    r = rec(client, tok, overrides={"interests": ["adventure"], "travel_month": 7}, diversify=False)
    assert names(r)[0] == "Ladakh"
    src = r["applied_preferences"]["sources"]
    assert src["interests"] == "request" and src["travel_month"] == "request" and src["budget_per_day_minor"] == "saved"
    cleared = rec(client, tok, overrides={"budget_per_day_minor": None})
    assert cleared["applied_preferences"]["budget_per_day_minor"] is None  # sending null clears the saved value
    assert rec(client, tok, overrides={"interests": []})["applied_preferences"]["interests"] == []


def test_unmatched_interests_and_unused_preferences_are_reported(client, tok):
    setprefs(client, tok, interests=["history", "kayaking"], group_size=4, accommodation_preference="hotel")
    r = rec(client, tok)
    assert "kayaking" in r["applied_preferences"]["unmatched_interests"]
    assert any("kayaking" in n for n in r["notes"]) and any("group size" in n for n in r["notes"])
    assert any("accommodation preference" in n for n in r["notes"])


def test_budget_incompatibility_is_penalised_and_explained(client, tok):
    r = rec(client, tok, overrides={"budget_per_day_minor": 250000, "interests": ["adventure"]}, diversify=False)
    ladakh, manali = find(r, "Ladakh"), find(r, "Manali")
    assert ladakh["score"] < manali["score"]
    assert any("Clearly over budget" in c or "above your" in c for c in ladakh["cautions"])


def test_priorities_change_the_ranking(client, tok):
    base = {"overrides": {"budget_per_day_minor": 300000, "interests": ["history"]}, "diversify": False}
    interest_first = rec(client, tok, **base, priorities={"interest": "high", "budget": "low"})
    budget_first = rec(client, tok, **base, priorities={"interest": "low", "budget": "high"})
    # Manali is the only place inside the budget but has no history: a budget-heavy weighting must lift it
    # relative to the history-led leader, even though the order of the top three is unchanged here
    assert find(budget_first, "Manali")["score"] > find(interest_first, "Manali")["score"]
    gap = lambda r: find(r, "Jaipur")["score"] - find(r, "Manali")["score"]  # noqa: E731
    assert gap(budget_first) < gap(interest_first)
    assert budget_first["effective_weights"]["budget"] == pytest.approx(0.4)
    assert interest_first["effective_weights"]["interest"] == pytest.approx(0.7)


# ------------------------------------------------------------------ published-only & filters & pagination
def test_only_published_records_are_recommended(client, tok, db):
    setprefs(client, tok, interests=["beach"])
    assert "Goa" in names(rec(client, tok, page_size=50))
    db.execute(Destination.__table__.update().where(Destination.name == "Goa").values(is_published=False))
    db.commit()
    assert "Goa" not in names(rec(client, tok, page_size=50))
    attr_names = names(rec(client, tok, REC_A, page_size=50))
    assert not {"Baga Beach", "Fort Aguada"} & set(attr_names)  # Goa's attractions disappear with it
    assert len(attr_names) == 16


def test_filters(client, tok):
    setprefs(client, tok, interests=["adventure"])
    assert set(names(rec(client, tok, filters={"category": "beach"}, page_size=50))) == {"Goa", "Kerala"}
    assert set(names(rec(client, tok, filters={"climate": "cold"}, page_size=50))) == {"Manali", "Ladakh"}
    assert names(rec(client, tok, filters={"country": "India", "max_cost_minor": 320000}, page_size=50)) and set(
        names(rec(client, tok, filters={"max_cost_minor": 320000}, page_size=50))
    ) == {"Manali", "Jaipur"}
    assert rec(client, tok, filters={"country": "Nepal"})["items"] == []
    assert rec(client, tok, filters={"category": "beach"})["total_candidates"] == 2


def test_pagination_is_consistent_and_ranks_are_absolute(client, tok):
    setprefs(client, tok, interests=["history", "adventure"])
    pages = [rec(client, tok, page=p, page_size=2) for p in (1, 2, 3)]
    seen = [n for pg in pages for n in names(pg)]
    assert len(seen) == len(set(seen)) == 5
    assert [i["rank"] for pg in pages for i in pg["items"]] == [1, 2, 3, 4, 5]
    assert all(pg["total_candidates"] == 5 and pg["page_size"] == 2 for pg in pages)
    assert rec(client, tok, page=9, page_size=2)["items"] == []


def test_diversity_reranking_is_optional_and_keeps_the_best_item(client, tok):
    setprefs(client, tok, interests=["adventure", "culture"])
    plain = rec(client, tok, diversify=False, page_size=5)
    div = rec(client, tok, diversify=True, diversity_lambda=0.3, page_size=5)
    assert plain["diversified"] is False and div["diversified"] is True and div["diversity_lambda"] == 0.3
    assert names(plain)[0] == names(div)[0]
    assert all(i["original_rank"] >= 1 for i in div["items"])
    same = rec(client, tok, diversify=True, diversity_lambda=1.0, page_size=5)
    assert names(same) == names(plain)


# ------------------------------------------------------------------ strategies, cold start & popularity
def test_cold_start_without_signal_falls_back_to_popularity_and_says_so(client, tok, tok2):
    r = rec(client, tok)
    assert r["strategy"] == "popularity_fallback" and r["diversified"] is False
    assert any("popular places" in n.lower() for n in r["notes"])
    assert all(
        i["components"] == [] or all(c["status"] == "not_applicable" for c in i["components"]) for i in r["items"]
    )
    # another user's interactions create (aggregate) popularity
    goa = dest_id(client, tok2, "Goa")
    interact(client, tok2, "destination", goa, "save")
    assert names(rec(client, tok))[0] == "Goa"
    assert rec(client, tok)["items"][0]["reasons"] == ["Popular with other travelers."]


def test_explicit_strategies(client, tok):
    setprefs(client, tok, interests=["history"], budget_per_day_minor=1)
    cos = rec(client, tok, strategy="cosine", diversify=False)
    assert cos["strategy"] == "cosine" and cos["model_version"] == "cosine-v1" and names(cos)[0] == "Jaipur"
    assert [c["feature"] for c in cos["items"][0]["components"] if c["status"] != "not_applicable"] == ["interest"]
    pop = rec(client, tok, strategy="popularity")
    assert pop["strategy"] == "popularity" and pop["diversified"] is False


def test_missing_catalogue_data_lowers_confidence_instead_of_inflating_scores(client, tok, db):
    db.execute(
        Destination.__table__.update()
        .where(Destination.name == "Kerala")
        .values(
            estimated_cost_per_day_minor=None, best_season_start_month=None, best_season_end_month=None, climate=None
        )
    )
    db.commit()
    r = rec(
        client,
        tok,
        overrides={
            "interests": ["beach", "nature"],
            "budget_per_day_minor": 500000,
            "preferred_climate": "tropical",
            "travel_month": 1,
        },
        diversify=False,
        page_size=5,
    )
    kerala = find(r, "Kerala")
    assert kerala["confidence"] < 1.0 and len(kerala["missing"]) == 3
    assert any("could not be assessed" in m for m in kerala["missing"])
    assert [c["status"] for c in kerala["components"] if c["feature"] in ("budget", "climate", "season")] == [
        "unknown"
    ] * 3
    assert kerala["score"] < find(r, "Goa")["score"]  # a fully-known tropical beach place beats the data-poor one


# ------------------------------------------------------------------ attraction recommendations
def test_attraction_recommendations(client, tok):
    setprefs(client, tok, interests=["adventure"], budget_per_day_minor=500000, trip_duration_days=3)
    r = rec(client, tok, REC_A, diversify=False, page_size=6)
    top = names(r)[:4]
    assert set(top) == {"Rohtang Pass", "Solang Valley", "Khardung La"} | {top[3]} and r["kind"] == "attraction"
    first = r["items"][0]
    assert first["attraction"]["category"]["slug"] == "adventure" and first["destination"] is None
    budget = next(c for c in first["components"] if c["feature"] == "budget")
    assert budget["status"] == "unknown" and any(
        "entry fee" in m.lower() for m in first["missing"]
    )  # seed data has no fees
    assert first["confidence"] < 1.0
    assert next(c for c in first["components"] if c["feature"] == "duration")["status"] == "not_applicable"


def test_attraction_filters_and_trip_length_alone_is_not_a_signal(client, tok):
    setprefs(client, tok, interests=["history"])
    jaipur = dest_id(client, tok, "Jaipur")
    r = rec(client, tok, REC_A, filters={"destination_id": jaipur}, page_size=10)
    assert r["total_candidates"] == 4 and set(names(r)) == {"Hawa Mahal", "Amber Fort", "City Palace", "Jantar Mantar"}
    assert set(names(rec(client, tok, REC_A, filters={"outdoor": True}, page_size=50))) >= {"Baga Beach"}
    assert all(
        i["attraction"]["is_outdoor"] for i in rec(client, tok, REC_A, filters={"outdoor": True}, page_size=50)["items"]
    )
    setprefs(client, tok, interests=[], trip_duration_days=5)
    assert rec(client, tok, REC_A)["strategy"] == "popularity_fallback"  # duration does not apply to attractions


# ------------------------------------------------------------------ persistence
def test_every_request_persists_a_run_with_snapshot_config_and_impressions(client, tok, db):
    setprefs(client, tok, interests=["history"], budget_per_day_minor=400000)
    r = rec(client, tok, page_size=3, priorities={"budget": "high"})
    run = db.get(RecommendationRun, r["run_id"])
    assert (
        run.kind == "destination"
        and run.strategy == "weighted"
        and run.returned_count == 3
        and run.total_candidates == 5
    )
    assert run.preferences["interests"] == ["history"] and run.preferences["budget_per_day_minor"] == 400000
    assert run.config["weights"]["budget"] == pytest.approx(0.4) and run.priorities == {"budget": "high"}
    assert run.latency_ms is not None and run.diversified is True
    items = db.scalars(
        select(RecommendationItem).where(RecommendationItem.run_id == run.id).order_by(RecommendationItem.rank)
    ).all()
    assert [i.rank for i in items] == [1, 2, 3]
    assert all(i.destination_id and not i.attraction_id and i.explanation["components"] for i in items)
    assert [str(i.id) for i in items] == [x["recommendation_item_id"] for x in r["items"]]


# ------------------------------------------------------------------ interactions
def test_interactions_are_idempotent_and_derive_state(client, tok, db):
    d = dest_id(client, tok, "Goa")
    a = interact(client, tok, "destination", d, "save").json()
    assert a["recorded"] is True and a["state"]["saved"] is True
    b = interact(client, tok, "destination", d, "save").json()
    assert b["recorded"] is False and b["state"]["saved"] is True  # no duplicate event
    assert interact(client, tok, "destination", d, "like").json()["state"]["liked"] is True
    s = interact(client, tok, "destination", d, "dislike").json()["state"]
    assert s["disliked"] is True and s["liked"] is False
    assert interact(client, tok, "destination", d, "reaction_clear").json()["state"] == {
        "saved": True,
        "liked": False,
        "disliked": False,
        "dismissed": False,
    }
    assert interact(client, tok, "destination", d, "unsave").json()["state"]["saved"] is False
    assert db.scalar(select(func.count()).select_from(UserInteraction)) == 5
    st = client.get(f"{API}/interactions/state", params={"item_type": "destination", "item_id": d}, headers=auth(tok))
    assert st.status_code == 200 and st.json()["saved"] is False


def test_repeated_views_within_minutes_are_deduplicated_but_clicks_count(client, tok, db):
    d = dest_id(client, tok, "Goa")
    assert interact(client, tok, "destination", d, "view").json()["recorded"] is True
    assert interact(client, tok, "destination", d, "view").json()["recorded"] is False
    assert interact(client, tok, "destination", d, "click").json()["recorded"] is True
    assert interact(client, tok, "destination", d, "click").json()["recorded"] is True
    assert db.scalar(select(func.count()).select_from(UserInteraction)) == 3


def test_interaction_targets_must_exist_and_be_published(client, tok, db):
    zero = "00000000-0000-0000-0000-000000000000"
    assert interact(client, tok, "destination", zero, "save").status_code == 404
    assert interact(client, tok, "attraction", zero, "save").status_code == 404
    d = dest_id(client, tok, "Goa")
    db.execute(Destination.__table__.update().where(Destination.name == "Goa").values(is_published=False))
    db.commit()
    assert interact(client, tok, "destination", d, "save").status_code == 404
    assert (
        client.get(
            f"{API}/interactions/state", params={"item_type": "destination", "item_id": d}, headers=auth(tok)
        ).status_code
        == 404
    )
    assert interact(client, tok, "destination", zero, "teleport").status_code == 422


def test_interactions_can_reference_only_your_own_matching_impression(client, tok, tok2):
    setprefs(client, tok, interests=["history"])
    r = rec(client, tok)
    item = r["items"][0]
    ok = interact(
        client,
        tok,
        "destination",
        item["destination"]["id"],
        "click",
        source="recommendation",
        recommendation_item_id=item["recommendation_item_id"],
    )
    assert ok.status_code == 200 and ok.json()["recorded"] is True
    # someone else's impression id behaves exactly like a missing one
    assert (
        interact(
            client,
            tok2,
            "destination",
            item["destination"]["id"],
            "click",
            recommendation_item_id=item["recommendation_item_id"],
        ).status_code
        == 404
    )
    # right impression, wrong item
    other = r["items"][1]["destination"]["id"]
    assert (
        interact(
            client, tok, "destination", other, "click", recommendation_item_id=item["recommendation_item_id"]
        ).status_code
        == 404
    )


def test_saved_list_shows_only_my_published_saved_items(client, tok, tok2, db):
    goa, jaipur = dest_id(client, tok, "Goa"), dest_id(client, tok, "Jaipur")
    interact(client, tok, "destination", goa, "save")
    interact(client, tok, "destination", jaipur, "save")
    interact(client, tok2, "destination", dest_id(client, tok2, "Manali"), "save")
    saved = client.get(f"{API}/interactions/saved", headers=auth(tok)).json()
    assert saved["total"] == 2 and [s["destination"]["name"] for s in saved["items"]] == [
        "Jaipur",
        "Goa",
    ]  # newest first
    assert (
        client.get(f"{API}/interactions/saved", params={"item_type": "attraction"}, headers=auth(tok)).json()["total"]
        == 0
    )
    assert (
        client.get(f"{API}/interactions/saved", params={"page_size": 1, "page": 2}, headers=auth(tok)).json()["items"][
            0
        ]["destination"]["name"]
        == "Goa"
    )
    db.execute(Destination.__table__.update().where(Destination.name == "Goa").values(is_published=False))
    db.commit()
    assert client.get(f"{API}/interactions/saved", headers=auth(tok)).json()["total"] == 1


def test_item_flags_reflect_the_users_own_state_only(client, tok, tok2):
    setprefs(client, tok, interests=["history"])
    setprefs(client, tok2, interests=["history"])
    jaipur = dest_id(client, tok, "Jaipur")
    interact(client, tok, "destination", jaipur, "save")
    assert find(rec(client, tok, page_size=5), "Jaipur")["saved"] is True
    assert find(rec(client, tok2, page_size=5), "Jaipur")["saved"] is False


# ------------------------------------------------------------------ history influences recommendations
def test_saved_and_liked_items_shape_recommendations_when_no_interests_are_stated(client, tok):
    for n in ("Jaipur", "Goa"):
        interact(client, tok, "destination", dest_id(client, tok, n), "save")
    r = rec(client, tok, diversify=False, page_size=5)
    assert r["strategy"] == "weighted" and r["applied_preferences"]["used_history"] is True
    assert any("inferred" in n for n in r["notes"])
    assert names(r)[:2] == ["Jaipur", "Goa"]  # history + heritage places the user saved
    assert any("saved, liked or viewed" in x for x in r["items"][0]["reasons"])


def test_dismissed_and_disliked_items_are_hidden_unless_requested(client, tok):
    setprefs(client, tok, interests=["history"])
    jaipur, goa = dest_id(client, tok, "Jaipur"), dest_id(client, tok, "Goa")
    interact(client, tok, "destination", jaipur, "dismiss")
    interact(client, tok, "destination", goa, "dislike")
    r = rec(client, tok, page_size=50)
    assert "Jaipur" not in names(r) and "Goa" not in names(r) and r["total_candidates"] == 3
    back = rec(client, tok, page_size=50, include_dismissed=True)
    assert {"Jaipur", "Goa"} <= set(names(back))
    interact(client, tok, "destination", jaipur, "restore")
    assert "Jaipur" in names(rec(client, tok, page_size=50))


def test_negative_history_lowers_a_category_for_that_user_only(client, tok, tok2):
    for t in (tok, tok2):
        setprefs(client, t, interests=["history", "beach"])
    base = rec(client, tok, diversify=False, page_size=5)
    kerala0, jaipur0 = find(base, "Kerala")["score"], find(base, "Jaipur")["score"]
    baga = find(rec(client, tok, REC_A, page_size=50), "Baga Beach")["attraction"]["id"]  # a pure "beach" attraction
    interact(client, tok, "attraction", baga, "dislike")
    after = rec(client, tok, diversify=False, page_size=5)
    assert find(after, "Kerala")["score"] < kerala0 < 1  # beach evidence went negative for this user
    assert find(after, "Jaipur")["score"] > jaipur0  # ...so the remaining interest (history) gains share
    other = rec(client, tok2, diversify=False, page_size=5)
    assert find(other, "Kerala")["score"] == pytest.approx(kerala0)  # nobody else is affected
    assert "Baga Beach" not in names(rec(client, tok, REC_A, page_size=50))  # and the disliked item itself is hidden


# ------------------------------------------------------------------ feedback
def test_feedback_is_persisted_updatable_and_private(client, tok, tok2, db):
    setprefs(client, tok, interests=["history"])
    item = rec(client, tok)["items"][0]
    iid = item["recommendation_item_id"]
    r = client.post(
        f"{API}/recommendations/feedback",
        json={
            "recommendation_item_id": iid,
            "rating": "not_relevant",
            "reasons": ["too_expensive", "too_expensive", "wrong_season"],
            "comment": "Too pricey",
        },
        headers=auth(tok),
    )
    assert r.status_code == 200 and r.json()["reasons"] == ["too_expensive", "wrong_season"]
    again = client.post(
        f"{API}/recommendations/feedback", json={"recommendation_item_id": iid, "rating": "relevant"}, headers=auth(tok)
    )
    assert again.json()["rating"] == "relevant" and again.json()["reasons"] == []
    assert db.scalar(select(func.count()).select_from(RecommendationFeedback)) == 1  # one row per user+impression
    # somebody else cannot rate (or discover) my impression
    assert (
        client.post(
            f"{API}/recommendations/feedback",
            json={"recommendation_item_id": iid, "rating": "relevant"},
            headers=auth(tok2),
        ).status_code
        == 404
    )
    for bad in (
        {"rating": "meh"},
        {"rating": "relevant", "reasons": ["because"]},
        {"rating": "relevant", "comment": "x" * 501},
    ):
        assert (
            client.post(
                f"{API}/recommendations/feedback", json={"recommendation_item_id": iid, **bad}, headers=auth(tok)
            ).status_code
            == 422
        )
    zero = "00000000-0000-0000-0000-000000000000"
    assert (
        client.post(
            f"{API}/recommendations/feedback",
            json={"recommendation_item_id": zero, "rating": "relevant"},
            headers=auth(tok),
        ).status_code
        == 404
    )


def test_feedback_shapes_future_recommendations(client, tok):
    setprefs(client, tok, interests=["history", "beach"])
    kerala0 = find(rec(client, tok, diversify=False, page_size=5), "Kerala")["score"]
    baga = find(rec(client, tok, REC_A, page_size=50), "Baga Beach")  # impression of a pure beach attraction
    r = client.post(
        f"{API}/recommendations/feedback",
        json={
            "recommendation_item_id": baga["recommendation_item_id"],
            "rating": "not_relevant",
            "reasons": ["not_my_interest"],
        },
        headers=auth(tok),
    )
    assert r.status_code == 200
    after = find(rec(client, tok, diversify=False, page_size=5), "Kerala")["score"]
    assert after < kerala0  # "not relevant" on a beach item lowers beach affinity


# ------------------------------------------------------------------ history & privacy
def test_history_lists_only_my_runs_and_details_are_private(client, tok, tok2):
    setprefs(client, tok, interests=["history"])
    a1, a2 = rec(client, tok), rec(client, tok, REC_A)
    rec(client, tok2, overrides={"interests": ["beach"]})
    h = client.get(f"{API}/recommendations/history", headers=auth(tok)).json()
    assert h["total"] == 2 and [r["kind"] for r in h["items"]] == ["attraction", "destination"]  # newest first
    assert h["items"][1]["top_items"][0] == "Jaipur" and h["items"][1]["preferences"]["interests"] == ["history"]
    assert (
        client.get(f"{API}/recommendations/history", params={"kind": "destination"}, headers=auth(tok)).json()["total"]
        == 1
    )
    assert (
        client.get(f"{API}/recommendations/history", params={"page_size": 1, "page": 2}, headers=auth(tok)).json()[
            "items"
        ][0]["kind"]
        == "destination"
    )
    assert client.get(f"{API}/recommendations/history", headers=auth(tok2)).json()["total"] == 1
    detail = client.get(f"{API}/recommendations/history/{a1['run_id']}", headers=auth(tok))
    assert detail.status_code == 200 and detail.json()["config"]["weights"]["interest"] == 0.35
    assert detail.json()["items"][0]["name"] == "Jaipur" and detail.json()["items"][0]["explanation"]["components"]
    # another user's run is indistinguishable from a missing one
    assert client.get(f"{API}/recommendations/history/{a1['run_id']}", headers=auth(tok2)).status_code == 404
    assert (
        client.get(f"{API}/recommendations/history/00000000-0000-0000-0000-000000000000", headers=auth(tok)).status_code
        == 404
    )
    _ = a2


def test_run_detail_includes_my_feedback(client, tok):
    setprefs(client, tok, interests=["history"])
    r = rec(client, tok)
    client.post(
        f"{API}/recommendations/feedback",
        json={"recommendation_item_id": r["items"][0]["recommendation_item_id"], "rating": "relevant"},
        headers=auth(tok),
    )
    d = client.get(f"{API}/recommendations/history/{r['run_id']}", headers=auth(tok)).json()
    assert d["items"][0]["feedback"] == "relevant" and d["items"][1]["feedback"] is None
