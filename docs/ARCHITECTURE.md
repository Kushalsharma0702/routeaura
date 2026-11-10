# RouteAura Architecture

## 1. System overview

```
Browser (React/Vite)  --/api/v1 (JSON, JWT + refresh cookie)-->  FastAPI modular monolith
                                                                   |-- PostgreSQL (source of truth)
                                                                   |-- Redis (cache, rate limits, job queue)   [Milestone 8/9]
                                                                   |-- Providers: LLM, maps, weather, speech, payments (behind interfaces)
```

The existing front end is kept. It talks to the backend only through `src/lib/api/` (typed client) and TanStack Query hooks. Pages never call `fetch` directly.

## 2. Backend layout (`backend/app/`)

```
main.py                 app factory, middleware, exception handlers, routers
core/                   config (pydantic-settings), security (hashing, JWT), logging, errors, rate limit
database/               engine, session dependency, declarative base
models/                 SQLAlchemy 2.x ORM models (one file per aggregate)
schemas/                Pydantic v2 request/response models
repositories/           data access only; no business rules
services/               shared cross-module services
modules/<domain>/       router.py + service.py (+ domain-specific logic)
    authentication, users, destinations, attractions, recommendations,
    itinerary, optimization, context_engine, voice_assistant,
    hotels, bookings, notifications, analytics
integrations/           llm, maps, weather, speech, payments (interface + adapters)
workers/                background jobs
tests/
```

Rules: routers -> services -> repositories -> models. Routers contain no business logic. Services never import from routers. Integrations are injected, never imported directly by domain logic.

## 3. Database design (ER summary)

Implemented per milestone; **bold** = created in Milestone 1.

```
**users** 1--1 **user_preferences**
**users** 1--* **refresh_tokens**
**users** 1--* **audit_logs**
users 1--* trips 1--* itineraries 1--* itinerary_days 1--* itinerary_activities *--1 attractions
destinations 1--* attractions *--1 attraction_categories
destinations 1--* hotels 1--* room_types 1--* room_inventory (per date)
packages *--* attractions (package_attractions);   packages *--1 destinations
bookings 1--* booking_items (package | room_type + date range) ; bookings 1--* payments
itineraries 1--* optimization_runs ; itineraries 1--* itinerary_versions
trips 1--* weather_snapshots ; trips 1--* context_events (adaptation history)
users 1--* notifications (idempotency_key unique)
users 1--* user_interactions ; users 1--* recommendation_logs ; itineraries 1--* itinerary_feedback
users 1--* assistant_conversations 1--* assistant_messages
routes 1--* route_segments (between attractions/destinations, with mode, distance_m, duration_s, source)
```

Conventions: UUID primary keys, `created_at`/`updated_at` timestamptz, soft delete (`deleted_at`) only on user-facing catalogue entities (destinations, attractions, hotels, packages), money as integer minor units + currency, every `source` column distinguishes `provider` / `estimate` / `seed`. Constraints that matter: unique `users.email` (case-insensitive index), unique `(room_type_id, date)` in inventory with `CHECK (booked <= total)`, unique `notifications.idempotency_key`.

### Mock data -> database mapping

| Mock (`mockData.ts`) | Table(s) | Changes needed |
|---|---|---|
| `User` | `users`, `user_preferences` | `client` -> `traveler`; add password hash, status |
| `TravelPackage` | `packages`, `package_attractions` | `destination` string -> FK; `price` -> minor units; `visible` -> `is_published` |
| `Destination` | `destinations`, `attractions` | add lat/lng, categories, cost, duration, climate; `attractions: string[]` -> rows |
| `Route` | `routes`, `route_segments` | `distance`/`duration` strings -> numeric meters/seconds |
| `Booking` | `bookings`, `booking_items`, `payments` | client name/email/phone become joins on `users`; status enum extended (pending, confirmed, cancelled, failed, refunded) |
| chart series | derived by analytics queries | no table |

