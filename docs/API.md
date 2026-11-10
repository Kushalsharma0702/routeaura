# API Contract

Base URL `/api/v1`. Interactive docs (non-production): `http://localhost:8000/docs`.
All errors share one shape: `{"error": {"code": "...", "message": "...", "details": null | [...]}}`.
Validation failures return `422` with `code: "validation_error"` and `details: [{field, message}]`.
Auth: `Authorization: Bearer <access_token>` (see Milestone 1 endpoints below).

## Conventions
- Money is **integer minor units** (paise) plus `currency` (default `INR`).
- Paginated responses: `{items, total, page, page_size}`. `page >= 1`, `1 <= page_size <= 100`.
- `source` on records: `seed` / `admin` = curated estimates; only `provider` is sourced data. `opening_hours_source: null` (and `opening_hours: null`) means **unknown**, never assumed.
- Public endpoints return only **published, non-deleted** records. An attraction is public only if its destination is also published.
- IDs are UUIDs; destinations can also be addressed by `slug` on public reads.

## Auth and users (Milestone 1)
| Method | Path | Access | Notes |
|---|---|---|---|
| POST | `/auth/register` | public | 201, sets `ra_refresh` HttpOnly cookie, returns `{access_token, expires_in, user}`. Always creates a `traveler`. 409 `email_taken` |
| POST | `/auth/login` | public | Same response; 401 `invalid_credentials` (identical for unknown email / wrong password); 403 `account_disabled` |
| POST | `/auth/refresh` | cookie | Rotates the refresh token; replaying an old one revokes the session |
| POST | `/auth/logout` | cookie | 204 |
| GET/PATCH | `/users/me` | user | |
| GET/PUT | `/users/me/preferences` | user | |
| GET | `/users` | admin | `q`, `page`, `page_size` |
| PATCH | `/users/{id}` | admin | `role`, `is_active`; audited; cannot modify self |

## Catalogue: public reads (no authentication)
| Method | Path | Query params | Response |
|---|---|---|---|
| GET | `/categories` | | `Category[]` |
| GET | `/destinations` | `q`, `country`, `category` (slug), `climate`, `month` (1-12, best-season filter incl. wrap-around such as Oct-Mar), `max_cost_minor`, `lat`+`lng`+`radius_km` (all three or none), `sort` = `name\|-name\|cost\|-cost\|duration\|newest\|distance`, `page`, `page_size` (default 12) | `Page<Destination>` |
| GET | `/destinations/nearby` | `lat`, `lng` (required), `radius_km` (default 10, max 500), `page`, `page_size` | `Page<Destination>` sorted by distance, each with `distance_m` |
| GET | `/destinations/{id\|slug}` | | `Destination` (404 if unpublished/deleted) |
| GET | `/destinations/{id\|slug}/attractions` | `q`, `category`, `outdoor`, `sort`, `page`, `page_size` (default 50) | `Page<Attraction>` |
| GET | `/attractions` | `q`, `destination_id`, `category`, `outdoor`, `lat`+`lng`+`radius_km`, `sort`, `page`, `page_size` (default 20) | `Page<Attraction>` |
| GET | `/attractions/nearby` | `lat`, `lng` (required), `radius_km` (default 10, max 500), `category`, `outdoor`, `page`, `page_size` | `Page<Attraction>` nearest first with `distance_m` |
| GET | `/attractions/{id}` | | `Attraction` |

`sort=distance` requires a centre. `q` is a case-insensitive substring match (LIKE wildcards in input are literal). Latitude must be within [-90, 90], longitude within [-180, 180] (422 otherwise).

## Catalogue: admin writes (`Authorization` with an admin token; 401 anonymous, 403 traveler)
| Method | Path | Body / params |
|---|---|---|
| POST | `/admin/categories` | `{name, description?}`; 409 `category_exists` (case-insensitive) |
| PATCH | `/admin/categories/{id}` | `{name?, description?}` |
| DELETE | `/admin/categories/{id}` | 204; 409 `category_in_use` when referenced |
| GET | `/admin/destinations` | `q`, `country`, `category`, `climate`, `include_deleted`, `sort`, `page`, `page_size`; includes drafts |
| GET | `/admin/destinations/{id}` | includes drafts |
| POST | `/admin/destinations` | see below; 201 |
| PATCH | `/admin/destinations/{id}` | any subset; required fields cannot be set to `null`; season months must be set/cleared together |
| DELETE | `/admin/destinations/{id}` | **soft delete**; also soft-deletes its attractions; 204 |
| GET | `/admin/attractions` | `destination_id`, `q`, `category`, `sort`, `page`, `page_size`; includes drafts |
| GET | `/admin/attractions/{id}` | |
| POST | `/admin/attractions` | see below; 201 |
| PATCH | `/admin/attractions/{id}` | any subset |
| DELETE | `/admin/attractions/{id}` | soft delete; 204 |

