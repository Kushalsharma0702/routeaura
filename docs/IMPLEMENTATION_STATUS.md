# Implementation Status

_Last updated: 2026-11-11_

| Wave / Milestone | Status |
|---|---|
| 0 Audit & architecture | ✅ |
| 1 Backend foundation & auth | ✅ (tag `milestone-1-auth-foundation`) |
| 2 Destinations, attractions, spatial search | ✅ (commit `45a1a23`) |
| **Wave 1: 3 Recommendations + 4 AI itinerary generator** | ✅ implemented and verified, see below |
| Wave 2: 5 Route optimization + 6 Context adaptation | ⏳ not started |
| Wave 3: 7 Voice + 8 Bookings/notifications | ⏳ not started |
| Final release & research validation | ⏳ not started |

## Wave 1 delivered
**Recommendations** (`docs/RECOMMENDATION_ENGINE.md`): deterministic, LLM-free engine with feature normalisation/encoding, weighted content-based scoring, cosine interest similarity, budget/duration/climate/season/style compatibility, explicit priorities, MMR diversity re-ranking, per-feature explanations, honest missing-data policy (lower bound + confidence), popularity fallback for cold start, interaction + feedback persistence with decayed history, recommendation history, and strict per-user privacy. APIs: `/recommendations/{destinations,attractions,history,feedback}`, `/interactions`.
**Itinerary generator** (`planner.py`, `llm_planning.py`, `service.py`): trip validation, attraction ranking with the same engine, optional provider-independent LLM (intent parsing + day grouping, Pydantic-validated, one retry) with a deterministic fallback that is always labelled; deterministic selection, nearest-neighbour ordering, first-fit packing, lunch break, opening-hour checks only where verified and dated, budget and time validation, persistence, versions with restore, add/remove/edit/reorder/regenerate, ownership enforcement.
**Frontend**: "For You" page (preference controls, priorities, variety, explanations, save/hide/feedback, saved, history), dashboard recommendations section, destination save/like/view tracking, planner form, My Trips, itinerary detail (day tabs, activity cards, budget breakdown, generation log, validations, edit/regenerate/restore).
**Evaluation** (all SYNTHETIC, seeded, reproducible): `docs/research/RECOMMENDATION_EVALUATION.md`, `docs/research/ITINERARY_EVALUATION.md`.

## Verified test results (2026-11-11)
| Check | Result |
|---|---|
| Backend `uv run pytest -q` (plain PostgreSQL 18) | **256 passed, 8 skipped** (the skipped are PostGIS-only variants; last PostGIS run was at Milestone 2) |
| Backend `ruff check` | clean |
| Frontend `npm test` | **67 passed** (10 files), stable over 3 runs |
| `npx tsc -p tsconfig.app.json --noEmit`, `npm run lint` | clean; 0 lint errors, 8 old react-refresh warnings |
| `npm run build` | passes |
| Live API run (real DB, real seed data) of recommendations | cold start fallback, ranked + explained results, season flip, idempotent save, feedback, history, 404 for another user's run/impression, 401 anonymous |

## Known gaps and honest caveats
1. **The LLM path has never been run against a real provider** (no credentials). It is tested with scripted fake clients (valid plans, malformed output, invented ids, transport errors, retry, prompt interpretation). `AnthropicLLM` is verified only for request shape.
2. **Itinerary generation was not exercised through a browser** (it was run live against the real API and database: generate, edit, version, restore, 404 for another user); it is covered by 49 backend API/planner tests and 10 frontend tests with mocked network.
3. **Travel times are estimates** (great-circle x 1.3 / 30 km/h) and labelled as such; there is no routing provider yet (Wave 2). Seed attractions have no verified opening hours and no entry fees, so opening-hour checks and activity costs are mostly "unknown" for real data.
4. Mobile bottom nav: "Packages" was replaced by "Trips" (6 items). Packages/bookings are still mock data until Wave 3.
5. Evaluation results are synthetic and share signal families with the scorer (see the research docs for limits); no user study exists.
6. `group_size` and `accommodation_preference` are stored but not scored (no catalogue data); the API says so in `notes`.
7. Docker images and GitHub Actions have still not been run end to end (planned for the final release phase). Rate limiting is per-process.
