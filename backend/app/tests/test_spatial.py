"""Nearby / radius search. Every test runs against each available backend and is checked against
the pure-Python haversine reference, so PostGIS and the portable backend must agree."""
import pytest
from sqlalchemy import select

from app.core.config import get_settings
from app.database.session import get_engine
from app.models.catalog import Attraction
from app.modules.spatial.backends import postgis_available, reset_backend_cache
from app.modules.spatial.geo import haversine_m

API = "/api/v1"
HAWA_MAHAL = (26.9239, 75.8267)
HAS_POSTGIS = postgis_available(get_engine())  # migrations enable it in the test DB when present


@pytest.fixture(params=["haversine", pytest.param("postgis", marks=pytest.mark.skipif(
    not HAS_POSTGIS, reason="PostGIS is not installed in the test database"))])
def backend(request, monkeypatch):
    monkeypatch.setenv("SPATIAL_BACKEND", request.param)
    get_settings.cache_clear()
    reset_backend_cache()
    yield request.param
    monkeypatch.undo()
    get_settings.cache_clear()
    reset_backend_cache()


def nearby(client, lat, lng, radius_km, **extra):
    return client.get(f"{API}/attractions/nearby", params={"lat": lat, "lng": lng, "radius_km": radius_km, **extra})


def test_radius_search_matches_reference(client, seeded, backend):
    r = nearby(client, *HAWA_MAHAL, 2)
    assert r.status_code == 200
    names = [a["name"] for a in r.json()["items"]]
    # nearest first; Amber Fort (~8 km away) is outside the 2 km radius
    expected = sorted(("Hawa Mahal", "City Palace", "Jantar Mantar"), key=lambda n: haversine_m(
        *HAWA_MAHAL, *{"Hawa Mahal": HAWA_MAHAL, "City Palace": (26.9258, 75.8237), "Jantar Mantar": (26.9247, 75.8246)}[n]))
    assert names == expected == ["Hawa Mahal", "Jantar Mantar", "City Palace"]
    # distances agree with the pure reference to within a metre
    for a in r.json()["items"]:
        assert a["distance_m"] == pytest.approx(haversine_m(*HAWA_MAHAL, a["latitude"], a["longitude"]), abs=1.0)
    assert r.json()["items"][0]["distance_m"] < 1


def test_exactly_matches_brute_force_for_many_radii(client, seeded, db, backend):
    rows = db.scalars(select(Attraction)).all()
    for radius_km in (1, 10, 100, 500):
        expected = {a.name for a in rows if haversine_m(*HAWA_MAHAL, float(a.latitude), float(a.longitude)) <= radius_km * 1000}
        got = {a["name"] for a in nearby(client, *HAWA_MAHAL, radius_km, page_size=100).json()["items"]}
        assert got == expected, radius_km


def test_radius_boundary_is_inclusive_and_exclusive_correctly(client, seeded, db, backend):
    amber = db.scalar(select(Attraction).where(Attraction.name == "Amber Fort"))
    d = haversine_m(*HAWA_MAHAL, float(amber.latitude), float(amber.longitude))
    assert "Amber Fort" not in {a["name"] for a in nearby(client, *HAWA_MAHAL, (d - 50) / 1000).json()["items"]}
    assert "Amber Fort" in {a["name"] for a in nearby(client, *HAWA_MAHAL, (d + 50) / 1000).json()["items"]}


def test_nearby_filters_and_pagination(client, seeded, backend):
    assert nearby(client, *HAWA_MAHAL, 500, category="beach", page_size=100).json()["total"] == 0  # Goa is ~1,100 km away
    big = nearby(client, 15.4, 73.9, 100, category="beach").json()  # around Goa
    assert {a["name"] for a in big["items"]} == {"Baga Beach"}
    p1 = nearby(client, *HAWA_MAHAL, 500, page_size=2).json()
    assert len(p1["items"]) == 2 and p1["total"] >= 4
    assert [a["distance_m"] for a in p1["items"]] == sorted(a["distance_m"] for a in p1["items"])


