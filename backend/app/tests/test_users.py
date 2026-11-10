from sqlalchemy import select

from app.models.user import AuditLog

from .conftest import GOOD, auth

API = "/api/v1"


def test_update_profile(client, traveler):
    h = auth(traveler["access_token"])
    r = client.patch(f"{API}/users/me", json={"full_name": " Asha R ", "phone": "+91 98765 43210"}, headers=h)
    assert r.status_code == 200 and r.json()["full_name"] == "Asha R"
    assert client.patch(f"{API}/users/me", json={"phone": "abc"}, headers=h).status_code == 422


def test_profile_cannot_change_role(client, traveler):
    h = auth(traveler["access_token"])
    client.patch(f"{API}/users/me", json={"role": "admin", "full_name": "A"}, headers=h)
    assert client.get(f"{API}/users/me", headers=h).json()["role"] == "traveler"


def test_preferences_roundtrip_and_validation(client, traveler):
    h = auth(traveler["access_token"])
    empty = client.get(f"{API}/users/me/preferences", headers=h)
    assert empty.status_code == 200 and empty.json()["interests"] == []
    payload = {"budget_per_day_minor": 500000, "trip_duration_days": 5,
               "interests": ["History", " food ", "history"], "preferred_climate": "arid",
               "group_size": 2, "language": "hi"}
    r = client.put(f"{API}/users/me/preferences", json=payload, headers=h)
    assert r.status_code == 200
    assert r.json()["interests"] == ["food", "history"]  # normalised + de-duplicated
    assert client.get(f"{API}/users/me/preferences", headers=h).json()["language"] == "hi"
    for bad in ({"group_size": 0}, {"trip_duration_days": 90}, {"preferred_climate": "lava"},
                {"budget_per_day_minor": -5}):
        assert client.put(f"{API}/users/me/preferences", json=bad, headers=h).status_code == 422


def test_traveler_cannot_use_admin_endpoints(client, traveler):
    h = auth(traveler["access_token"])
    assert client.get(f"{API}/users", headers=h).status_code == 403
    assert client.patch(f"{API}/users/{traveler['user']['id']}", json={"role": "admin"},
                        headers=h).status_code == 403


def test_admin_lists_and_searches_users(client, traveler, admin_token):
    h = auth(admin_token)
    r = client.get(f"{API}/users", headers=h)
    assert r.status_code == 200 and r.json()["total"] == 2
    r = client.get(f"{API}/users", params={"q": "asha"}, headers=h)
    assert [u["email"] for u in r.json()["items"]] == [GOOD["email"]]
    assert client.get(f"{API}/users", params={"page_size": 1000}, headers=h).status_code == 422


def test_admin_changes_role_and_is_audited(client, traveler, admin_token, db):
    h = auth(admin_token)
    uid = traveler["user"]["id"]
    r = client.patch(f"{API}/users/{uid}", json={"role": "admin"}, headers=h)
    assert r.status_code == 200 and r.json()["role"] == "admin"
    log = db.scalar(select(AuditLog).where(AuditLog.action == "user.update"))
    assert log and log.entity_id == uid and log.detail["after"] == {"role": "admin"}
    # role is read from DB, so the promoted user's existing token is now admin-capable
    assert client.get(f"{API}/users", headers=auth(traveler["access_token"])).status_code == 200


def test_admin_deactivation_blocks_login_and_kills_sessions(client, traveler, admin_token):
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as tc:  # separate cookie jar holding the traveler's session
        assert tc.post(f"{API}/auth/login", json={"email": GOOD["email"],
                                                   "password": GOOD["password"]}).status_code == 200
        uid = traveler["user"]["id"]
        r = client.patch(f"{API}/users/{uid}", json={"is_active": False}, headers=auth(admin_token))
        assert r.status_code == 200
        login = tc.post(f"{API}/auth/login", json={"email": GOOD["email"],
                                                    "password": GOOD["password"]})
        assert login.status_code == 403
        assert tc.post(f"{API}/auth/refresh").status_code == 401
    assert client.get(f"{API}/users/me", headers=auth(traveler["access_token"])).status_code == 401


def test_admin_cannot_modify_self_or_missing_user(client, admin_token):
    h = auth(admin_token)
    me = client.get(f"{API}/users/me", headers=h).json()["id"]
    assert client.patch(f"{API}/users/{me}", json={"is_active": False}, headers=h).status_code == 400
    missing = "00000000-0000-0000-0000-000000000000"
    assert client.patch(f"{API}/users/{missing}", json={"is_active": False}, headers=h).status_code == 404
