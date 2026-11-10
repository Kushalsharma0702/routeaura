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
