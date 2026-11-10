# Implementation Status

_Last updated: 2026-11-11_

| Wave / Milestone | Status |
|---|---|
| 0 Audit & architecture | ✅ |
| 1 Backend foundation & auth | ✅ (tag `milestone-1-auth-foundation`) |
| 2 Destinations, attractions, spatial search | ✅ (commit `45a1a23`) |
| **Wave 1: 3 Recommendations + 4 AI itinerary generator** | ✅ implemented and verified, see below |
| **Wave 2: 5 Route optimization + 6 Context adaptation** | ✅ implemented and verified, see below |
| **Wave 3: 7 Voice assistant + 8 Hotels/bookings/payments/notifications** | ✅ implemented and verified, see below |
| Final release & research validation | ⏳ not started |

## Wave 1 delivered
**Recommendations** (`docs/RECOMMENDATION_ENGINE.md`): deterministic, LLM-free engine with feature normalisation/encoding, weighted content-based scoring, cosine interest similarity, budget/duration/climate/season/style compatibility, explicit priorities, MMR diversity re-ranking, per-feature explanations, honest missing-data policy (lower bound + confidence), popularity fallback for cold start, interaction + feedback persistence with decayed history, recommendation history, and strict per-user privacy. APIs: `/recommendations/{destinations,attractions,history,feedback}`, `/interactions`.
**Itinerary generator** (`planner.py`, `llm_planning.py`, `service.py`): trip validation, attraction ranking with the same engine, optional provider-independent LLM (intent parsing + day grouping, Pydantic-validated, one retry) with a deterministic fallback that is always labelled; deterministic selection, nearest-neighbour ordering, first-fit packing, lunch break, opening-hour checks only where verified and dated, budget and time validation, persistence, versions with restore, add/remove/edit/reorder/regenerate, ownership enforcement.
**Frontend**: "For You" page (preference controls, priorities, variety, explanations, save/hide/feedback, saved, history), dashboard recommendations section, destination save/like/view tracking, planner form, My Trips, itinerary detail (day tabs, activity cards, budget breakdown, generation log, validations, edit/regenerate/restore).
**Evaluation** (all SYNTHETIC, seeded, reproducible): `docs/research/RECOMMENDATION_EVALUATION.md`, `docs/research/ITINERARY_EVALUATION.md`.

## Wave 2 delivered
**Route optimization** (`modules/routing/`): OR-Tools multi-day optimizer (day assignment + order) with verified opening windows, lunch break, start location, required/locked activities, budget, configurable objective `Z = a*distance + b*time + c*cost + d*preference`, relaxed/infeasible handling with diagnostics, plain-language comparison of original vs optimized plan, persisted previews and explicit, version-checked apply. Dijkstra and A* (own implementations, parity-tested against NetworkX). Routing providers behind an interface: labelled great-circle `estimate` (default) and an OSRM adapter with resilient fallback; the source is stored and shown for every itinerary.
**Context adaptation** (`modules/context/`, `integrations/weather/`): weather provider interface (`none` default, Open-Meteo adapter), freshness checks (stale data is never acted on), rain/heat alternatives, closure replacements (admin-verified hours or traveler reports), delay re-planning, budget-aware alternatives, feasibility-aware replacement choice, deduplicated pending proposals, approve/reject with staleness protection, adaptation history. Approval is always required.
**Frontend**: Leaflet map (order lines, original dashed vs optimized solid), optimization controls with before/after comparison and apply, lock toggle on activities, conditions panel with provenance, traveler reports, and approve/reject of suggestions.
**Evaluation** (SYNTHETIC): `docs/research/ROUTING_CONTEXT_EVALUATION.md`.

## Wave 3 delivered
**Bookings** (`modules/bookings/`, migration 0007): hotels, room types, per-night inventory (`CHECK booked <= total`), bookings with a 15-minute payment hold, idempotent create/pay (`Idempotency-Key`, unique per user), row-locked inventory (`SELECT ... FOR UPDATE`), pay/cancel/expire under booking-row locks, refund policy (>=2 days 100%, 1 day 50%, else 0; admin cancel 100%), retry of failed refunds, DB-derived admin analytics. Payments go through an interface with **only a development simulator** (labelled `simulated`; no card data is collected). Hotel seed data is fictional with placeholder prices.
**Notifications** (`modules/notifications/`, `workers/`): idempotent in-app notifications (booking, hold expiry, trip reminders, weather alerts, adaptation proposals/approvals); optional SMTP email (skipped without provider, retried up to 3 times); jobs `expire_holds`, `trip_reminders`, `weather_alerts`, `deliver_notifications` run by `python -m app.workers.run --once|--loop` or in-process with `BACKGROUND_JOBS_ENABLED=true`, guarded by a Postgres advisory lock on a dedicated connection.
**Voice assistant** (`modules/assistant/`, `integrations/speech/`): deterministic English/Hindi NLU (optional LLM intent with rule fallback), dispatches only to the existing recommendation, itinerary and booking services, destructive edits need an explicit yes/no turn, the assistant cannot pay or cancel bookings. Speech: Sarvam and Azure adapters, browser Web Speech fallback; missing/failed speech never blocks text chat.
**Frontend**: Hotels, hotel detail with availability and booking, payment dialog (simulator warning), My Bookings (refund preview), notifications bell and page, Assistant page (language switch, text and voice, confirm buttons), live client and admin dashboards, admin Hotels (hotel form, rooms, inventory) and Bookings. **Mock data removed**: `src/data/mockData.ts`, Packages and Routes pages (admin and client) and `StatusBadge` were deleted; no page reads mock data. Travel packages and the standalone routes catalogue no longer exist in the UI (routes are produced by the optimizer on itineraries).

