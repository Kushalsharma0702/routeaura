import os

# Must be set before the app is imported. Tests always use the dedicated test database.
os.environ.update(
    ENVIRONMENT="test",
    DATABASE_URL=os.environ.get(
        "TEST_DATABASE_URL", "postgresql+psycopg://localhost:5432/routeaura_test"
    ),
    JWT_SECRET="test-secret-test-secret-test-secret-0123456789",
    RATE_LIMIT_ENABLED="false",
)

import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.core.ratelimit import reset_rate_limits  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.database.session import get_engine, get_sessionmaker  # noqa: E402
from app.main import app  # noqa: E402
from app.models.user import Role, User  # noqa: E402

assert get_settings().environment == "test"
assert get_settings().database_url.endswith("_test"), "refusing to run against a non-test DB"


@pytest.fixture(scope="session", autouse=True)
def migrated_db():
    cfg = Config("alembic.ini")
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
    yield


@pytest.fixture(autouse=True)
def clean_db(migrated_db):
    with get_engine().begin() as conn:
        conn.execute(text(
            "TRUNCATE users, user_preferences, refresh_tokens, audit_logs, destination_categories, "
            "attractions, destinations, attraction_categories, recommendation_runs, recommendation_items, "
            "recommendation_feedback, user_interactions, itinerary_versions, itinerary_activities, itineraries CASCADE"))
    reset_rate_limits()
    yield


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def db():
    with get_sessionmaker()() as session:
        yield session


GOOD = {"email": "asha@example.com", "password": "Sup3rSecret", "full_name": "Asha Rao"}


@pytest.fixture
def traveler(client):
    r = client.post("/api/v1/auth/register", json=GOOD)
    assert r.status_code == 201
    return r.json()


@pytest.fixture
def admin_token(client, db):
    db.add(User(email="boss@example.com", full_name="Boss", role=Role.ADMIN,
                password_hash=hash_password("Adm1nPassword")))
    db.commit()
    r = client.post("/api/v1/auth/login", json={"email": "boss@example.com",
                                                 "password": "Adm1nPassword"})
    assert r.status_code == 200
    return r.json()["access_token"]


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def seeded(db):
    """The demo catalogue (5 destinations / 20 attractions), published."""
    from app.scripts.seed_catalog import seed

    seed(db)
    return db


@pytest.fixture
def traveler_token(traveler):
    return traveler["access_token"]


def pytest_collection_modifyitems(config, items):
    pass
