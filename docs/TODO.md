# TODO

## Next action
Wave 3: multilingual voice assistant (Hindi/English; Sarvam, Azure, browser fallback), hotels/rooms/inventory, concurrency-safe bookings, development payment adapter, notifications (in-app first), then removal of the remaining mock data (packages, routes, bookings, analytics).

## Needs the owner
- Credentials, none required to run: `LLM_API_KEY`, `OSRM_BASE_URL` (or another routing service), `WEATHER_PROVIDER=open-meteo` (no key; sends destination coordinates), later Sarvam/Azure speech keys, payment sandbox, email/SMS.
- Permission before any public deployment or paid service.

## Verification debt
- Run the LLM, OSRM and Open-Meteo adapters once against the real services and review results.
- Click through For You, Planner, My Trips (map, optimize, conditions) in a real browser; check the map on mobile widths.
- `docker compose up --build` end to end; first GitHub Actions run; PostGIS test run on the final code.
- Real opening hours/fees for catalogue data (`source=provider`); otherwise checks stay "unknown".
- Benchmark the optimizer on larger instances and compare with an exact solver.

## Deferred
- Road geometry polylines on the map (needs a provider that returns them).
- Notifications for adaptation alerts and trip reminders (Wave 3).
- Voice, hotels/bookings/payments, notifications, mock-data removal (Wave 3); release hardening (final phase).
- Email verification / password reset; Redis rate limiter; image upload.
