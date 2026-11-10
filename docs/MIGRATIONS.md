# Database Migrations

Alembic is the only schema path. Run from `backend/` with `DATABASE_URL` set (see `.env.example`).

```bash
uv run alembic upgrade head          # apply all
uv run alembic current               # show the current revision
uv run alembic downgrade -1          # roll back one step (development only)
uv run alembic revision --autogenerate -m "describe change" --rev-id 0004   # then REVIEW the file
```

| Revision | Adds |
|---|---|
| 0001 | users, user_preferences, refresh_tokens, audit_logs |
| 0002 | attraction_categories, destinations, destination_categories, attractions (CHECK constraints on coordinates, cost, duration, season) |
| 0003 | **Optional PostGIS**: if the server offers the extension, enables it and adds generated `location geography(Point,4326)` columns with GiST indexes on destinations and attractions. A no-op otherwise. |
| 0004 | `user_interactions`, `recommendation_runs`, `recommendation_items`, `recommendation_feedback` |
| 0005 | `itineraries`, `itinerary_activities`, `itinerary_versions` |
| 0006 | `optimization_runs`, `context_snapshots`, `adaptation_proposals`, `itinerary_activities.locked` |
| 0007 | `hotels`, `room_types`, `room_inventory` (CHECK booked<=total), `bookings` (unique user+idempotency key), `payments`, `notifications` (unique idempotency key), `notification_deliveries`, `assistant_conversations`, `assistant_messages` |

## PostGIS
- **Decision:** PostGIS is used where available; plain `latitude`/`longitude` columns stay the source of truth, and a portable haversine backend serves everything else (`SPATIAL_BACKEND=auto|postgis|haversine`, default `auto`). See `TECHNICAL_DECISIONS.md` #13.
- **Docker/CI** use `postgis/postgis:16-3.4`, so migration 0003 enables it automatically. That image is amd64-only (runs under emulation on Apple silicon).
- **Local Homebrew PostgreSQL** does not ship PostGIS (`brew install postgis` pulls ~85 formulae), so it runs on the haversine backend. To get PostGIS locally, use the Docker image: `docker run -d -p 5433:5432 -e POSTGRES_PASSWORD=... -e POSTGRES_DB=routeaura postgis/postgis:16-3.4`.
- **Enabling it on an existing database:** install the extension on the server, then `uv run python -m app.scripts.enable_postgis` (idempotent; needs a role allowed to `CREATE EXTENSION`). Restart the API so the backend choice is re-detected.
- **Tests:** `uv run pytest` runs the haversine backend; the PostGIS variants run automatically when the test database's server has the extension (`TEST_DATABASE_URL=postgresql+psycopg://postgres:...@localhost:5433/routeaura_test`).

## Seed data (development / demo)
`uv run python -m app.scripts.seed_catalog` loads 7 categories, 5 destinations and 20 attractions (idempotent; refuses to run in production). Coordinates are approximate and costs/durations are placeholder estimates, all marked `source=seed`; opening hours are left unknown.
