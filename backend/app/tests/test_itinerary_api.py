import json
from datetime import date, timedelta

import pytest
from sqlalchemy import func, select

from app.integrations.llm.base import LLMError
from app.integrations.llm.providers import NoLLM
from app.models.catalog import Attraction, Destination
from app.models.itinerary import Itinerary, ItineraryActivity, ItineraryVersion

from .conftest import auth

API = "/api/v1"


class FakeLLM:
    """Scripted model: returns queued replies (strings) or raises queued exceptions."""

    name, model = "fake", "fake-model"

    def __init__(self, *replies):
        self.replies, self.calls = list(replies), []

    def complete(self, system, user, *, max_tokens=2000):
        self.calls.append((system, user))
        r = self.replies.pop(0)
        if isinstance(r, Exception):
            raise r
        return r(user) if callable(r) else r


@pytest.fixture
def use_llm(monkeypatch):
    def install(llm):
        monkeypatch.setattr("app.modules.itinerary.service.get_llm", lambda: llm)
        return llm

    return install


def register(client, email):
    return client.post(
        f"{API}/auth/register", json={"email": email, "password": "Passw0rdOK", "full_name": "T"}
    ).json()["access_token"]


@pytest.fixture
def tok(client, seeded):
    return register(client, "tess@example.com")


@pytest.fixture
def tok2(client, seeded):
    return register(client, "uma@example.com")


@pytest.fixture
def jaipur(db):
    return db.scalar(select(Destination).where(Destination.slug == "jaipur"))


def gen(client, token, dest, **kw):
    body = {"destination_id": str(dest.id), "days": 2, "interests": ["history"], **kw}
    r = client.post(f"{API}/itineraries/generate", json=body, headers=auth(token))
    return r


def ids_of(it):
    return [a["id"] for d in it["day_plans"] for a in d["activities"]]


# ------------------------------------------------------------------ validation
@pytest.mark.parametrize(
    "body",
    [
        {"days": 0},
        {"days": 15},
        {"travelers": 0},
        {"travelers": 21},
        {"budget_total_minor": -1},
        {"days": None},
        {"start_date": "2001-01-01", "days": 2},
        {"end_date": "2030-01-02", "days": 2},
        {"start_date": "2030-01-05", "end_date": "2030-01-01"},
        {"start_date": "2030-01-01", "end_date": "2030-03-01"},
        {"start_date": "2030-01-01", "end_date": "2030-01-03", "days": 5},
        {"travel_style": "wild"},
        {"start_location": {"name": "x", "lat": 95, "lng": 0}},
    ],
)
def test_invalid_trip_requests_are_rejected(client, tok, jaipur, body):
    req = {"destination_id": str(jaipur.id), "days": 2, **body}
    assert client.post(f"{API}/itineraries/generate", json=req, headers=auth(tok)).status_code == 422


def test_unknown_or_unpublished_destination_and_empty_destination(client, tok, jaipur, db):
    zero = "00000000-0000-0000-0000-000000000000"
    r = client.post(f"{API}/itineraries/generate", json={"destination_id": zero, "days": 2}, headers=auth(tok))
    assert r.status_code == 422 and r.json()["error"]["code"] == "unknown_destination"
    db.execute(Attraction.__table__.update().where(Attraction.destination_id == jaipur.id).values(is_published=False))
    db.commit()
    r = gen(client, tok, jaipur)
    assert r.status_code == 422 and r.json()["error"]["code"] == "no_attractions"
    assert (
        client.post(f"{API}/itineraries/generate", json={"destination_id": str(jaipur.id), "days": 2}).status_code
        == 401
    )


