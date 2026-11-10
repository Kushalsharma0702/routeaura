import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from app.models.catalog import Attraction, Destination
from app.models.user import AuditLog

from .conftest import auth

API = "/api/v1"
DEST = {"name": "Udaipur", "country": "India", "region": "Rajasthan", "latitude": 24.5854,
        "longitude": 73.7125, "description": "City of Lakes", "is_published": True}


@pytest.fixture
def cat(client, admin_token):
    r = client.post(f"{API}/admin/categories", json={"name": "Lakes"}, headers=auth(admin_token))
    assert r.status_code == 201
    return r.json()


@pytest.fixture
def dest(client, admin_token, cat):
    r = client.post(f"{API}/admin/destinations", json={**DEST, "category_ids": [cat["id"]]},
                    headers=auth(admin_token))
    assert r.status_code == 201, r.text
    return r.json()


def attraction_payload(dest_id, cat_id, **kw):
    return {"destination_id": dest_id, "category_id": cat_id, "name": "City Palace Udaipur",
            "latitude": 24.5764, "longitude": 73.6835, "is_published": True, **kw}


# ------------------------------------------------------------------ permissions
def test_public_can_read_but_not_write(client, dest, cat):
    assert client.get(f"{API}/destinations").status_code == 200
    assert client.get(f"{API}/categories").status_code == 200
    for method, url, body in [
        ("post", "/admin/destinations", DEST), ("patch", f"/admin/destinations/{dest['id']}", {}),
        ("delete", f"/admin/destinations/{dest['id']}", None), ("post", "/admin/categories", {"name": "xx"}),
        ("post", "/admin/attractions", {}), ("get", "/admin/destinations", None),
    ]:
        r = getattr(client, method)(f"{API}{url}", **({"json": body} if body is not None else {}))
        assert r.status_code == 401, (method, url)


def test_traveler_cannot_use_admin_endpoints(client, dest, cat, traveler_token):
    h = auth(traveler_token)
    assert client.get(f"{API}/admin/destinations", headers=h).status_code == 403
    assert client.post(f"{API}/admin/destinations", json=DEST, headers=h).status_code == 403
    assert client.patch(f"{API}/admin/destinations/{dest['id']}", json={"name": "Hack"}, headers=h).status_code == 403
    assert client.delete(f"{API}/admin/destinations/{dest['id']}", headers=h).status_code == 403
    assert client.post(f"{API}/admin/categories", json={"name": "Nope"}, headers=h).status_code == 403
    assert client.post(f"{API}/admin/attractions", json={}, headers=h).status_code == 403
    assert client.get(f"{API}/destinations/{dest['slug']}").status_code == 200  # reading is fine


# ------------------------------------------------------------------ destination CRUD
def test_destination_crud_and_persistence(client, admin_token, cat, db):
    h = auth(admin_token)
    r = client.post(f"{API}/admin/destinations", json={**DEST, "category_ids": [cat["id"]],
                    "estimated_cost_per_day_minor": 450000, "recommended_duration_days": 3,
                    "best_season_start_month": 10, "best_season_end_month": 3, "climate": "arid",
                    "images": ["https://example.com/a.jpg"]}, headers=h)
    assert r.status_code == 201
    d = r.json()
    assert d["slug"] == "udaipur" and d["source"] == "admin" and d["categories"][0]["slug"] == "lakes"
    # persisted: visible to an independent DB session
    row = db.scalar(select(Destination).where(Destination.slug == "udaipur"))
    assert row and float(row.latitude) == pytest.approx(24.5854) and row.estimated_cost_per_day_minor == 450000
    # update (PATCH)
    r = client.patch(f"{API}/admin/destinations/{d['id']}", json={"description": "Updated", "is_published": False}, headers=h)
    assert r.status_code == 200 and r.json()["description"] == "Updated" and r.json()["name"] == "Udaipur"
    db.expire_all()
    assert db.get(Destination, row.id).is_published is False
    # read via public id/slug
    client.patch(f"{API}/admin/destinations/{d['id']}", json={"is_published": True}, headers=h)
    assert client.get(f"{API}/destinations/{d['id']}").json()["slug"] == "udaipur"
    assert client.get(f"{API}/destinations/udaipur").status_code == 200