## 4. Authentication design

- `POST /auth/register`, `/auth/login` -> `{access_token}` + `Set-Cookie: refresh_token` (HttpOnly, SameSite=Lax, Secure in production, path `/api/v1/auth`).
- `POST /auth/refresh` rotates the refresh token. Presenting an already-rotated token revokes the entire token family (theft detection).
- `POST /auth/logout` revokes the family and clears the cookie.
- `get_current_user` and `require_role("admin")` dependencies enforce authorization server-side.

## 5. Frontend integration plan

1. `src/lib/api/client.ts`: fetch wrapper, base URL, bearer token from in-memory store, single-flight refresh on 401, typed error class.
2. `src/lib/api/<module>.ts` + `src/hooks/use<Module>.ts`: typed functions and TanStack Query hooks.
3. `AuthContext` becomes a thin wrapper over the auth API (session restored from the refresh cookie on load).
4. Pages migrate from `mockData` to hooks one module at a time; each migrated page gets loading, empty and error states and a test.
5. Vite dev proxy `/api -> http://localhost:8000` so cookies are same-origin.

## 6. AI and optimization plan (Milestones 3-6)

- **Recommender:** weighted content-based scoring over normalized features (interest cosine similarity, budget fit, season overlap, duration fit, climate, style); weights in config; per-feature contributions returned as the explanation. Evaluation: Precision@K, Recall@K, NDCG@K on a labelled set that is explicitly marked synthetic when synthetic.
- **Itinerary generator:** LLM only for (a) intent extraction into a Pydantic schema and (b) human-readable text. Candidate selection, scheduling, budget and opening-hour checks are deterministic. Every LLM output is schema-validated; numeric fields are recomputed by the backend.
- **Optimizer:** graph (NetworkX) with Dijkstra and A* (haversine heuristic) for path queries; OR-Tools routing/CP-SAT for ordering with time windows and the weighted objective `Z = aD + bT + cC + dP`; baselines (input order, nearest neighbour) for comparison; every run persisted in `optimization_runs`.
- **Context engine:** collect -> check freshness -> detect -> find affected activities -> candidates -> re-optimize affected span -> explain -> user approval -> persist. Weather and traffic only from configured providers.
- **Voice:** STT/TTS provider interfaces (Sarvam, Azure, browser fallback); the assistant calls the same recommendation/itinerary/booking services as the REST API.

## 7. Security plan

Argon2id, JWT validation with fixed algorithm and required claims, server-side RBAC, Pydantic validation everywhere, parameterized queries only (ORM), CORS allow-list, request size limit, auth rate limiting, audit log for admin writes, no stack traces to clients, secrets only from environment, `pip-audit` and `npm audit` in CI.

## 8. Testing plan

Backend: pytest against a real PostgreSQL test database built by running Alembic migrations; unit tests for pure algorithms; API tests via `TestClient`; concurrency test for booking inventory. Frontend: Vitest + Testing Library with the API layer mocked at the network boundary (MSW-style fetch mocks). E2E: scripted API-level flow first, browser E2E (Playwright) added in Milestone 9.


## 9. Intelligence layer (Wave 1)
```
POST /recommendations/*  -> RecommendationService -> engine (pure) : features -> profile -> scoring -> ranking/MMR -> explanations
POST /interactions        -> append-only user_interactions (state derived by folding events; idempotent)
POST /itineraries/generate-> ItineraryService
                              1. validate trip       2. rank attractions with the SAME engine (score_attractions)
                              3. LLM (optional, provider-independent, validated)  OR  deterministic planner
                              4. planner (pure): select -> nearest-neighbour order -> first-fit day packing -> time schedule -> validate
                              5. persist itinerary + activities + version 1 (PostgreSQL)
```
* `engine/` and `itinerary/planner.py` import no database or framework code and are tested directly; services only translate between ORM rows and engine data classes.
* `integrations/llm/`: `LLMClient` protocol, `NoLLM` (default), `AnthropicLLM` (HTTPS; request shape tested with fakes, **not exercised against the live API**). The itinerary service never trusts model output: IDs must belong to the supplied candidates, no duplicates, limits per day, otherwise retry once then fall back.
* Tables added: `user_interactions`, `recommendation_runs`, `recommendation_items`, `recommendation_feedback` (0004); `itineraries`, `itinerary_activities`, `itinerary_versions` (0005). Preference snapshots live in `recommendation_runs.preferences`.
* Ownership is enforced in the service layer for every itinerary/run/impression/feedback access.
* Travel times are estimates (great-circle x 1.3 / 30 km/h) and labelled as such; routing providers are the next wave.


