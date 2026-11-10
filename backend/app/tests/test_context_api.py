from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import select, update

from app.integrations.weather.base import DayForecast, WeatherError
from app.models.catalog import Attraction, Destination
from app.models.optimization import AdaptationProposal, ContextSnapshot

from .conftest import auth

API = "/api/v1"
START = date.today() + timedelta(days=20)


class FakeWeather:
    name = "fake-weather"

    def __init__(self, per_day=None, age_min=1, error=None):
        self.per_day, self.age_min, self.error, self.calls = per_day or {}, age_min, error, 0

    def forecast(self, lat, lng, start, end):
        self.calls += 1
        if self.error:
            raise self.error
        fetched = datetime.now(UTC) - timedelta(minutes=self.age_min)
        out = []
        d = start
        while d <= end:
            day = (d - start).days + 1
            prob, mm, tmax = self.per_day.get(day, (None, None, None))
            out.append(DayForecast(d, mm, prob, tmax, None, self.name, fetched))
            d += timedelta(days=1)
        return out


@pytest.fixture
def use_weather(monkeypatch):
    def install(provider):
        monkeypatch.setattr("app.modules.context.service.get_weather", lambda: provider)
        return provider

    return install


def register(client, email):
    return client.post(
        f"{API}/auth/register", json={"email": email, "password": "Passw0rdOK", "full_name": "T"}
    ).json()["access_token"]


@pytest.fixture
def tok(client, seeded):
    return register(client, "ctx@example.com")


@pytest.fixture
def tok2(client, seeded):
    return register(client, "ctx2@example.com")


@pytest.fixture
def jaipur(db):
    return db.scalar(select(Destination).where(Destination.slug == "jaipur"))


def by_name(it):
    return {a["attraction"]["name"]: a for d in it["day_plans"] for a in d["activities"]}


@pytest.fixture
def trip(client, tok, jaipur):
    """1-day trip with dates: Amber Fort (indoor in seed), Hawa Mahal (indoor), Jantar Mantar (OUTDOOR); City Palace is the spare."""
    h = auth(tok)
    it = client.post(
        f"{API}/itineraries/generate",
        json={"destination_id": str(jaipur.id), "days": 1, "interests": ["history"], "start_date": START.isoformat()},
        headers=h,
    ).json()
    present = by_name(it)
    if "City Palace" in present:
        client.delete(f"{API}/itineraries/{it['id']}/activities/{present['City Palace']['id']}", headers=h)
    it = client.get(f"{API}/itineraries/{it['id']}", headers=h).json()
    if "Jantar Mantar" not in by_name(it):
        j = client.get(f"{API}/attractions", params={"q": "Jantar"}).json()["items"][0]["id"]
        it = client.post(
            f"{API}/itineraries/{it['id']}/activities", json={"attraction_id": j, "day_number": 1}, headers=h
        ).json()
    assert "City Palace" not in by_name(it) and by_name(it)["Jantar Mantar"]["attraction"]["is_outdoor"]
    return it


def adapt(client, tok, it):
    r = client.post(f"{API}/itineraries/{it['id']}/adapt", headers=auth(tok))
    assert r.status_code == 200, r.text
    return r.json()


# ------------------------------------------------------------------ no provider: honest and still useful
def test_without_a_weather_provider_nothing_is_invented(client, tok, trip):
    h = auth(tok)
    st = client.get(f"{API}/itineraries/{trip['id']}/context", headers=h).json()
    assert st["weather_provider"] == "none" and st["weather_configured"] is False and st["snapshots"] == []
    assert any("No weather provider is configured" in n for n in st["notes"])
    r = client.post(f"{API}/itineraries/{trip['id']}/context/refresh", headers=h)
    assert r.status_code == 409 and r.json()["error"]["code"] == "provider_not_configured"
    res = adapt(client, tok, trip)
    assert (
        res["issues"] == [] and res["proposals"] == [] and any("weather was not considered" in n for n in res["notes"])
    )


def test_refresh_requires_dates_and_reports_provider_failures(client, tok, jaipur, use_weather):
    h = auth(tok)
    undated = client.post(
        f"{API}/itineraries/generate", json={"destination_id": str(jaipur.id), "days": 1}, headers=h
    ).json()
    use_weather(FakeWeather())
    r = client.post(f"{API}/itineraries/{undated['id']}/context/refresh", headers=h)
    assert r.status_code == 422 and r.json()["error"]["code"] == "dates_required"
    assert client.get(f"{API}/itineraries/{undated['id']}/context", headers=h).json()["needs_dates"] is True
    dated = client.patch(f"{API}/itineraries/{undated['id']}", json={"start_date": START.isoformat()}, headers=h).json()
    use_weather(FakeWeather(error=WeatherError("boom")))
    r = client.post(f"{API}/itineraries/{dated['id']}/context/refresh", headers=h)
    assert r.status_code == 502 and r.json()["error"]["code"] == "provider_error"