def test_duplicate_names_get_unique_slugs(client, admin_token):
    h = auth(admin_token)
    a = client.post(f"{API}/admin/destinations", json=DEST, headers=h).json()
    b = client.post(f"{API}/admin/destinations", json=DEST, headers=h).json()
    assert (a["slug"], b["slug"]) == ("udaipur", "udaipur-2")


def test_unpublished_destinations_hidden_from_public(client, admin_token):
    h = auth(admin_token)
    d = client.post(f"{API}/admin/destinations", json={**DEST, "is_published": False}, headers=h).json()
    assert client.get(f"{API}/destinations").json()["total"] == 0
    assert client.get(f"{API}/destinations/{d['slug']}").status_code == 404
    assert client.get(f"{API}/admin/destinations", headers=h).json()["total"] == 1
    assert client.get(f"{API}/admin/destinations/{d['id']}", headers=h).status_code == 200


def test_soft_delete_hides_and_cascades(client, admin_token, dest, cat, db):
    h = auth(admin_token)
    a = client.post(f"{API}/admin/attractions", json=attraction_payload(dest["id"], cat["id"]), headers=h).json()
    assert client.delete(f"{API}/admin/destinations/{dest['id']}", headers=h).status_code == 204
    assert client.get(f"{API}/destinations/{dest['slug']}").status_code == 404
    assert client.get(f"{API}/attractions/{a['id']}").status_code == 404
    assert client.get(f"{API}/admin/destinations", headers=h).json()["total"] == 0
    assert client.get(f"{API}/admin/destinations", params={"include_deleted": True}, headers=h).json()["total"] == 1
    assert client.delete(f"{API}/admin/destinations/{dest['id']}", headers=h).status_code == 404  # already gone
    # row is retained (soft delete), not removed
    assert db.scalar(select(Attraction.deleted_at).where(Attraction.name == "City Palace Udaipur")) is not None


def test_admin_writes_are_audited(client, admin_token, dest, db):
    actions = {a.action for a in db.scalars(select(AuditLog))}
    assert {"category.create", "destination.create"} <= actions


# ------------------------------------------------------------------ validation
@pytest.mark.parametrize("patch", [
    {"latitude": 90.0001}, {"latitude": -91}, {"longitude": 180.5}, {"longitude": -181}, {"latitude": "abc"},
])
def test_invalid_coordinates_rejected_on_create(client, admin_token, patch):
    r = client.post(f"{API}/admin/destinations", json={**DEST, **patch}, headers=auth(admin_token))
    assert r.status_code == 422 and r.json()["error"]["code"] == "validation_error"


def test_boundary_coordinates_accepted(client, admin_token):
    for lat, lng in [(90, 180), (-90, -180), (0, 0)]:
        r = client.post(f"{API}/admin/destinations", json={**DEST, "latitude": lat, "longitude": lng},
                        headers=auth(admin_token))
        assert r.status_code == 201


def test_invalid_coordinates_rejected_on_update(client, admin_token, dest):
    r = client.patch(f"{API}/admin/destinations/{dest['id']}", json={"latitude": 200}, headers=auth(admin_token))
    assert r.status_code == 422


def test_database_rejects_bad_coordinates_even_bypassing_api(db):
    with pytest.raises(IntegrityError):
        db.execute(text("INSERT INTO destinations (id, slug, name, country, description, latitude, longitude, "
                        "images, is_published, source, currency) VALUES (gen_random_uuid(), 'x', 'Xx', 'In', '', "
                        "95, 10, '[]', true, 'admin', 'INR')"))
    db.rollback()


@pytest.mark.parametrize("bad", [
    {"best_season_start_month": 10},  # missing end
    {"best_season_start_month": 13, "best_season_end_month": 2},
    {"climate": "lava"}, {"images": ["javascript:alert(1)"]}, {"images": ["https://x.io/a.jpg"] * 13},
    {"estimated_cost_per_day_minor": -1}, {"recommended_duration_days": 0}, {"name": "x"},
])
def test_destination_field_validation(client, admin_token, bad):
    assert client.post(f"{API}/admin/destinations", json={**DEST, **bad}, headers=auth(admin_token)).status_code == 422


def test_update_cannot_null_required_fields_or_break_season_pair(client, admin_token, dest):
    h = auth(admin_token)
    assert client.patch(f"{API}/admin/destinations/{dest['id']}", json={"name": None}, headers=h).status_code == 422
    client.patch(f"{API}/admin/destinations/{dest['id']}", json={"best_season_start_month": 1, "best_season_end_month": 2}, headers=h)
    r = client.patch(f"{API}/admin/destinations/{dest['id']}", json={"best_season_end_month": None}, headers=h)
    assert r.status_code == 422