### Destination body
`name` (2-120), `country` (2-80), `region?`, `description` (<=5000), `latitude`, `longitude`, `estimated_cost_per_day_minor?` (>=0), `recommended_duration_days?` (1-60), `best_season_start_month?` + `best_season_end_month?` (1-12, both or neither), `climate?` (`tropical|temperate|cold|arid|any`), `climate_notes?`, `accessibility_notes?`, `images` (<=12 http(s) URLs), `is_published` (default false), `category_ids` (<=10 existing categories; 422 `unknown_category` otherwise).
Response adds `id`, `slug` (generated from the name, unique, stable after renames), `source`, `categories[]`, `attraction_count`, `distance_m` (only in radius queries), timestamps, `deleted_at`.

### Attraction body
`destination_id` (create only; 422 `unknown_destination`), `category_id` (422 `unknown_category`), `name` (2-140), `description`, `latitude`, `longitude`, `estimated_cost_minor?`, `typical_duration_minutes` (5-1440), `opening_hours?` = `{"mon": [["09:30","17:30"]], "sun": []}` (days `mon..sun`, empty list = closed, absent day = unknown, `HH:MM` with open < close), `is_outdoor`, `accessibility_notes?`, `images`, `is_published`.
Response adds `id`, `slug` (unique per destination), `category{id,slug,name}`, `opening_hours_source` (`admin` when hours were provided), `source`, `distance_m`.

Every admin write is recorded in `audit_logs`.

## Spatial behaviour
Distances are metres on a sphere (R = 6,371,008.8 m). With PostGIS the query uses `ST_DWithin`/`ST_Distance` (spheroid disabled) on a GiST-indexed `geography` column; without it, a bounding-box prefilter on indexed `latitude, longitude` plus an SQL haversine. The two backends are tested against each other and against a pure-Python reference (including the antimeridian and poles).


## Recommendations and interactions (Wave 1; all endpoints require authentication)
| Method | Path | Notes |
|---|---|---|
| POST | `/recommendations/destinations` | body `RecommendationRequest`; returns `RecommendationResponse` |
| POST | `/recommendations/attractions` | same; attraction filters: `filters.destination_id`, `filters.category`, `filters.outdoor` |
| GET | `/recommendations/history` | `kind`, `page`, `page_size`; the caller's own runs, newest first |
| GET | `/recommendations/history/{run_id}` | run detail with config, preference snapshot, impressions and explanations; other users' runs return 404 |
| POST | `/recommendations/feedback` | `{recommendation_item_id, rating: relevant\|not_relevant, reasons[], comment?}`; upserts one row per user+impression; 404 for someone else's impression |
| POST | `/interactions` | `{item_type, item_id, interaction_type, source?, recommendation_item_id?}` -> `{recorded, state}`; state events are idempotent (`recorded:false` when nothing changed) |
| GET | `/interactions/state` | `item_type`, `item_id` -> `{saved, liked, disliked, dismissed}` |
| GET | `/interactions/saved` | `item_type?`, paging; only published items |

`RecommendationRequest`: `overrides` (`budget_per_day_minor`, `trip_duration_days`, `interests`, `preferred_climate`, `preferred_season`, `travel_month`, `travel_style`; a sent field replaces the saved value, null clears it), `priorities` (`{interest|budget|duration|climate|season|style: ignore|low|normal|high}`), `filters`, `strategy` (`weighted` default, `cosine`, `popularity`), `diversify` (default true), `diversity_lambda` (0-1), `include_dismissed`, `page`, `page_size` (<= 50). Each request persists one run (preference snapshot, config, impressions).
Response items: `recommendation_item_id`, `rank`, `original_rank`, `score` (relevance, **not a probability**), `confidence`, `components[]`, `reasons[]`, `cautions[]`, `missing[]`, `saved/liked/disliked`, and the `destination` or `attraction`. `strategy` is `weighted|cosine|popularity|popularity_fallback`. See `RECOMMENDATION_ENGINE.md`.