# ------------------------------------------------------------------ weather adaptation
def test_rain_creates_a_pending_proposal_with_provenance_and_never_changes_the_plan(client, tok, trip, use_weather, db):
    h = auth(tok)
    use_weather(FakeWeather({1: (85, 12.0, 24)}))
    st = client.post(f"{API}/itineraries/{trip['id']}/context/refresh", headers=h).json()
    assert (
        st["weather_configured"]
        and st["snapshots"][0]["source"] == "fake-weather"
        and st["snapshots"][0]["fresh"] is True
    )
    res = adapt(client, tok, trip)
    assert (
        [i["type"] for i in res["issues"]] == ["rain"]
        and "85% chance of rain" in res["issues"][0]["evidence"]
        and "fake-weather" in res["issues"][0]["evidence"]
    )
    prop = res["proposals"][0]
    assert prop["status"] == "pending" and prop["material"] is True and prop["base_version"] == trip["current_version"]
    ch = prop["changes"][0]
    assert (
        ch["action"] == "replace"
        and ch["from"] == "Jantar Mantar"
        and ch["to"] == "City Palace"
        and "indoor" in ch["reason"]
    )
    assert (
        prop["preview"]["after"]["days"][0]["stops"].count("City Palace") == 1
        and "Jantar Mantar" not in prop["preview"]["after"]["days"][0]["stops"]
    )
    assert prop["preview"]["alternatives"][0]["name"] == "City Palace"
    # nothing was applied
    now = client.get(f"{API}/itineraries/{trip['id']}", headers=h).json()
    assert "Jantar Mantar" in by_name(now) and now["current_version"] == trip["current_version"]
    assert db.scalar(select(AdaptationProposal.status)) == "pending"


def test_approving_applies_the_change_as_a_new_version(client, tok, trip, use_weather):
    h = auth(tok)
    use_weather(FakeWeather({1: (90, 20.0, 22)}))
    client.post(f"{API}/itineraries/{trip['id']}/context/refresh", headers=h)
    pid = adapt(client, tok, trip)["proposals"][0]["id"]
    r = client.post(f"{API}/adaptations/{pid}/approve", headers=h)
    assert r.status_code == 200
    it = r.json()
    names = by_name(it)
    assert "City Palace" in names and "Jantar Mantar" not in names and names["City Palace"]["source"] == "adapted"
    assert it["current_version"] == trip["current_version"] + 1 and it["violations"] == []
    assert (
        client.get(f"{API}/itineraries/{trip['id']}/versions", headers=h)
        .json()[0]["summary"]
        .startswith("Adapted (rain)")
    )
    prop = client.get(f"{API}/adaptations/{pid}", headers=h).json()
    assert prop["status"] == "approved" and prop["applied_version"] == it["current_version"] and prop["decided_at"]
    assert client.post(f"{API}/adaptations/{pid}/approve", headers=h).status_code == 409
    assert client.post(f"{API}/adaptations/{pid}/reject", headers=h).status_code == 409


def test_rejecting_leaves_the_itinerary_untouched(client, tok, trip, use_weather):
    h = auth(tok)
    use_weather(FakeWeather({1: (90, 20.0, 22)}))
    client.post(f"{API}/itineraries/{trip['id']}/context/refresh", headers=h)
    pid = adapt(client, tok, trip)["proposals"][0]["id"]
    assert client.post(f"{API}/adaptations/{pid}/reject", headers=h).json()["status"] == "rejected"
    it = client.get(f"{API}/itineraries/{trip['id']}", headers=h).json()
    assert "Jantar Mantar" in by_name(it) and it["current_version"] == trip["current_version"]
    assert [p["status"] for p in client.get(f"{API}/itineraries/{trip['id']}/adaptations", headers=h).json()] == [
        "rejected"
    ]


def test_repeated_adapt_does_not_create_duplicate_proposals(client, tok, trip, use_weather, db):
    h = auth(tok)
    use_weather(FakeWeather({1: (90, 20.0, 22)}))
    client.post(f"{API}/itineraries/{trip['id']}/context/refresh", headers=h)
    a, b = adapt(client, tok, trip), adapt(client, tok, trip)
    assert a["proposals"][0]["id"] == b["proposals"][0]["id"]
    assert len(db.scalars(select(AdaptationProposal)).all()) == 1


