# TODO

## Next action
Wave 2: route optimization (OR-Tools, Dijkstra/A*) and context adaptation (weather/routing providers, approval workflow).

## Needs the owner
- Provider credentials, none required to run: LLM (`LLM_PROVIDER=anthropic`, `LLM_API_KEY`), later routing, weather, speech (Sarvam/Azure), payment sandbox, email/SMS.
- Permission before any public deployment or paid service.

## Verification debt
- Run the LLM path once against a real provider and review the plans.
- Click through For You, Planner and My Trips in a real browser.
- `docker compose up --build` end to end; first GitHub Actions run; PostGIS test run on the final code.
- Real opening hours/fees for catalogue data (`source=provider`), otherwise checks stay "unknown".

## Deferred
- Map UI, routing provider, optimization (Wave 2); voice, bookings, notifications (Wave 3); release hardening.
- Email verification / password reset; Redis rate limiter; image upload.