## Verified test results (2026-11-11, Wave 3 code)
| Check | Result |
|---|---|
| Backend `uv run pytest -q` (plain PostgreSQL 18) | **488 passed, 8 skipped** (PostGIS-only variants), including 3 real multi-thread booking-concurrency tests |
| Backend `ruff check` | clean |
| Frontend `npx vitest run` | **94 passed** (13 files) |
| `npx tsc -p tsconfig.app.json --noEmit`, `npm run lint`, `npm run build` | clean / 0 lint errors (8 old react-refresh warnings) / passes |

## Wave 3 caveats
* **Sarvam, Azure speech and SMTP adapters were never run against live services** (mocked HTTP/SMTP only). Without credentials the assistant works in text and uses browser speech where the browser supports it.
* **Payments are a development simulator only.** No real gateway integration exists; going live needs a provider adapter, webhook handling and a security review.
* Hindi NLU is rule-based and covers a limited vocabulary; unknown phrasing gets a clarification, not a guess.
* The new UI (booking flow, assistant, voice capture, map) was verified by component tests with mocked network, not in a real browser; browser speech recognition support varies.
* Hotel inventory/prices are illustrative seed data; no live hotel supplier.
* SMS delivery has a table but no provider.

## Earlier verified results (2026-11-11, Wave 2 code)
| Check | Result |
|---|---|
| Backend `uv run pytest -q` (plain PostgreSQL 18) | **351 passed, 8 skipped** (the skipped are PostGIS-only variants; last PostGIS run was at Milestone 2) |
| Backend `ruff check` | clean |
| Frontend `npm test` | **80 passed** (11 files), stable over 3 runs |
| `npx tsc -p tsconfig.app.json --noEmit`, `npm run lint` | clean; 0 lint errors, 8 old react-refresh warnings |
| `npm run build` | passes |
| Live API run (real DB, real seed data) of recommendations | cold start fallback, ranked + explained results, season flip, idempotent save, feedback, history, 404 for another user's run/impression, 401 anonymous |

## Wave 2 caveats (in addition to the list below)
* **OSRM and Open-Meteo adapters were never run against the live services** (mocked HTTP only); no weather or routing provider is configured by default, so by default travel times are estimates and weather is unavailable (reports and verified hours still work).
* **The Leaflet map was not rendered in a real browser**; component tests use a stub that records what would be drawn. Lines connect stops in order and are not road geometry.
* Optimization quality is measured only against the planner's own travel estimates; no exact-solver comparison or large-instance benchmark.
* OR-Tools `improve` mode (guided local search) is time-limited and not repeatable; the default is deterministic.
* Alternatives still introduce a schedule issue in ~42% of proposals in the synthetic benchmark; previews show them and approval is required.
* Notifications are sent for new proposals and approvals (Wave 3); ignoring a proposal produces no reminder.

## Known gaps and honest caveats (Wave 1)
1. **The LLM path has never been run against a real provider** (no credentials). It is tested with scripted fake clients (valid plans, malformed output, invented ids, transport errors, retry, prompt interpretation). `AnthropicLLM` is verified only for request shape.
2. **Itinerary generation was not exercised through a browser** (it was run live against the real API and database: generate, edit, version, restore, 404 for another user); it is covered by 49 backend API/planner tests and 10 frontend tests with mocked network.
3. **Travel times are estimates** (great-circle x 1.3 / 30 km/h) and labelled as such; there is no routing provider yet (Wave 2). Seed attractions have no verified opening hours and no entry fees, so opening-hour checks and activity costs are mostly "unknown" for real data.
4. Mobile bottom nav is limited to 6 items. (Packages/routes mock pages were removed in Wave 3.)
5. Evaluation results are synthetic and share signal families with the scorer (see the research docs for limits); no user study exists.
6. `group_size` and `accommodation_preference` are stored but not scored (no catalogue data); the API says so in `notes`.
7. Docker images and GitHub Actions have still not been run end to end (planned for the final release phase). Rate limiting is per-process.
