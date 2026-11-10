# TODO

## Next action
Final release phase: full verification, security and authorization audits, migration up/down check, Docker Compose and CI validation, reproducible evaluations, performance benchmarks, release checklist.

## Needs the owner
- Credentials, none required to run: `LLM_API_KEY`, `OSRM_BASE_URL` (or another routing service), `WEATHER_PROVIDER=open-meteo` (no key; sends destination coordinates), `SPEECH_PROVIDER` + Sarvam/Azure keys, `EMAIL_PROVIDER=smtp` + `SMTP_*`, a real payment gateway (only the simulator exists), SMS provider.
- Permission before any public deployment or paid service.

## Verification debt
- Run the LLM, OSRM and Open-Meteo adapters once against the real services and review results.
- Click through For You, Planner, My Trips (map, optimize, conditions) in a real browser; check the map on mobile widths.
- `docker compose up --build` end to end; first GitHub Actions run; PostGIS test run on the final code.
- Real opening hours/fees for catalogue data (`source=provider`); otherwise checks stay "unknown".
- Benchmark the optimizer on larger instances and compare with an exact solver.

## Deferred
- Live verification of Sarvam/Azure/SMTP adapters; real payment gateway + webhooks; SMS provider; hotel supplier integration.
- Browser click-through of booking, assistant and voice flows.
- Road geometry polylines on the map (needs a provider that returns them).
- Release hardening (final phase).
- Email verification / password reset; Redis rate limiter; image upload.
