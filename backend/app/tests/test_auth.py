import time
from datetime import UTC, datetime, timedelta

import jwt
from sqlalchemy import select

from app.core.config import get_settings
from app.core.ratelimit import reset_rate_limits
from app.models.user import RefreshToken, User

from .conftest import GOOD, auth

API = "/api/v1"


def test_register_creates_traveler_and_session(client, db):
    r = client.post(f"{API}/auth/register", json=GOOD)
    assert r.status_code == 201
    body = r.json()
    assert body["user"]["role"] == "traveler"
    assert body["user"]["email"] == "asha@example.com"
    assert "password" not in str(body)
    set_cookie = r.headers["set-cookie"].lower()
    assert "httponly" in set_cookie and "samesite=lax" in set_cookie
    assert db.scalar(select(User.password_hash)).startswith("$argon2id$")


def test_register_cannot_escalate_to_admin(client):
    r = client.post(f"{API}/auth/register", json={**GOOD, "role": "admin"})
    assert r.status_code == 201
    assert r.json()["user"]["role"] == "traveler"


def test_register_duplicate_email_is_case_insensitive(client, traveler):
    r = client.post(f"{API}/auth/register", json={**GOOD, "email": "ASHA@Example.com"})
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "email_taken"


def test_register_rejects_weak_password_and_bad_email(client):
    assert client.post(f"{API}/auth/register", json={**GOOD, "password": "short1"}).status_code == 422
    assert client.post(f"{API}/auth/register", json={**GOOD, "password": "onlyletters"}).status_code == 422
    r = client.post(f"{API}/auth/register", json={**GOOD, "email": "nope"})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "validation_error"


def test_login_success_and_uniform_failure(client, traveler):
    ok = client.post(f"{API}/auth/login", json={"email": GOOD["email"], "password": GOOD["password"]})
    assert ok.status_code == 200 and ok.json()["access_token"]
    wrong = client.post(f"{API}/auth/login", json={"email": GOOD["email"], "password": "Wrong1234"})
    unknown = client.post(f"{API}/auth/login", json={"email": "who@example.com", "password": "Wrong1234"})
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()  # no user enumeration


def test_protected_endpoint_requires_valid_token(client, traveler):
    assert client.get(f"{API}/users/me").status_code == 401
    assert client.get(f"{API}/users/me", headers=auth("garbage")).status_code == 401
    assert client.get(f"{API}/users/me", headers=auth(traveler["access_token"])).status_code == 200


def test_tokens_with_wrong_secret_or_expired_are_rejected(client, traveler):
    s = get_settings()
    uid = traveler["user"]["id"]
    now = datetime.now(UTC)
    forged = jwt.encode({"sub": uid, "type": "access", "iat": now, "exp": now + timedelta(minutes=5)},
                        "x" * 40, algorithm="HS256")
    expired = jwt.encode({"sub": uid, "type": "access", "iat": now - timedelta(hours=1),
                          "exp": now - timedelta(minutes=1)}, s.jwt_secret, algorithm="HS256")
    wrong_type = jwt.encode({"sub": uid, "type": "refresh", "iat": now, "exp": now + timedelta(minutes=5)},
                            s.jwt_secret, algorithm="HS256")
    for tok in (forged, expired, wrong_type):
        assert client.get(f"{API}/users/me", headers=auth(tok)).status_code == 401


def test_refresh_rotates_and_replay_revokes_family(client, traveler):
    old = client.cookies.get("ra_refresh")
    assert old
    r = client.post(f"{API}/auth/refresh")
    assert r.status_code == 200
    new = client.cookies.get("ra_refresh")
    assert new and new != old
    # Replaying the rotated-out token is treated as theft: session is destroyed.
    client.cookies.set("ra_refresh", old, path="/api/v1/auth")
    assert client.post(f"{API}/auth/refresh").status_code == 401
    client.cookies.set("ra_refresh", new, path="/api/v1/auth")
    assert client.post(f"{API}/auth/refresh").status_code == 401


def test_refresh_without_cookie_is_401(client):
    assert client.post(f"{API}/auth/refresh").status_code == 401


def test_logout_revokes_session(client, traveler, db):
    assert client.post(f"{API}/auth/logout").status_code == 204
    assert client.post(f"{API}/auth/refresh").status_code == 401
    assert all(t.revoked_at for t in db.scalars(select(RefreshToken)))


def test_refresh_tokens_stored_hashed(client, traveler, db):
    raw = client.cookies.get("ra_refresh")
    stored = db.scalar(select(RefreshToken.token_hash))
    assert stored != raw and len(stored) == 64


def test_login_rate_limited(client, traveler, monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "true")
    get_settings.cache_clear()
    reset_rate_limits()
    try:
        codes = [client.post(f"{API}/auth/login",
                             json={"email": GOOD["email"], "password": "Wrong1234"}).status_code
                 for _ in range(12)]
        assert codes[:10] == [401] * 10 and 429 in codes[10:]
    finally:
        monkeypatch.setenv("RATE_LIMIT_ENABLED", "false")
        get_settings.cache_clear()
        reset_rate_limits()


def test_oversized_body_rejected(client):
    r = client.post(f"{API}/auth/login", content=b"x" * 2_000_000,
                    headers={"content-type": "application/json"})
    assert r.status_code == 413


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/health/ready").status_code == 200
    _ = time  # keep import used if timing assertions are added