## Itineraries (Wave 1; all endpoints require authentication and are scoped to the owner, other users get 404)
| Method | Path | Notes |
|---|---|---|
| POST | `/itineraries/generate` | `TripRequest` -> 201 `Itinerary`. Needs `destination_id` and `days` or `start_date`+`end_date`; optional `travelers`, `budget_total_minor`, `interests`, `travel_style`, `accommodation_preference`, `start_location{name,lat,lng}`, `title`, `prompt`, `use_llm` |
| GET | `/itineraries` | paging; own, non-deleted |
| GET / PATCH / DELETE | `/itineraries/{id}` | PATCH: `title`, `status (draft\|saved)`, `budget_total_minor`, `traveler_count`, `start_date`; DELETE is a soft delete (204) |
| POST | `/itineraries/{id}/regenerate` | optional `interests`, `travel_style`, `budget_total_minor`, `use_llm`; replaces all activities (previous version stays restorable) |
| POST | `/itineraries/{id}/activities` | `{attraction_id, day_number, position?, duration_min?}`; 409 if already present; 422 if not a published attraction of this destination |
| PATCH / DELETE | `/itineraries/{id}/activities/{aid}` | PATCH `duration_min`, `notes`; DELETE returns the updated itinerary |
| POST | `/itineraries/{id}/reorder` | `{days:[{day_number, activity_ids[]}]}` must list every activity exactly once |
| GET | `/itineraries/{id}/versions`, `/versions/{n}` | history and snapshots |
| POST | `/itineraries/{id}/versions/{n}/restore` | creates a new version; history is never rewritten |

`Itinerary` includes `day_plans[].activities[]` (start/end time, `duration_min`, `travel_min`/`travel_m` with `travel_source: "estimate"`, `cost_minor` per person or null when unknown, `hours_status` `verified_open|verified_closed|unknown`, `warnings`, `explanation`), `budget` (known costs only, living estimate, deviation, `unknown_cost_items`), `violations[]` (`day_overrun|opening_hours|max_per_day|budget`), `generation_source` (`llm|deterministic_fallback`) and `generation_info` (notes, per-step timings, LLM provider/model/error, dropped attractions).
Generation: the LLM (when `LLM_PROVIDER` and `LLM_API_KEY` are set) may only interpret a free-text `prompt` and propose day groupings from the supplied attraction ids; output is Pydantic-validated (one retry), then scheduled and checked by deterministic code. Any failure falls back to the deterministic planner and says so. Times, costs and constraints are never taken from the model.


## Route optimization (Wave 2; authenticated, owner-scoped, other users get 404)
| Method | Path | Notes |
|---|---|---|
| POST | `/itineraries/{id}/optimize` | body `{weights?: {distance,time,cost,preference,taxi_rupees_per_km}, improve?: bool, time_limit_ms?: 200-10000}` -> 201 `Optimization` **preview**; nothing changes |
| GET | `/itineraries/{id}/optimizations`, `/optimizations/{run_id}` | history / one run |
| POST | `/optimizations/{run_id}/apply` | applies the previewed plan as a new version; 409 `stale_optimization` if the itinerary changed since, `already_applied`, `nothing_to_apply` (infeasible) |
| PATCH | `/itineraries/{id}/activities/{aid}` | now also accepts `locked: bool` (locked and user-added activities are never dropped by the optimizer) |

`Optimization`: `status` (`optimized|relaxed|infeasible`), `before` / `after` (`days[].stops[]` + `metrics`: distance, travel minutes, wait, violations, budget), `delta`, `changes[]` (plain-language explanation), `dropped[]` (with reasons), `routing` (`source`, `notes`, `live_traffic`, `fetched_at`), `weights`, `solver_ms`. `relaxed` means no plan satisfied every constraint, so opening hours and lunch were ignored and the remaining violations are listed; `infeasible` leaves the itinerary unchanged and explains why.
Objective: `Z = alpha*distance_km + beta*travel_min + gamma*travel_cost_rupees + delta*preference_penalty` (see `modules/routing/optimizer.py`). Travel data comes from the configured routing provider (`ROUTING_PROVIDER=osrm`, `OSRM_BASE_URL`) or, by default, the labelled great-circle estimate; saved itineraries record the source in `generation_info.routing` and every activity returns `travel_source`.