## 10. Routing and context layer (Wave 2)
```
ItineraryService._reschedule  -> RoutingProvider.matrix(points)   (estimate | osrm | resilient fallback)  -> legs stored on activities
POST /itineraries/{id}/optimize -> OptimizationService: matrix -> OR-Tools (day assignment + order, windows, lunch, budget, locked)
                                   -> re-evaluate with planner (authoritative) -> persist OptimizationRun (preview) -> explicit apply
POST /itineraries/{id}/adapt    -> ContextService: fresh weather snapshots + verified hours + traveler reports
                                   -> context.engine (pure): detect -> alternatives -> feasibility-aware pick -> simulate
                                   -> pending AdaptationProposal -> traveler approves/rejects -> new itinerary version
```
* `modules/routing/graph.py`: Dijkstra and A* (tested against NetworkX); `optimizer.py`: OR-Tools; `explain.py`: pure change explanations; `service.py`: persistence/approval. Graph pathfinding and TSP-style ordering are separate problems and neither is real road routing: road times come from a provider or are labelled estimates.
* Providers sit behind interfaces (`integrations/routing`, `integrations/weather`); defaults are `estimate` and `none`. OSRM and Open-Meteo adapters are verified only against mocked HTTP responses, **never against the live services**.
* Tables (0006): `optimization_runs`, `context_snapshots`, `adaptation_proposals`, plus `itinerary_activities.locked`.
* Freshness: weather older than `WEATHER_MAX_AGE_MINUTES` (default 180) is reported as stale and never acted on.
* Known OR-Tools quirk: the `SetAllowedVehiclesForIndex` binding is broken in 9.15, so day restrictions use `VehicleVar(...).RemoveValue(...)`.


## 11. Voice, bookings and notifications (Wave 3)
```
/assistant/chat -> AssistantService: nlu (rules, en/hi; optional LLM intent) -> RecommendationService | ItineraryService | BookingService (read-only)
                   destructive edit -> "awaiting_confirmation" -> explicit yes/no turn; the assistant never pays or cancels
/assistant/voice/* -> SpeechProvider (none | Sarvam | Azure)  ; browser Web Speech API is the client-side fallback
POST /bookings (Idempotency-Key) -> lock room_inventory rows (FOR UPDATE, ordered by day) -> decrement availability -> pending_payment + hold
POST /bookings/{id}/pay -> PaymentProvider (development simulator only) -> confirmed | failed ; cancel -> refund per policy ; expire_holds job releases stock
workers: expire_holds, trip_reminders, weather_alerts, deliver_notifications  (advisory lock on a dedicated connection; one runner at a time)
notifications: ON CONFLICT (idempotency_key) DO NOTHING -> in-app list/unread; optional email delivery with retries
```
* Concurrency safety rests on the database: ordered row locks, `CHECK (booked <= total)`, unique `(user_id, idempotency_key)`; verified with real multi-thread tests.
* Payment, speech and email providers sit behind interfaces; only the payment simulator, mocked-HTTP speech adapters and an SMTP adapter exist, none verified live.
* `today_local()` (`BOOKING_TIMEZONE`, default Asia/Kolkata) defines "today" for booking dates and refund tiers.
