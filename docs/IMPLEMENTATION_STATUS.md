# Implementation Status

_Last updated: 2026-11-11_

| Milestone | Status |
|---|---|
| 0 Audit, architecture, plan | ✅ Done |
| 1 Backend foundation + auth | ✅ Done (tag `milestone-1-auth-foundation`) |
| 2 Destinations & attractions | ✅ Done, with the caveats below |
| 3 Recommendations | ⏳ Not started |
| 4 Itinerary generator | ⏳ Not started |
| 5 Route optimization | ⏳ Not started |
| 6 Context-aware adaptation | ⏳ Not started |
| 7 Voice assistant | ⏳ Not started |
| 8 Hotels, bookings, notifications | ⏳ Not started |
| 9 Analytics, E2E, deployment | ⏳ Not started |

## Milestone 1 (summary)
FastAPI + PostgreSQL + Alembic; register/login/refresh/logout with Argon2id, rotating refresh tokens and replay detection; server-side RBAC; profile, preferences and admin user management; frontend on the real API. Details: git history and `API.md`.
Lockfile decision resolved: npm only (`bun.lockb` removed; no workflow used it).

## Milestone 2: what exists and was verified

**Backend**
- Migrations `0002` (categories, destinations, destination_categories, attractions with CHECK constraints on coordinates, cost, duration and season) and `0003` (optional PostGIS, see `MIGRATIONS.md`).
- Models, Pydantic schemas, repositories, `CatalogService`, public and admin routers (full contract in `API.md`).
- Destination, attraction and category CRUD; publish/draft status; soft delete with cascade; unique slugs; audit log on every admin write.
- Latitude/longitude validated in Pydantic (including NaN/inf rejection) and by DB CHECK constraints.
- Search (`q`, country, category, climate, best month incl. wrap-around, max cost), sorting, pagination with caps.
- Spatial: `SpatialBackend` protocol with a PostGIS implementation (`ST_DWithin` on a GiST-indexed generated `geography` column) and a portable haversine implementation with bounding-box prefilter (antimeridian and pole aware); pure-Python reference in `modules/spatial/geo.py`. Endpoints: `/attractions/nearby`, `/destinations/nearby`, and `lat/lng/radius_km` filters on the list endpoints.
- Idempotent demo seed (`app.scripts.seed_catalog`, refuses to run in production).

**Frontend** (existing visual language kept; all mock destination data removed)
- Typed API layer + TanStack Query hooks; shared loading/empty/error/pagination components.
- Traveler: `/dashboard/destinations` (debounced search; category, climate, month and sort filters; pagination) and `/dashboard/destinations/:slug` (facts, estimate disclaimer, attractions with category and radius filters showing distances).
- Admin: `/admin/destinations` rewritten (search, pagination, create/edit dialog with validation, delete confirmation, Categories manager) and new `/admin/destinations/:id/attractions` (CRUD, opening-hours editor, validation).
- Route-level code splitting (main bundle 1,008 kB -> 496 kB).
- Query client no longer retries 4xx responses.

## Test results (2026-11-11, final code)

| Check | Result |
|---|---|
| Backend `uv run pytest -q`, plain PostgreSQL 18 | **93 passed, 8 skipped** (the 8 are the PostGIS variants) |
| Backend `pytest -q` against PostGIS 3.4 (`postgis/postgis:16-3.4`, Docker) | **101 passed, 0 skipped** (PostGIS and haversine backends both agree with the pure reference) |
| Backend `ruff check` | clean |
| Frontend `npm test` | **37 passed** (6 files) |
| `npm run lint` | 0 errors, 8 pre-existing react-refresh warnings (shadcn files) |
| `npx tsc -p tsconfig.app.json --noEmit` | clean |
| `npm run build` | passes |
| Live check through the Vite proxy against the real API/DB | public listing, month filter, nearby search, 401/403 on admin writes, 422 on bad coordinates, create then public visibility then soft delete: all as expected |