def test_proposals_go_stale_when_the_itinerary_changes_first(client, tok, trip, use_weather):
    h = auth(tok)
    use_weather(FakeWeather({1: (90, 20.0, 22)}))
    client.post(f"{API}/itineraries/{trip['id']}/context/refresh", headers=h)
    pid = adapt(client, tok, trip)["proposals"][0]["id"]
    client.patch(f"{API}/itineraries/{trip['id']}", json={"title": "Changed meanwhile"}, headers=h)
    r = client.post(f"{API}/adaptations/{pid}/approve", headers=h)
    assert r.status_code == 409 and r.json()["error"]["code"] == "stale_proposal"
    assert client.get(f"{API}/adaptations/{pid}", headers=h).json()["status"] == "superseded"


def test_stale_weather_is_ignored_and_the_reason_is_shown(client, tok, trip, use_weather):
    h = auth(tok)
    use_weather(FakeWeather({1: (95, 30.0, 22)}, age_min=600))
    st = client.post(f"{API}/itineraries/{trip['id']}/context/refresh", headers=h).json()
    assert st["snapshots"][0]["fresh"] is False and st["stale_days"] == [1] and st["snapshots"][0]["age_minutes"] >= 599
    res = adapt(client, tok, trip)
    assert res["issues"] == [] and res["stale_days"] == [1] and any("NOT used" in n for n in res["notes"])


def test_unknown_forecast_values_are_not_treated_as_bad_weather(client, tok, trip, use_weather):
    use_weather(FakeWeather({}))  # provider returns nulls
    client.post(f"{API}/itineraries/{trip['id']}/context/refresh", headers=auth(tok))
    res = adapt(client, tok, trip)
    assert res["issues"] == [] and any("no forecast values" in n for n in res["notes"])


def test_nice_weather_creates_no_proposals(client, tok, trip, use_weather):
    use_weather(FakeWeather({1: (10, 0.0, 26)}))
    client.post(f"{API}/itineraries/{trip['id']}/context/refresh", headers=auth(tok))
    res = adapt(client, tok, trip)
    assert res["issues"] == [] and res["proposals"] == []


def test_no_alternative_is_reported_as_unresolved_not_forced(client, tok, trip, use_weather, db):
    h = auth(tok)
    db.execute(
        update(Attraction).where(Attraction.name == "City Palace").values(is_published=False)
    )  # the only indoor spare disappears
    db.commit()
    use_weather(FakeWeather({1: (90, 20.0, 22)}))
    client.post(f"{API}/itineraries/{trip['id']}/context/refresh", headers=h)
    res = adapt(client, tok, trip)
    assert res["proposals"] == [] and res["unresolved"][0]["reason"] == "no suitable published alternative"


# ------------------------------------------------------------------ closures (verified and reported)
def test_verified_closed_day_triggers_a_closure_proposal_labelled_with_its_source(client, tok, trip, db):
    _ = auth(tok)
    weekday = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")[START.weekday()]
    db.execute(
        update(Attraction)
        .where(Attraction.name == "Hawa Mahal")
        .values(opening_hours={weekday: []}, opening_hours_source="admin")
    )
    db.commit()
    res = adapt(client, tok, trip)
    closure = next(i for i in res["issues"] if i["type"] == "closure")
    assert closure["source"] == "verified_hours" and "Hawa Mahal" in closure["evidence"]
    assert res["proposals"][0]["changes"][0]["from"] == "Hawa Mahal"


def test_user_reported_closure_is_labelled_consumed_once_and_validated(client, tok, tok2, trip):
    h = auth(tok)
    hawa = by_name(trip)["Hawa Mahal"]["id"]
    assert (
        client.post(f"{API}/itineraries/{trip['id']}/context/report", json={"type": "closure"}, headers=h).status_code
        == 422
    )
    other = "00000000-0000-0000-0000-000000000000"
    assert (
        client.post(
            f"{API}/itineraries/{trip['id']}/context/report", json={"type": "closure", "activity_id": other}, headers=h
        ).status_code
        == 404
    )
    r = client.post(
        f"{API}/itineraries/{trip['id']}/context/report", json={"type": "closure", "activity_id": hawa}, headers=h
    )
    assert r.status_code == 201 and r.json()["snapshots"][0]["source"] == "user_reported"
    res = adapt(client, tok, trip)
    assert res["issues"][0]["source"] == "user_reported" and res["proposals"][0]["changes"][0]["from"] == "Hawa Mahal"
    again = adapt(client, tok, trip)
    assert [i for i in again["issues"] if i["source"] == "user_reported"] == []  # a report is used once
    assert (
        client.post(
            f"{API}/itineraries/{trip['id']}/context/report",
            json={"type": "closure", "activity_id": hawa},
            headers=auth(tok2),
        ).status_code
        == 404
    )