## Context adaptation (Wave 2)
| Method | Path | Notes |
|---|---|---|
| GET | `/itineraries/{id}/context` | provider status, weather snapshots (source, age, `fresh`), traveler reports, notes |
| POST | `/itineraries/{id}/context/refresh` | fetch weather from the configured provider. 409 `provider_not_configured`, 422 `dates_required`, 502 `provider_error`; nothing is simulated |
| POST | `/itineraries/{id}/context/report` | `{type: closure, activity_id}`, `{type: delay, day_number, current_time_min, completed_activity_ids}`, `{type: spent, spent_minor}`; stored as `user_reported` |
| POST | `/itineraries/{id}/adapt` | detects issues from FRESH context and creates **pending** proposals (deduplicated); returns `issues`, `proposals`, `unresolved`, `stale_days`, `notes` |
| GET | `/itineraries/{id}/adaptations`, `/adaptations/{pid}` | proposal history |
| POST | `/adaptations/{pid}/approve` | applies the change as a new version (409 `stale_proposal` if the itinerary changed; the proposal becomes `superseded`) |
| POST | `/adaptations/{pid}/reject` | marks it rejected; the itinerary is untouched |

Issue types: `rain`, `heat` (outdoor activities only, from fresh provider forecasts), `closure` (admin-verified weekly hours with trip dates, or traveler-reported), `delay`, `over_budget` (traveler-reported). Alternatives are published attractions of the same destination, never verified-closed, ranked by category, relevance and proximity and chosen to minimise new schedule violations; a proposal's `preview` shows before/after and any remaining violations. Approval is required for every change.


## Hotels and bookings (Wave 3)
Public: `GET /hotels` (q, destination, min_stars, sort, page), `GET /hotels/{slug|id}`, `GET /hotels/{ref}/availability?check_in&check_out&guests&rooms`.
Traveler (auth, owner-scoped; other users get 404):
* `POST /bookings`: **requires `Idempotency-Key`**; same key + same body replays (200, header `Idempotent-Replayed: true`), same key + different body is 409. Creates `pending_payment` with a 15 min hold (`hold_expires_at`). 409 when sold out.
* `POST /bookings/{id}/pay` body `{payment_method}`: development simulator tokens `dev_card_ok`, `dev_card_declined` (402), `dev_card_error`. Responses carry `payment_note` and `simulated: true` on payments. Idempotent via header.
* `POST /bookings/{id}/cancel`: refund 100% when >= 2 days before check-in, 50% at 1 day, else 0 (see `refund_if_cancelled_now_minor`, `cancellation_policy`).
* `GET /bookings?status=`.
Admin (403 for travelers): `GET/POST /admin/hotels`, `PATCH/DELETE /admin/hotels/{id}`, `POST /admin/hotels/{id}/rooms`, `PATCH /admin/rooms/{id}`, `PUT /admin/rooms/{id}/inventory` (cannot go below booked), `GET /admin/bookings`, `POST /admin/bookings/{id}/cancel` (full refund), `POST /admin/bookings/{id}/retry-refund`, `GET /admin/analytics` (derived from the database; `notes` lists what is not measured).

## Notifications (auth, owner-scoped)
`GET /notifications?unread&page`, `GET /notifications/unread-count`, `POST /notifications/{id}/read`, `POST /notifications/read-all`.

## Assistant (auth)
`GET /assistant/capabilities`, `POST /assistant/chat {message, conversation_id?, language?, input_mode?}` -> `{reply, actions[], cards[], awaiting_confirmation, language, detected_language, interpreted_by}`, `GET/PATCH/DELETE /assistant/conversations[/{id}]`, `POST /assistant/voice/transcribe` (multipart `audio`, optional `language`), `POST /assistant/voice/synthesize {text, language}` (audio bytes). Voice errors: 503 `speech_not_configured`, 502 `speech_error`; credentials are never returned.
