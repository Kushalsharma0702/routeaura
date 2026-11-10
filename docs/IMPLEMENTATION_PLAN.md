# Implementation Plan and Backlog

A feature is done only when backend logic, frontend integration, persistence, validation, tests and docs all exist. Status is tracked in `IMPLEMENTATION_STATUS.md`.

| Milestone | Scope | Exit criteria |
|---|---|---|
| 0 | Audit, architecture, plan | Docs written; build/test baseline recorded |
| 1 | Backend foundation, PostgreSQL, Alembic, auth (register/login/refresh/logout/RBAC), profile + preferences, frontend auth integration, Docker/Compose skeleton, CI | Register/login/logout work from the UI against the real DB; auth + RBAC tests pass |
| 2 | Destinations, attractions, categories; admin CRUD; search/filter/pagination; seed data with coordinates; migrate Browse/ManageDestinations pages | Admin edits persist across refresh; tests pass |
| 3 | Recommendation engine, feedback, interaction logs, Precision@K/Recall@K/NDCG evaluation script, dashboard section | Ranked results with explanations; metrics reproducible |
| 4 | LLM provider interface, intent extraction, itinerary generation + validation, persistence, versions, planner UI | Natural-language request -> stored, validated itinerary |
| 5 | Distance matrix, Dijkstra, A*, OR-Tools ordering with time windows, optimization runs, baseline comparison, map + route UI | Optimizer beats baselines in recorded runs; unit tests on known graphs |
| 6 | Weather/map adapters, context engine, adapt endpoint, approval flow | Rain/closure scenarios produce explained, approved changes |
| 7 | Assistant chat (EN/HI), STT/TTS interfaces, conversation persistence, voice UI | Text chat works without keys; voice works when keys present |
| 8 | Hotels, rooms, inventory, transactional bookings, cancellation/refund states, payments adapter, notifications + worker | Concurrent booking test proves no overbooking |
| 9 | Analytics + experiment exports, Playwright E2E, production compose, full CI, final docs | Definition of Done checklist met |

## Cross-cutting backlog (do alongside)

- Fix the 3 existing lint errors (Milestone 1).
- Code-split the 1 MB bundle with route-level lazy loading (Milestone 2).
- Replace `mockData` imports page by page; delete `mockData.ts` when unused (end of Milestone 8).
- Rename leftover "Escapade Central" strings to RouteAura (Milestone 1).
- Pick one lockfile (npm) and remove `bun.lockb` (needs the owner's go-ahead, so left in place for now).
