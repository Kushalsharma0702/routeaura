# Technical Decisions

| # | Decision | Rationale | Trade-off |
|---|---|---|---|
| 1 | Modular monolith (single FastAPI app, module-per-domain) | Small team, one deployable, modules stay independently testable | Not horizontally split by domain until needed |
| 2 | **Synchronous SQLAlchemy 2.x + psycopg 3**, sync route handlers | FastAPI runs sync handlers in a threadpool; far simpler transactions, `SELECT ... FOR UPDATE` for booking inventory, and test fixtures. Workloads are DB-bound, not high-concurrency. | Async I/O for LLM/maps calls will use `httpx` inside dedicated integration clients, not the DB layer |
| 3 | Python 3.12 via `uv` | System Python is 3.15 (pre-release for many wheels: OR-Tools, NumPy ecosystem) | Contributors need `uv` (documented) |
| 4 | Passwords: **Argon2id** (`argon2-cffi`) | Current OWASP recommendation | Slightly slower login; tuned for tests via a low-cost parameter set |
| 5 | Auth: short-lived JWT access token (15 min) in memory on the client + **rotating refresh token** (opaque random, SHA-256 hashed in DB, family-based reuse detection) | Refresh token in an `HttpOnly; SameSite=Lax` cookie keeps it out of JS; access token is never persisted in `localStorage` | Needs cookie-aware CORS (`allow_credentials`) and a Vite dev proxy so the browser sees one origin |
| 6 | Roles stored in DB as an enum (`traveler`, `admin`); authorization enforced server-side in dependencies | Never trust client-side checks | Frontend maps `traveler` to its existing `client` UI role at the API boundary |
| 7 | Alembic migrations are the only schema path; tests run migrations, not `create_all` | Migration drift is caught in CI | Slightly slower test setup |
| 8 | Rate limiting: in-process sliding window on auth endpoints now, Redis-backed when the Redis service is wired in Milestone 8/9 | Works with no extra service in dev | Per-process only; documented limitation |
| 9 | Frontend keeps existing stack; adds a typed `src/lib/api/` layer and TanStack Query hooks (already installed). No Zustand until a genuine global-state need appears | Avoid unnecessary dependencies | |
| 10 | External providers sit behind interfaces; with no key set the app raises an explicit `ProviderNotConfigured` error, and dev adapters are labelled `source="development"` in every response | Never present mock data as live data | Some features degrade until keys exist |
| 11 | Money stored as integer minor units plus ISO currency (`INR` default) | No float rounding errors in budget checks | Conversion helpers needed at the edges |
| 12 | Coordinates stored as `latitude`/`longitude` numeric columns (no PostGIS) initially; distances via haversine + provider routing | PostGIS adds an operational dependency; revisit if spatial queries become heavy | |