# ------------------------------------------------------------------ deterministic fallback
def test_fallback_generation_is_valid_labelled_persisted_and_explained(client, tok, jaipur, db):
    r = gen(client, tok, jaipur, budget_total_minor=2_000_000, travelers=2)
    assert r.status_code == 201, r.text
    it = r.json()
    assert (
        it["generation_source"] == "deterministic_fallback" and it["status"] == "draft" and it["current_version"] == 1
    )
    assert any("deterministic planner" in n for n in it["generation_info"]["notes"])
    assert it["generation_info"]["llm"]["provider"] == "none" and "estimates" in it["generation_info"]["travel_times"]
    assert [s["step"] for s in it["generation_info"]["steps"]][:3] == [
        "validate",
        "rank_attractions",
        "deterministic_plan",
    ]
    assert len(it["day_plans"]) == 2 and it["violations"] == []
    acts = [a for d in it["day_plans"] for a in d["activities"]]
    assert 2 <= len(acts) <= 4 and len({a["attraction"]["id"] for a in acts}) == len(acts)  # no duplicates
    assert all(a["attraction"]["category"] == "History & Heritage" for a in acts)  # interest respected
    first = it["day_plans"][0]["activities"][0]
    assert first["start_time"] == "09:00" or first["travel_min"] >= 0
    assert first["travel_source"] == "estimate" and first["explanation"]["reasons"]
    assert any(
        "not verified" in w or "No travel date" in w for a in acts for w in a["warnings"]
    )  # seed data has no verified hours
    assert it["budget"]["unknown_cost_items"] == len(acts) and it["budget"]["within_budget"] is True
    assert it["budget"]["living_estimate_minor"] == 320000 * 2 * 2
    # persisted in PostgreSQL, with a version-1 snapshot
    assert db.scalar(select(func.count()).select_from(ItineraryActivity)) == len(acts)
    v = db.scalar(select(ItineraryVersion).where(ItineraryVersion.version == 1))
    assert v.summary == "Generated" and len(v.snapshot["activities"]) == len(acts)


def test_activity_times_never_overlap_and_stay_inside_the_day(client, tok, jaipur):
    it = gen(client, tok, jaipur, days=3).json()
    for d in it["day_plans"]:
        prev_end = 0
        for a in d["activities"]:
            assert a["start_min"] >= prev_end and a["end_min"] == a["start_min"] + a["duration_min"]
            prev_end = a["end_min"]
        if d["activities"]:
            assert prev_end <= 18 * 60


def test_budget_too_small_for_living_costs_reports_a_violation(client, tok, jaipur):
    it = gen(client, tok, jaipur, budget_total_minor=100_000).json()
    assert it["budget"]["within_budget"] is False and any(v["type"] == "budget" for v in it["violations"])
    assert sum(len(d["activities"]) for d in it["day_plans"]) <= 4


def test_dates_set_the_day_count_and_enable_date_labels(client, tok, jaipur):
    start = date.today() + timedelta(days=30)
    it = gen(
        client, tok, jaipur, days=None, start_date=start.isoformat(), end_date=(start + timedelta(days=2)).isoformat()
    ).json()
    assert it["days"] == 3 and it["day_plans"][2]["date"] == (start + timedelta(days=2)).isoformat()


def test_start_location_drives_the_first_stop(client, tok, jaipur):
    near_amber = gen(
        client,
        tok,
        jaipur,
        interests=["history"],
        days=1,
        start_location={"name": "Amber", "lat": 26.9855, "lng": 75.8513},
    ).json()
    assert (
        near_amber["day_plans"][0]["activities"][0]["attraction"]["name"] == "Amber Fort"
    )  # nearest to the start point first
    assert near_amber["start_location"]["name"] == "Amber"
    in_town = gen(
        client,
        tok,
        jaipur,
        interests=["history"],
        days=1,
        start_location={"name": "Hawa", "lat": 26.9239, "lng": 75.8267},
    ).json()
    assert in_town["day_plans"][0]["activities"][0]["attraction"]["name"] == "Hawa Mahal"


# ------------------------------------------------------------------ LLM path
def good_plan(user):
    cands = json.JSONDecoder().raw_decode(user)[0]["attractions"]  # retries append text after the JSON prompt
    ids = [c["id"] for c in cands]
    return json.dumps(
        {
            "days": [
                {"day": 1, "attraction_ids": ids[:2], "theme": "Old city", "rationale": "Close together."},
                {"day": 2, "attraction_ids": ids[2:4], "theme": "Forts", "rationale": "Hill forts."},
            ]
        }
    )


def test_llm_plan_is_validated_then_scheduled_by_code(client, tok, jaipur, use_llm):
    llm = use_llm(FakeLLM(good_plan))
    it = gen(client, tok, jaipur).json()
    assert it["generation_source"] == "llm" and it["generation_info"]["llm"] == {
        "provider": "fake",
        "model": "fake-model",
    }
    assert any("computed by the app" in n for n in it["generation_info"]["notes"])
    assert it["generation_info"]["themes"]["1"]["theme"] == "Old city"
    assert it["day_plans"][0]["activities"][0]["explanation"]["llm"]["rationale"] == "Close together."
    assert it["violations"] == [] and len(llm.calls) == 1
    assert "Do NOT output times" in llm.calls[0][0]  # the model is told it may not set numbers