# ------------------------------------------------------------------ categories
def test_category_rules(client, admin_token, cat, dest):
    h = auth(admin_token)
    assert client.post(f"{API}/admin/categories", json={"name": "lakes"}, headers=h).status_code == 409  # case-insens
    other = client.post(f"{API}/admin/categories", json={"name": "Deserts", "description": "Dunes"}, headers=h).json()
    assert client.patch(f"{API}/admin/categories/{other['id']}", json={"name": "Lakes"}, headers=h).status_code == 409
    assert client.patch(f"{API}/admin/categories/{other['id']}", json={"description": None}, headers=h).json()["description"] is None
    assert client.delete(f"{API}/admin/categories/{cat['id']}", headers=h).status_code == 409  # in use by dest
    assert client.delete(f"{API}/admin/categories/{other['id']}", headers=h).status_code == 204
    assert client.delete(f"{API}/admin/categories/{other['id']}", headers=h).status_code == 404
    bad = client.post(f"{API}/admin/destinations", json={**DEST, "category_ids": ["00000000-0000-0000-0000-000000000000"]}, headers=h)
    assert bad.status_code == 422 and bad.json()["error"]["code"] == "unknown_category"


# ------------------------------------------------------------------ attractions
def test_attraction_crud_and_visibility(client, admin_token, dest, cat, db):
    h = auth(admin_token)
    hours = {"mon": [["09:30", "17:30"]], "sun": []}
    r = client.post(f"{API}/admin/attractions", json=attraction_payload(dest["id"], cat["id"], opening_hours=hours,
                    estimated_cost_minor=30000, typical_duration_minutes=120, is_outdoor=False), headers=h)
    assert r.status_code == 201
    a = r.json()
    assert a["slug"] == "city-palace-udaipur" and a["opening_hours_source"] == "admin" and a["category"]["slug"] == "lakes"
    assert db.scalar(select(Attraction.estimated_cost_minor).where(Attraction.name == a["name"])) == 30000
    assert client.get(f"{API}/attractions/{a['id']}").status_code == 200
    # same name twice in one destination gets a distinct slug
    b = client.post(f"{API}/admin/attractions", json=attraction_payload(dest["id"], cat["id"]), headers=h).json()
    assert b["slug"] == "city-palace-udaipur-2" and b["opening_hours"] is None and b["opening_hours_source"] is None
    # update & clear opening hours
    r = client.patch(f"{API}/admin/attractions/{a['id']}", json={"opening_hours": None, "is_outdoor": True}, headers=h)
    assert r.status_code == 200 and r.json()["opening_hours"] is None and r.json()["is_outdoor"] is True
    # unpublished attraction hidden; unpublishing the destination hides its attractions too
    client.patch(f"{API}/admin/attractions/{b['id']}", json={"is_published": False}, headers=h)
    assert client.get(f"{API}/attractions/{b['id']}").status_code == 404
    assert client.get(f"{API}/destinations/{dest['slug']}/attractions").json()["total"] == 1
    client.patch(f"{API}/admin/destinations/{dest['id']}", json={"is_published": False}, headers=h)
    assert client.get(f"{API}/attractions/{a['id']}").status_code == 404
    assert client.get(f"{API}/attractions").json()["total"] == 0
    # delete
    assert client.delete(f"{API}/admin/attractions/{a['id']}", headers=h).status_code == 204
    assert client.get(f"{API}/admin/attractions/{a['id']}", headers=h).status_code == 404


@pytest.mark.parametrize("bad", [
    {"latitude": 91}, {"longitude": -181}, {"typical_duration_minutes": 2}, {"typical_duration_minutes": 2000},
    {"opening_hours": {"funday": [["09:00", "10:00"]]}}, {"opening_hours": {"mon": [["18:00", "09:00"]]}},
    {"opening_hours": {"mon": [["9am", "5pm"]]}}, {"estimated_cost_minor": -5},
])
def test_attraction_validation(client, admin_token, dest, cat, bad):
    r = client.post(f"{API}/admin/attractions", json=attraction_payload(dest["id"], cat["id"], **bad), headers=auth(admin_token))
    assert r.status_code == 422


