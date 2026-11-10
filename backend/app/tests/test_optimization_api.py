import pytest
from sqlalchemy import select

from app.integrations.routing.base import TravelMatrix
from app.integrations.routing.providers import EstimateRouting
from app.models.catalog import Destination
from app.models.optimization import OptimizationRun

from .conftest import auth

API = "/api/v1"


def register(client, email):
    return client.post(
        f"{API}/auth/register", json={"email": email, "password": "Passw0rdOK", "full_name": "T"}
    ).json()["access_token"]


@pytest.fixture
def tok(client, seeded):
    return register(client, "opt@example.com")


@pytest.fixture
def tok2(client, seeded):
    return register(client, "opt2@example.com")


@pytest.fixture
def trip(client, tok, db):
    """A 1-day Jaipur trip in a deliberately bad (zig-zag) order: Hawa -> Amber -> Jantar -> City Palace."""
    jaipur = db.scalar(select(Destination).where(Destination.slug == "jaipur"))
    it = client.post(
        f"{API}/itineraries/generate",
        json={"destination_id": str(jaipur.id), "days": 2, "interests": ["history"]},
        headers=auth(tok),
    ).json()
    by_name = {a["attraction"]["name"]: a["id"] for d in it["day_plans"] for a in d["activities"]}
    order = [by_name[n] for n in ("Hawa Mahal", "Amber Fort", "Jantar Mantar", "City Palace")]
    bad = client.post(
        f"{API}/itineraries/{it['id']}/reorder",
        json={"days": [{"day_number": 1, "activity_ids": order}, {"day_number": 2, "activity_ids": []}]},
        headers=auth(tok),
    )
    assert bad.status_code == 200
    return bad.json()


def names(it):
    return [[a["attraction"]["name"] for a in d["activities"]] for d in it["day_plans"]]


def optimize(client, tok, it, **body):
    return client.post(f"{API}/itineraries/{it['id']}/optimize", json=body, headers=auth(tok))


def test_preview_compares_original_and_optimized_without_changing_anything(client, tok, trip, db):
    before = names(trip)
    r = optimize(client, tok, trip)
    assert r.status_code == 201, r.text
    o = r.json()
    assert o["status"] == "optimized" and o["applied"] is False and o["base_version"] == trip["current_version"]
    assert o["routing"]["source"] == "estimate" and o["routing"]["live_traffic"] is False
    assert any("not road routing" in n for n in o["routing"]["notes"])
    b, a = o["before"]["metrics"], o["after"]["metrics"]
    assert a["distance_m"] < b["distance_m"] and a["travel_min"] < b["travel_min"] and a["violations"] == []
    assert o["delta"]["distance_m"] < 0 and o["delta"]["distance_pct"].startswith("-")
    assert sorted(x["name"] for d in o["after"]["days"] for x in d["stops"]) == sorted(
        n for d in before for n in d
    )  # same attractions
    assert any("Travel distance" in c for c in o["changes"]) and any(
        "order changed" in c or "Moved" in c for c in o["changes"]
    )
    assert o["weights"]["distance"] == 1.0 and o["solver_ms"] is not None
    # a preview changes nothing
    assert names(client.get(f"{API}/itineraries/{trip['id']}", headers=auth(tok)).json()) == before
    assert db.scalar(select(OptimizationRun).where(OptimizationRun.id == o["id"])).applied is False


def test_applying_an_optimization_persists_a_new_version_and_marks_the_run(client, tok, trip, db):
    o = optimize(client, tok, trip).json()
    r = client.post(f"{API}/optimizations/{o['id']}/apply", headers=auth(tok))
    assert r.status_code == 200
    out = r.json()
    after_names = [[x["name"] for x in d["stops"]] for d in o["after"]["days"]]
    assert names(out) == after_names and out["current_version"] == trip["current_version"] + 1
    new_total = sum(a["travel_m"] for d in out["day_plans"] for a in d["activities"])
    old_total = sum(a["travel_m"] for d in trip["day_plans"] for a in d["activities"])
    assert new_total < old_total and out["violations"] == []
    versions = client.get(f"{API}/itineraries/{trip['id']}/versions", headers=auth(tok)).json()
    assert versions[0]["summary"].startswith("Optimized route")
    db.expire_all()
    assert db.get(OptimizationRun, o["id"]).applied is True
    hist = client.get(f"{API}/itineraries/{trip['id']}/optimizations", headers=auth(tok)).json()
    assert len(hist) == 1 and hist[0]["applied"] is True
    # applying twice is refused
    assert client.post(f"{API}/optimizations/{o['id']}/apply", headers=auth(tok)).status_code == 409


def test_stale_previews_cannot_be_applied(client, tok, trip):
    o = optimize(client, tok, trip).json()
    client.patch(f"{API}/itineraries/{trip['id']}", json={"title": "Edited after the preview"}, headers=auth(tok))
    r = client.post(f"{API}/optimizations/{o['id']}/apply", headers=auth(tok))
    assert r.status_code == 409 and r.json()["error"]["code"] == "stale_optimization"