@pytest.mark.parametrize(
    "bad",
    [
        "not json at all",
        '{"days": "nope"}',
        '{"days": []}',
        '{"days": [{"day": 1, "attraction_ids": ["00000000-0000-0000-0000-000000000000"]}]}',  # invented id
        '{"days": [{"day": 9, "attraction_ids": []}]}',  # day out of range
    ],
)
def test_malformed_or_invalid_llm_output_falls_back_with_a_visible_reason(client, tok, jaipur, use_llm, bad):
    llm = use_llm(FakeLLM(bad, bad))
    r = gen(client, tok, jaipur)
    it = r.json()
    assert r.status_code == 201 and it["generation_source"] == "deterministic_fallback"
    assert it["generation_info"]["llm"]["error"] and any(
        "deterministic planner" in n for n in it["generation_info"]["notes"]
    )
    assert len(llm.calls) == 2 and "rejected" in llm.calls[1][1]  # one retry that tells the model what was wrong
    assert [s["status"] for s in it["generation_info"]["steps"] if s["step"] == "llm_plan"] == ["failed"]
    assert sum(len(d["activities"]) for d in it["day_plans"]) >= 2


def test_llm_retry_can_succeed_after_a_bad_first_reply(client, tok, jaipur, use_llm):
    use_llm(FakeLLM("garbage", good_plan))
    assert gen(client, tok, jaipur).json()["generation_source"] == "llm"


def test_llm_transport_failure_falls_back(client, tok, jaipur, use_llm):
    use_llm(FakeLLM(LLMError("boom")))
    it = gen(client, tok, jaipur).json()
    assert it["generation_source"] == "deterministic_fallback" and "LLMError" in it["generation_info"]["llm"]["error"]


def test_llm_cannot_force_an_infeasible_schedule(client, tok, jaipur, use_llm):
    def overloaded(user):
        ids = [c["id"] for c in json.JSONDecoder().raw_decode(user)[0]["attractions"]]
        return json.dumps({"days": [{"day": 1, "attraction_ids": ids[:4]}, {"day": 2, "attraction_ids": []}]})

    use_llm(FakeLLM(overloaded))
    it = gen(client, tok, jaipur).json()
    assert it["generation_source"] == "llm" and it["violations"] == []
    assert sum(len(d["activities"]) for d in it["day_plans"]) == 4  # re-packed across days instead of overrunning day 1
    assert all(d["ends_at"] is None or d["ends_at"] <= "18:00" for d in it["day_plans"])


def test_free_text_prompt_is_interpreted_only_when_an_llm_exists(client, tok, jaipur, use_llm):
    intent = '{"destination_name":"Jaipur","days":2,"budget_total_inr":25000,"travelers":2,"interests":["history","food"],"travel_style":"comfort"}'
    use_llm(FakeLLM(intent, good_plan))
    r = client.post(
        f"{API}/itineraries/generate",
        json={"destination_id": str(jaipur.id), "prompt": "2 days in Jaipur for two, ₹25,000, history and food"},
        headers=auth(tok),
    )
    it = r.json()
    assert (
        r.status_code == 201 and it["days"] == 2 and it["traveler_count"] == 2 and it["budget_total_minor"] == 2_500_000
    )
    assert it["interests"] == ["history", "food"] and it["travel_style"] == "comfort"
    assert any("read from your message" in n for n in it["generation_info"]["notes"])
    # without an LLM the prompt is ignored (never silently "understood")
    use_llm(NoLLM())
    r2 = client.post(
        f"{API}/itineraries/generate",
        json={"destination_id": str(jaipur.id), "prompt": "something", "days": 1},
        headers=auth(tok),
    )
    assert r2.status_code == 201 and any("no AI provider" in n for n in r2.json()["generation_info"]["notes"])
    r3 = client.post(
        f"{API}/itineraries/generate",
        json={"destination_id": str(jaipur.id), "prompt": "no days given"},
        headers=auth(tok),
    )
    assert r3.status_code == 422


def test_bad_intent_output_does_not_break_generation(client, tok, jaipur, use_llm):
    use_llm(FakeLLM("???", "???", good_plan))  # intent fails twice, then the planning call succeeds
    r = client.post(
        f"{API}/itineraries/generate",
        json={"destination_id": str(jaipur.id), "prompt": "x", "days": 2},
        headers=auth(tok),
    )
    assert r.status_code == 201 and any("Could not interpret" in n for n in r.json()["generation_info"]["notes"])
    assert r.json()["generation_source"] == "llm"