def test_attraction_requires_existing_destination_and_category(client, admin_token, dest, cat):
    h = auth(admin_token)
    zero = "00000000-0000-0000-0000-000000000000"
    assert client.post(f"{API}/admin/attractions", json=attraction_payload(zero, cat["id"]), headers=h).json()["error"]["code"] == "unknown_destination"
    assert client.post(f"{API}/admin/attractions", json=attraction_payload(dest["id"], zero), headers=h).json()["error"]["code"] == "unknown_category"


# ------------------------------------------------------------------ search, filter, sort, pagination
def test_destination_search_filters_sorting(client, seeded):
    def ids(**params):
        r = client.get(f"{API}/destinations", params=params)
        assert r.status_code == 200, r.text
        return [d["name"] for d in r.json()["items"]], r.json()["total"]

    assert ids()[1] == 5
    assert ids(q="pink")[0] == ["Jaipur"]
    assert ids(q="GOA")[0] == ["Goa"]  # case-insensitive
    assert ids(q="%")[1] == 0 and ids(q="_")[1] == 0  # LIKE wildcards are literal
    assert ids(category="beach")[0] == ["Goa", "Kerala"]
    assert ids(climate="cold")[0] == ["Ladakh", "Manali"]
    assert ids(country="india")[1] == 5 and ids(country="Nepal")[1] == 0
    # season filter incl. wrap-around Oct-Mar (Goa) and non-wrapping Jun-Sep (Ladakh)
    assert "Goa" in ids(month=12)[0] and "Goa" in ids(month=2)[0] and "Goa" not in ids(month=7)[0]
    assert ids(month=7)[0] == ["Ladakh"]  # July: only the Jun-Sep destination is in season
    assert "Ladakh" in ids(month=7)[0] and "Ladakh" not in ids(month=12)[0]
    # cost cap and sorts (cost stored in paise)
    cheap, _ = ids(max_cost_minor=330000)
    assert set(cheap) == {"Manali", "Jaipur"}
    assert ids(sort="cost")[0][0] == "Manali" and ids(sort="-cost")[0][0] == "Ladakh"
    assert ids(sort="-name")[0][0] == "Manali" and ids(sort="name")[0][0] == "Goa"
    assert client.get(f"{API}/destinations", params={"sort": "bogus"}).status_code == 422


def test_pagination(client, seeded):
    r = client.get(f"{API}/destinations", params={"page_size": 2, "page": 1}).json()
    assert (len(r["items"]), r["total"], r["page"], r["page_size"]) == (2, 5, 1, 2)
    p3 = client.get(f"{API}/destinations", params={"page_size": 2, "page": 3}).json()
    assert len(p3["items"]) == 1
    seen = [d["name"] for p in (1, 2, 3) for d in client.get(f"{API}/destinations", params={"page_size": 2, "page": p}).json()["items"]]
    assert len(seen) == len(set(seen)) == 5  # no duplicates or gaps across pages
    assert client.get(f"{API}/destinations", params={"page": 99}).json()["items"] == []
    for bad in ({"page": 0}, {"page_size": 0}, {"page_size": 101}):
        assert client.get(f"{API}/destinations", params=bad).status_code == 422


def test_attraction_search_and_counts(client, seeded):
    jaipur = client.get(f"{API}/destinations/jaipur").json()
    assert jaipur["attraction_count"] == 4
    r = client.get(f"{API}/destinations/jaipur/attractions").json()
    assert r["total"] == 4 and all(a["category"]["slug"] == "history-heritage" for a in r["items"])
    assert client.get(f"{API}/attractions", params={"q": "fort"}).json()["total"] == 2  # Fort Aguada, Amber Fort
    assert client.get(f"{API}/attractions", params={"outdoor": "true", "category": "beach"}).json()["total"] == 2
    assert client.get(f"{API}/attractions", params={"destination_id": jaipur["id"], "page_size": 3}).json()["total"] == 4
    assert client.get(f"{API}/destinations/nowhere/attractions").status_code == 404


def test_catalog_survives_new_sessions(client, seeded):
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as other:
        assert other.get(f"{API}/destinations").json()["total"] == 5


def test_seed_is_idempotent(seeded):
    from app.scripts.seed_catalog import seed

    assert seed(seeded) == {"categories": 0, "destinations": 0, "attractions": 0, "hotels": 0, "room_types": 0}