def test_list_endpoint_supports_near_and_distance_sort(client, seeded, backend):
    r = client.get(f"{API}/attractions", params={"lat": 26.92, "lng": 75.82, "radius_km": 12, "sort": "distance"})
    items = r.json()["items"]
    assert r.status_code == 200 and len(items) == 4  # the four Jaipur attractions
    assert [a["distance_m"] for a in items] == sorted(a["distance_m"] for a in items)
    # radius search composes with other filters
    r = client.get(f"{API}/attractions", params={"lat": 26.92, "lng": 75.82, "radius_km": 12, "outdoor": "true"})
    assert [a["name"] for a in r.json()["items"]] == ["Jantar Mantar"]


def test_nearby_destinations(client, seeded, backend):
    r = client.get(f"{API}/destinations/nearby", params={"lat": 26.9, "lng": 75.8, "radius_km": 50})
    assert [d["name"] for d in r.json()["items"]] == ["Jaipur"]
    r = client.get(f"{API}/destinations/nearby", params={"lat": 26.9, "lng": 75.8, "radius_km": 500})
    assert [d["name"] for d in r.json()["items"]] == ["Jaipur"]  # Manali is ~600 km away
    r = client.get(f"{API}/destinations", params={"lat": 30.0, "lng": 76.5, "radius_km": 500, "sort": "distance"})
    names = [d["name"] for d in r.json()["items"]]
    assert names[:2] == ["Manali", "Jaipur"] and "Kerala" not in names and "Goa" not in names


def test_unpublished_attractions_never_appear_in_nearby(client, seeded, db, backend):
    db.execute(Attraction.__table__.update().where(Attraction.name == "Hawa Mahal").values(is_published=False))
    db.commit()
    assert "Hawa Mahal" not in {a["name"] for a in nearby(client, *HAWA_MAHAL, 2).json()["items"]}


@pytest.mark.parametrize("params", [
    {"lat": 91, "lng": 0, "radius_km": 5}, {"lat": 0, "lng": 181, "radius_km": 5},
    {"lat": 10, "lng": 10, "radius_km": 0}, {"lat": 10, "lng": 10, "radius_km": -3},
    {"lat": 10, "lng": 10, "radius_km": 501}, {"lat": 10, "lng": 10, "radius_km": "far"},
    {"lng": 10, "radius_km": 5},
])
def test_invalid_nearby_params_rejected(client, seeded, params):
    assert client.get(f"{API}/attractions/nearby", params=params).status_code == 422


def test_partial_near_params_and_distance_sort_without_centre(client, seeded):
    assert client.get(f"{API}/attractions", params={"lat": 10, "lng": 10}).status_code == 422
    assert client.get(f"{API}/attractions", params={"sort": "distance"}).status_code == 422
    assert client.get(f"{API}/destinations", params={"sort": "distance"}).status_code == 422


def test_antimeridian_search(client, admin_token, backend):
    """A radius search centred just west of the date line must find a point just east of it."""
    from .conftest import auth

    h = auth(admin_token)
    cat = client.post(f"{API}/admin/categories", json={"name": "Islands"}, headers=h).json()
    d = client.post(f"{API}/admin/destinations", json={"name": "Dateline Isle", "country": "Fiji", "latitude": -16.7,
                    "longitude": 179.95, "is_published": True}, headers=h).json()
    for name, lng in (("East Of Line", -179.95), ("West Of Line", 179.9), ("Far Away", 170.0)):
        client.post(f"{API}/admin/attractions", json={"destination_id": d["id"], "category_id": cat["id"], "name": name,
                    "latitude": -16.7, "longitude": lng, "is_published": True}, headers=h)
    r = nearby(client, -16.7, 179.99, 30)
    assert {a["name"] for a in r.json()["items"]} == {"East Of Line", "West Of Line"}


def test_auto_mode_picks_a_working_backend(client, seeded, monkeypatch):
    monkeypatch.setenv("SPATIAL_BACKEND", "auto")
    get_settings.cache_clear()
    reset_backend_cache()
    try:
        assert nearby(client, *HAWA_MAHAL, 2).json()["total"] == 3
    finally:
        monkeypatch.undo()
        get_settings.cache_clear()
        reset_backend_cache()