# ------------------------------------------------------------------ management & persistence
def test_get_list_update_delete_and_ownership(client, tok, tok2, jaipur, db):
    it = gen(client, tok, jaipur).json()
    iid = it["id"]
    assert client.get(f"{API}/itineraries/{iid}", headers=auth(tok)).json()["title"] == it["title"]
    lst = client.get(f"{API}/itineraries", headers=auth(tok)).json()
    assert (
        lst["total"] == 1 and lst["items"][0]["destination_name"] == "Jaipur" and lst["items"][0]["activity_count"] >= 2
    )
    saved = client.patch(
        f"{API}/itineraries/{iid}", json={"title": "My Jaipur", "status": "saved"}, headers=auth(tok)
    ).json()
    assert saved["title"] == "My Jaipur" and saved["status"] == "saved" and saved["current_version"] == 2
    db.expire_all()
    assert db.get(Itinerary, iid).title == "My Jaipur"  # persisted, not just echoed
    for bad in (
        {"title": ""},
        {"title": None},
        {"status": "published"},
        {"traveler_count": 0},
        {"start_date": "2001-01-01"},
    ):
        assert client.patch(f"{API}/itineraries/{iid}", json=bad, headers=auth(tok)).status_code == 422
    # another user sees nothing and can change nothing; the response is the same as for a missing id
    h2 = auth(tok2)
    assert client.get(f"{API}/itineraries/{iid}", headers=h2).status_code == 404
    assert client.get(f"{API}/itineraries", headers=h2).json()["total"] == 0
    for method, url, body in [
        ("patch", "", {"title": "x"}),
        ("delete", "", None),
        ("post", "/regenerate", {}),
        ("get", "/versions", None),
        ("post", "/reorder", {"days": []}),
        ("post", "/activities", {"attraction_id": "00000000-0000-0000-0000-000000000000", "day_number": 1}),
    ]:
        r = getattr(client, method)(
            f"{API}/itineraries/{iid}{url}", headers=h2, **({"json": body} if body is not None else {})
        )
        assert r.status_code == 404, (method, url)
    assert client.get(f"{API}/itineraries/{iid}").status_code == 401
    assert client.delete(f"{API}/itineraries/{iid}", headers=auth(tok)).status_code == 204
    assert client.get(f"{API}/itineraries/{iid}", headers=auth(tok)).status_code == 404
    assert client.get(f"{API}/itineraries", headers=auth(tok)).json()["total"] == 0
    assert db.get(Itinerary, iid) is not None  # soft delete


def test_add_remove_edit_and_reorder_activities_persist_and_reschedule(client, tok, jaipur, db):
    h = auth(tok)
    it = gen(client, tok, jaipur, days=2).json()
    iid = it["id"]
    gone = client.delete(
        f"{API}/itineraries/{iid}/activities/{ids_of(it)[0]}", headers=h
    ).json()  # frees one attraction to re-add
    it = gone
    used = {a["attraction"]["id"] for d in it["day_plans"] for a in d["activities"]}
    spare = next(
        a for a in db.scalars(select(Attraction).where(Attraction.destination_id == jaipur.id)) if str(a.id) not in used
    )
    added = client.post(
        f"{API}/itineraries/{iid}/activities",
        json={"attraction_id": str(spare.id), "day_number": 2, "position": 1, "duration_min": 45},
        headers=h,
    )
    assert added.status_code == 201
    day2 = added.json()["day_plans"][1]["activities"]
    assert (
        day2[0]["attraction"]["id"] == str(spare.id) and day2[0]["source"] == "user" and day2[0]["duration_min"] == 45
    )
    assert [a["position"] for a in day2] == list(range(1, len(day2) + 1))
    assert all(day2[i]["start_min"] >= day2[i - 1]["end_min"] for i in range(1, len(day2)))  # times were recomputed
    assert (
        client.post(
            f"{API}/itineraries/{iid}/activities", json={"attraction_id": str(spare.id), "day_number": 1}, headers=h
        ).status_code
        == 409
    )
    other_dest = db.scalar(select(Attraction).where(Attraction.destination_id != jaipur.id))
    assert (
        client.post(
            f"{API}/itineraries/{iid}/activities",
            json={"attraction_id": str(other_dest.id), "day_number": 1},
            headers=h,
        ).status_code
        == 422
    )
    assert (
        client.post(
            f"{API}/itineraries/{iid}/activities", json={"attraction_id": str(spare.id), "day_number": 9}, headers=h
        ).status_code
        == 422
    )

    aid = day2[0]["id"]
    edited = client.patch(
        f"{API}/itineraries/{iid}/activities/{aid}", json={"duration_min": 120, "notes": "Sunset"}, headers=h
    ).json()
    a = edited["day_plans"][1]["activities"][0]
    assert a["duration_min"] == 120 and a["notes"] == "Sunset" and a["end_min"] - a["start_min"] == 120
    assert (
        client.patch(f"{API}/itineraries/{iid}/activities/{aid}", json={"duration_min": 2}, headers=h).status_code
        == 422
    )

    # reorder: move everything from day 2 into day 1 in reverse order
    all_ids = ids_of(edited)
    new_day1 = list(reversed(all_ids))
    moved = client.post(
        f"{API}/itineraries/{iid}/reorder",
        json={"days": [{"day_number": 1, "activity_ids": new_day1}, {"day_number": 2, "activity_ids": []}]},
        headers=h,
    )
    assert (
        moved.status_code == 200
        and ids_of(moved.json()) == new_day1
        and moved.json()["day_plans"][1]["activities"] == []
    )
    assert (
        client.post(
            f"{API}/itineraries/{iid}/reorder",
            json={"days": [{"day_number": 1, "activity_ids": new_day1[:-1]}]},
            headers=h,
        ).status_code
        == 422
    )  # must list all
    assert (
        client.post(
            f"{API}/itineraries/{iid}/reorder",
            json={"days": [{"day_number": 1, "activity_ids": new_day1 + new_day1[:1]}]},
            headers=h,
        ).status_code
        == 422
    )

    removed = client.delete(f"{API}/itineraries/{iid}/activities/{new_day1[0]}", headers=h).json()
    assert new_day1[0] not in ids_of(removed) and len(ids_of(removed)) == len(new_day1) - 1
    assert client.delete(f"{API}/itineraries/{iid}/activities/{new_day1[0]}", headers=h).status_code == 404
    # everything above is in the database
    db.expire_all()
    rows = db.scalars(
        select(ItineraryActivity).where(ItineraryActivity.itinerary_id == iid).order_by(ItineraryActivity.position)
    ).all()
    assert [str(r.id) for r in rows] == ids_of(removed)


