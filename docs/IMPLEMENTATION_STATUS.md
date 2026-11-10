# Implementation Status

_Last updated: 2026-11-11_

| Milestone | Status |
|---|---|
| 0 Audit, architecture, plan | ✅ Done (`REPOSITORY_AUDIT.md`, `ARCHITECTURE.md`, `IMPLEMENTATION_PLAN.md`, `TECHNICAL_DECISIONS.md`) |
| 1 Backend foundation + auth | ✅ Done, with the exceptions listed below |
| 2 Destinations & attractions | ⏳ Not started |
| 3 Recommendations | ⏳ Not started |
| 4 Itinerary generator | ⏳ Not started |
| 5 Route optimization | ⏳ Not started |
| 6 Context-aware adaptation | ⏳ Not started |
| 7 Voice assistant | ⏳ Not started |
| 8 Hotels, bookings, notifications | ⏳ Not started |
| 9 Analytics, E2E, deployment | ⏳ Not started |

## Milestone 1: what exists and was verified

Verified by running commands (results at the bottom):

- FastAPI app (`backend/app`), modular layout, structured JSON logs, central error format, request-size limit, security headers, CORS allow-list, `/health` and `/health/ready`.
- PostgreSQL schema via Alembic migration `0001`: `users`, `user_preferences`, `refresh_tokens`, `audit_logs` (check constraints on role and preference ranges).
- Auth: register, login, refresh with **rotation and replay detection**, logout; Argon2id hashing; JWT (fixed algorithm, required claims); HttpOnly SameSite=Lax refresh cookie; in-process rate limit on auth routes.
- RBAC enforced server-side (`traveler`, `admin`); role read from DB on every request.
- Profile and travel-preference APIs; admin user list/search/pagination and role/active changes with audit log, self-lockout protection, session revocation on disable.
- Dev seed script that refuses to run outside `ENVIRONMENT=development`.
- Frontend: typed API client (`src/lib/api/`), single-flight token refresh, `AuthContext` on the real API, registration + login UI (react-hook-form + zod), working Profile and Travel Preferences, Manage Users on real data, Vite `/api` proxy.
- Frontend lint errors fixed (3 -> 0); placeholder test replaced with real tests.
- Dockerfiles, `docker-compose.yml`, nginx config, GitHub Actions CI.

## Known gaps and honest caveats

1. **Docker images were not built or run.** The Docker daemon was not running on the dev machine; `docker compose config` validates, but build and `up` are untested. Verify before relying on them.
2. **CI has never run.** The workflow is untested on GitHub. The dependency-audit step is advisory (`|| true`).
3. **No browser-level test.** The UI was exercised through component tests and the real API via `curl` through the Vite proxy; nobody has clicked through it in a browser yet. Playwright E2E is planned for Milestone 9.
4. **Client bookings pages show no data for real users.** `MyBookings` and `ClientDashboard` still read mock bookings keyed by the old mock user ids, so real accounts see empty lists until Milestone 8 persists bookings. Packages, destinations, routes, bookings and analytics pages are still on mock data (in-memory, lost on refresh) until their milestones.
5. Rate limiting is per-process (Redis-backed limiter planned).
6. No email verification or password reset yet (not in the spec; flagged in `TODO.md`).
7. Compose publishes the backend on 8000 for convenience; remove for production.
8. `bun.lockb` still committed alongside `package-lock.json` (needs owner decision).

## Test results (2026-11-11)

| Check | Result |
|---|---|
| `cd backend && uv run pytest -q` | 22 passed |
| `cd backend && uv run ruff check .` | clean |
| `npm test` | 10 passed (2 files) |
| `npm run lint` | 0 errors, 8 pre-existing react-refresh warnings in shadcn files |
| `npx tsc -p tsconfig.app.json --noEmit` | clean |
| `npm run build` | passes (1.0 MB bundle, not yet code-split) |
| Manual API flow through Vite proxy | register, refresh via cookie, `/users/me`, traveler 403 on admin route, admin list: all as expected |

## Files modified in Milestone 1

Modified: `.gitignore`, `package.json`, `package-lock.json`, `vite.config.ts`, `tailwind.config.ts`, `src/App.tsx`, `src/main.tsx`, `src/contexts/AuthContext.tsx`, `src/pages/Index.tsx`, `src/pages/Login.tsx`, `src/pages/admin/ManageUsers.tsx`, `src/pages/client/ClientProfile.tsx`, `src/components/layouts/DashboardLayout.tsx`, `src/components/ui/{command,textarea}.tsx`, `src/data/mockData.ts` (comment only).
Deleted: `src/test/example.test.ts` (placeholder).
Added: `backend/**`, `src/lib/api/*`, `src/hooks/useUsers.ts`, `src/test/{api-client.test.ts,auth-flow.test.tsx}`, `docs/*`, `Dockerfile`, `docker-compose.yml`, `deploy/nginx.conf`, `.dockerignore`, `.env.example`, `.env.development`, `.github/workflows/ci.yml`.

## Next milestone: 2, Destinations & attractions

1. Models + migration: `destinations`, `attraction_categories`, `attractions` (lat/lng, cost, duration, opening hours JSON, `source` column), soft delete.
2. Repositories/services/routers: public list/search/filter/sort/paginate and detail; admin CRUD with audit log.
3. Seed the 5 mock destinations with real coordinates and structured attractions (labelled `source=seed`).
4. Frontend: `lib/api/destinations.ts`, hooks, migrate `ManageDestinations` and add a traveler destination browser; route-level code splitting.
5. Tests: repository/service/API (filters, pagination, RBAC), frontend component tests.
