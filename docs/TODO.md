# TODO

## Next action
Start Milestone 3 (see the end of `IMPLEMENTATION_STATUS.md`).

## Needs a decision from the owner
- Credentials needed later: LLM key (M4), maps/routing key (M5), weather key (M6), Sarvam/Azure speech (M7), payment sandbox (M8). Until then the adapters will be explicit dev adapters.

## Verification debt (do before relying on these)
- Click through the traveler and admin catalogue screens in a real browser (layout, dialogs, mobile nav with 5 items).
- Build and run `docker compose up --build` on a machine with a running daemon; confirm migration 0003 enables PostGIS and the API reports the PostGIS backend.
- First GitHub Actions run of `.github/workflows/ci.yml` (the pip-audit step is advisory).
- Benchmark radius search with PostGIS vs haversine on a larger data set (thousands of attractions).

## Deferred / not yet in scope
- Map UI (Leaflet) with markers and radius circle: with the itinerary/route milestones.
- Image upload/storage (images are URLs).
- Real provider data for destinations/attractions/opening hours (`source=provider`).
- Email verification and password reset.
- Redis-backed rate limiter (currently in-process).
- Packages, routes and bookings still on mock data: Milestone 8 (bookings/packages) and Milestone 5 (routes).
- Browser E2E (Playwright): Milestone 9.