def test_version_history_and_restore(client, tok, jaipur):
    h = auth(tok)
    it = gen(client, tok, jaipur).json()
    iid, original = it["id"], ids_of(it)
    client.delete(f"{API}/itineraries/{iid}/activities/{original[0]}", headers=h)
    client.patch(f"{API}/itineraries/{iid}", json={"title": "Renamed"}, headers=h)
    vs = client.get(f"{API}/itineraries/{iid}/versions", headers=h).json()
    assert (
        [v["version"] for v in vs] == [3, 2, 1]
        and vs[0]["summary"].startswith("Updated")
        and vs[1]["summary"].startswith("Removed")
    )
    detail = client.get(f"{API}/itineraries/{iid}/versions/1", headers=h).json()
    assert len(detail["snapshot"]["activities"]) == len(original)
    assert client.get(f"{API}/itineraries/{iid}/versions/99", headers=h).status_code == 404
    restored = client.post(f"{API}/itineraries/{iid}/versions/1/restore", headers=h).json()
    assert (
        len(ids_of(restored)) == len(original) and restored["title"] == it["title"] and restored["current_version"] == 4
    )
    assert [v["summary"] for v in client.get(f"{API}/itineraries/{iid}/versions", headers=h).json()][
        0
    ] == "Restored version 1"  # history is never rewritten


def test_regenerate_replaces_activities_and_records_a_version(client, tok, jaipur, use_llm):
    h = auth(tok)
    it = gen(client, tok, jaipur, days=2).json()
    iid = it["id"]
    use_llm(FakeLLM(good_plan))
    r = client.post(
        f"{API}/itineraries/{iid}/regenerate", json={"interests": ["food"], "budget_total_minor": 3_000_000}, headers=h
    )
    assert r.status_code == 200
    out = r.json()
    assert out["generation_source"] == "llm" and out["interests"] == ["food"] and out["budget_total_minor"] == 3_000_000
    assert out["current_version"] == 2 and set(ids_of(out)).isdisjoint(ids_of(it))  # new activity rows
    assert client.get(f"{API}/itineraries/{iid}/versions", headers=h).json()[0]["summary"] == "Regenerated"


def test_unpublished_attraction_is_flagged_not_crashing_reads(client, tok, jaipur, db):
    it = gen(client, tok, jaipur).json()
    db.execute(
        Attraction.__table__.update()
        .where(Attraction.id == it["day_plans"][0]["activities"][0]["attraction"]["id"])
        .values(is_published=False)
    )
    db.commit()
    assert client.get(f"{API}/itineraries/{it['id']}", headers=auth(tok)).status_code == 200