def test_delay_report_moves_or_removes_what_no_longer_fits(client, tok, jaipur):
    h = auth(tok)
    it = client.post(
        f"{API}/itineraries/generate",
        json={"destination_id": str(jaipur.id), "days": 2, "interests": ["history"]},
        headers=h,
    ).json()
    assert len(it["day_plans"][0]["activities"]) >= 2  # there is a day to be late for
    r = client.post(
        f"{API}/itineraries/{it['id']}/context/report",
        json={"type": "delay", "day_number": 1, "current_time_min": 15 * 60, "completed_activity_ids": []},
        headers=h,
    )
    assert r.status_code == 201
    res = adapt(client, tok, it)
    assert res["issues"][0]["type"] == "delay" and "15:00" in res["issues"][0]["evidence"]
    assert res["proposals"] and all(c["action"] in ("move", "remove") for c in res["proposals"][0]["changes"])
    assert all(c["name"] for c in res["proposals"][0]["changes"])
    bad = client.post(
        f"{API}/itineraries/{it['id']}/context/report",
        json={"type": "delay", "day_number": 9, "current_time_min": 600},
        headers=h,
    )
    assert bad.status_code == 422
    assert (
        client.post(
            f"{API}/itineraries/{it['id']}/context/report", json={"type": "delay", "day_number": 1}, headers=h
        ).status_code
        == 422
    )


def test_overspending_report_proposes_a_cheaper_known_cost_alternative(client, tok, trip, db):
    h = auth(tok)
    db.execute(update(Attraction).where(Attraction.name == "Amber Fort").values(estimated_cost_minor=500000))
    db.execute(update(Attraction).where(Attraction.name == "City Palace").values(estimated_cost_minor=50000))
    db.commit()
    amber = by_name(trip)["Amber Fort"]["id"]
    client.patch(f"{API}/itineraries/{trip['id']}/activities/{amber}", json={"duration_min": 180}, headers=h)
    # price was copied when generated: re-add so the stored cost is the new one
    client.delete(f"{API}/itineraries/{trip['id']}/activities/{amber}", headers=h)
    amber_id = client.get(f"{API}/attractions", params={"q": "Amber"}).json()["items"][0]["id"]
    it = client.post(
        f"{API}/itineraries/{trip['id']}/activities", json={"attraction_id": amber_id, "day_number": 1}, headers=h
    ).json()
    client.patch(
        f"{API}/itineraries/{trip['id']}/activities/{by_name(it)['Amber Fort']['id']}",
        json={"locked": False},
        headers=h,
    )
    client.patch(f"{API}/itineraries/{trip['id']}", json={"budget_total_minor": 600000}, headers=h)
    client.post(
        f"{API}/itineraries/{trip['id']}/context/report", json={"type": "spent", "spent_minor": 300000}, headers=h
    )
    res = adapt(client, tok, trip)
    over = next(i for i in res["issues"] if i["type"] == "over_budget")
    assert over["source"] == "user_reported" and "planned activities still cost" in over["evidence"]
    ch = res["proposals"][0]["changes"][0]
    assert ch["from"] == "Amber Fort" and ch["to"] == "City Palace" and "known lower cost" in ch["reason"]


# ------------------------------------------------------------------ authorization
def test_ownership_and_authentication(client, tok, tok2, trip, use_weather):
    h, h2 = auth(tok), auth(tok2)
    use_weather(FakeWeather({1: (90, 20.0, 22)}))
    client.post(f"{API}/itineraries/{trip['id']}/context/refresh", headers=h)
    pid = adapt(client, tok, trip)["proposals"][0]["id"]
    for method, url in [("get", "/context"), ("post", "/context/refresh"), ("post", "/adapt"), ("get", "/adaptations")]:
        assert getattr(client, method)(f"{API}/itineraries/{trip['id']}{url}", headers=h2).status_code == 404, url
        assert getattr(client, method)(f"{API}/itineraries/{trip['id']}{url}").status_code == 401, url
    for method, url in [
        ("get", f"/adaptations/{pid}"),
        ("post", f"/adaptations/{pid}/approve"),
        ("post", f"/adaptations/{pid}/reject"),
    ]:
        assert getattr(client, method)(f"{API}{url}", headers=h2).status_code == 404, url
    assert client.get(f"{API}/adaptations/{pid}", headers=h).status_code == 200


def test_context_rows_are_persisted_with_source_and_expiry(client, tok, trip, use_weather, db):
    use_weather(FakeWeather({1: (10, 0.0, 26)}))
    client.post(f"{API}/itineraries/{trip['id']}/context/refresh", headers=auth(tok))
    snap = db.scalar(select(ContextSnapshot).where(ContextSnapshot.kind == "weather"))
    assert snap.source == "fake-weather" and snap.valid_until > snap.fetched_at and snap.payload["precip_prob"] == 10