Backend coverage areas: CRUD and persistence, admin/traveler/anonymous permissions, invalid and boundary coordinates (API and DB level), season/image/opening-hours/field validation, category rules (duplicate, in use, unknown), search/filter/sort/pagination (including LIKE-wildcard literals and no duplicates or gaps across pages), soft delete cascade, unpublished visibility rules, audit logging, radius search vs brute force at several radii, radius boundary, antimeridian, geo property test (bounding box never excludes a point inside the radius).
Frontend coverage areas: formatting/parsing/validation helpers, traveler browse (loading, cards, empty, error + retry, debounced search, pagination), destination detail (facts, estimates labelling, 404, error, empty, radius filter), admin (list, empty, error, client-side coordinate validation without API call, create with value conversion, server rejection toast, edit/PATCH, delete confirmation, category-in-use error).

## Known gaps and honest caveats

1. **No browser-level verification.** The UI was verified through component tests with mocked network and the API through real HTTP calls, but nobody has clicked through the screens in a browser (no visual/layout check, no real Radix interactions beyond jsdom). Playwright E2E is planned for Milestone 9.
2. **Docker images still not built or run end to end** (`docker compose config` validates; the PostGIS image was exercised only as a standalone test container). CI has never run.
3. **PostGIS is not available on the local Homebrew PostgreSQL**; local dev uses the haversine backend. Index-assisted `ST_DWithin` performance at scale is not benchmarked (the dev data set is 20 attractions).
4. The backend choice (PostGIS vs haversine) is detected once per process; restart the API after enabling PostGIS.
5. Seed data is illustrative: coordinates approximate, costs/durations are placeholder estimates (`source=seed`), opening hours unknown. Nothing is provider-sourced yet.
6. Still on mock data (in-memory, lost on refresh): packages, routes, bookings, admin analytics charts. "My Bookings" and the client dashboard show nothing for real accounts until Milestone 8.
7. No map UI yet (Leaflet is planned with the itinerary/route work); coordinates are shown as numbers and used for radius search.
8. Rate limiting is per-process; no email verification or password reset.
9. No image upload (images are URLs only).

## Files modified in Milestone 2

Backend added: `app/models/catalog.py`, `app/schemas/catalog.py`, `app/repositories/catalog.py`, `app/modules/catalog/{router,service,slugs}.py`, `app/modules/spatial/{geo,backends}.py`, `app/scripts/{seed_catalog,enable_postgis}.py`, `migrations/versions/{0002,0003}*.py`, `app/tests/{test_catalog,test_spatial,test_geo}.py`.
Backend modified: `app/models/__init__.py`, `app/api/v1/router.py`, `app/core/config.py` (SPATIAL_BACKEND), `app/tests/conftest.py`, `pyproject.toml` (ruff).
Frontend added: `src/lib/{format,forms}.ts`, `src/lib/api/catalog.ts`, `src/hooks/{useCatalog,useDebounced}.ts`, `src/components/{QueryState.tsx,catalog/DestinationCard.tsx,admin/*}`, `src/pages/client/{BrowseDestinations,DestinationDetail}.tsx`, `src/pages/admin/ManageAttractions.tsx`, six test files under `src/test/`.
Frontend modified: `src/pages/admin/ManageDestinations.tsx` (rewritten), `src/App.tsx` (lazy routes, new routes, retry policy), `src/components/layouts/{DashboardLayout,MobileBottomNav}.tsx`, `src/data/mockData.ts` (destinations removed), `src/test/setup.ts`.
Infra/docs: `docker-compose.yml` and `.github/workflows/ci.yml` (PostGIS image), `README.md`, `docs/{API,MIGRATIONS,TECHNICAL_DECISIONS,IMPLEMENTATION_STATUS,TODO}.md`.

## Next milestone: 3, Personalized recommendation engine

1. Models + migration: `user_interactions` (view/save/click), `recommendation_logs`, optional `destination_features` view or computed features (interest vector from categories, budget tier, season, climate, duration).
2. Content-based scorer with normalised, configurable weights (interest similarity, budget, season, duration, climate, travel style); handle missing preferences; per-feature explanation.
3. APIs: `POST /recommendations`, `GET /recommendations`, `POST /recommendations/feedback`.
4. Evaluation script: Precision@K, Recall@K, NDCG@K on a labelled set clearly marked synthetic where it is; CSV/JSON output.
5. Frontend: "Recommended for you" on the traveler dashboard with explanations and feedback buttons; tests throughout.