def test_ownership_everywhere(client, tok, tok2, trip):
    o = optimize(client, tok, trip).json()
    h2 = auth(tok2)
    assert client.post(f"{API}/itineraries/{trip['id']}/optimize", json={}, headers=h2).status_code == 404
    assert client.get(f"{API}/itineraries/{trip['id']}/optimizations", headers=h2).status_code == 404
    assert client.get(f"{API}/optimizations/{o['id']}", headers=h2).status_code == 404
    assert client.post(f"{API}/optimizations/{o['id']}/apply", headers=h2).status_code == 404
    assert client.post(f"{API}/itineraries/{trip['id']}/optimize", json={}).status_code == 401
    assert client.get(f"{API}/optimizations/{o['id']}", headers=auth(tok)).status_code == 200


@pytest.mark.parametrize(
    "body",
    [{"weights": {"distance": -1}}, {"weights": {"time": 1000}}, {"time_limit_ms": 10}, {"time_limit_ms": 10**6}],
)
def test_invalid_optimize_requests(client, tok, trip, body):
    assert optimize(client, tok, trip, **body).status_code == 422


def test_empty_itinerary_cannot_be_optimized(client, tok, trip):
    ids = [a["id"] for d in trip["day_plans"] for a in d["activities"]]
    for i in ids:
        client.delete(f"{API}/itineraries/{trip['id']}/activities/{i}", headers=auth(tok))
    r = optimize(client, tok, trip)
    assert r.status_code == 422 and r.json()["error"]["code"] == "empty_itinerary"


def test_user_added_and_locked_activities_are_always_preserved(client, tok, trip, db):
    ids = {a["attraction"]["name"]: a["id"] for d in trip["day_plans"] for a in d["activities"]}
    client.patch(
        f"{API}/itineraries/{trip['id']}/activities/{ids['Amber Fort']}", json={"locked": True}, headers=auth(tok)
    )
    o = optimize(
        client, tok, trip, weights={"preference": 0}
    ).json()  # preference weight 0 makes dropping free for optional activities
    kept = {s["name"] for d in o["after"]["days"] for s in d["stops"]}
    assert "Amber Fort" in kept
    assert all(d["reason"] for d in o["dropped"])
    assert (
        client.patch(
            f"{API}/itineraries/{trip['id']}/activities/{ids['Amber Fort']}", json={"locked": None}, headers=auth(tok)
        ).status_code
        == 422
    )


def test_infeasible_requests_are_reported_and_cannot_be_applied(client, tok, trip):
    ids = [a["id"] for d in trip["day_plans"] for a in d["activities"]]
    for i in ids[:2]:
        client.patch(
            f"{API}/itineraries/{trip['id']}/activities/{i}",
            json={"duration_min": 1000, "locked": True},
            headers=auth(tok),
        )
    # two locked 1000-minute visits cannot fit into two 540-minute days (and one day cannot hold even one)
    o = optimize(client, tok, trip).json()
    assert o["status"] == "infeasible" and o["after"] is None and o["delta"] is None
    assert any("No change was possible" in c for c in o["changes"]) and any("need 2000 min" in n for n in o["notes"])
    assert client.post(f"{API}/optimizations/{o['id']}/apply", headers=auth(tok)).status_code == 409


class LabelledRouting:
    """Stands in for a real provider: same numbers as the estimate, different label and slower legs."""

    name = "test-provider"

    def matrix(self, points):
        m = EstimateRouting().matrix(points)
        return TravelMatrix(
            m.distance_m,
            [[x * 2 for x in row] for row in m.duration_min],
            "test-provider",
            notes=["provider test double"],
        )


def test_provider_source_is_carried_into_previews_and_saved_itineraries(client, tok, trip, monkeypatch):
    monkeypatch.setattr("app.modules.routing.service.get_routing", lambda: LabelledRouting())
    monkeypatch.setattr("app.modules.itinerary.service.get_routing", lambda: LabelledRouting())
    o = optimize(client, tok, trip).json()
    assert o["routing"]["source"] == "test-provider" and "provider test double" in o["routing"]["notes"]
    out = client.post(f"{API}/optimizations/{o['id']}/apply", headers=auth(tok)).json()
    assert {a["travel_source"] for d in out["day_plans"] for a in d["activities"]} == {"test-provider"}
    assert out["generation_info"]["routing"]["source"] == "test-provider"


def test_default_routing_is_labelled_as_an_estimate(client, tok, trip):
    assert {a["travel_source"] for d in trip["day_plans"] for a in d["activities"]} == {"estimate"}
    assert trip["generation_info"]["routing"]["live_traffic"] is False


def test_optimizing_twice_is_idempotent_once_applied(client, tok, trip):
    o1 = optimize(client, tok, trip).json()
    out = client.post(f"{API}/optimizations/{o1['id']}/apply", headers=auth(tok)).json()
    o2 = optimize(client, tok, out).json()
    assert o2["status"] == "optimized" and o2["before"]["metrics"]["distance_m"] == o2["after"]["metrics"]["distance_m"]
    assert any("already the best found" in c for c in o2["changes"])
