# Itinerary Construction Evaluation (SYNTHETIC)

> **Seeded synthetic trips only: no real users, no live opening hours, no live routing, no LLM calls. Do not quote these as real-world results.**

Reproduce (the planner balances activities across days since the packing change; results below are from that code): `cd backend && uv run python -m app.scripts.evaluate_itineraries --seeds 42 43 44 45 46 --out ../docs/research/results` (about 9 s). Raw outputs: `results/itinerary_results.json`, `.csv`, `itinerary_summary.md`.

## Method
Each synthetic trip has 14 candidate attractions (random coordinates around a centre, visit lengths 45-180 min, costs partly unknown, ~half with verified opening hours incl. a closed weekday), 1-4 days, 1-4 travelers, a living-cost estimate, and a budget (30% of trips are tight: 8% above the living cost). Three builders are judged by **the same validator** (`planner.schedule_day` + `planner.validate`): `simple_order` (top scores, ~3 per day, no constraint checks), `nearest_neighbour` (same selection, geographically ordered), and `validated_planner` (the app's planner: time and budget-aware selection, opening-hour-aware first-fit packing). Metrics: trips with any violation, violations per trip by type, budget deviation, activities scheduled, relevance utility (sum of scores), estimated travel minutes, latency.

## Results
Seeds [42, 43, 44, 45, 46] · 300 trips/seed · 14 attractions/trip

Mean over seeds ± sd across seeds.

| method | trips with a violation | violations/trip | day overruns | opening-hour | budget | over budget | mean budget dev. % | activities | utility (Σ score) | travel min | latency ms |
|---|---|---|---|---|---|---|---|---|---|---|---|
| simple_order | 0.705 ± 0.021 | 1.364 ± 0.091 | 0.260 ± 0.020 | 0.826 ± 0.076 | 0.278 ± 0.009 | 0.278 ± 0.009 | -18.659 ± 0.601 | 7.460 ± 0.248 | 4.981 ± 0.102 | 130.892 ± 4.058 | 0.009 ± 0.000 |
| nearest_neighbour | 0.670 ± 0.024 | 1.247 ± 0.040 | 0.212 ± 0.016 | 0.757 ± 0.021 | 0.278 ± 0.009 | 0.278 ± 0.009 | -18.659 ± 0.601 | 7.460 ± 0.248 | 4.981 ± 0.102 | 91.597 ± 2.427 | 0.024 ± 0.001 |
| validated_planner | 0.000 ± 0.000 | 0.000 ± 0.000 | 0.000 ± 0.000 | 0.000 ± 0.000 | 0.000 ± 0.000 | 0.000 ± 0.000 | -23.386 ± 0.597 | 8.265 ± 0.249 | 4.830 ± 0.093 | 100.552 ± 2.867 | 0.078 ± 0.002 |

### Paired differences (seed 42, 95% bootstrap CI)

| comparison | mean | 95% CI | n |
|---|---|---|---|
| nearest_neighbour - simple_order (has_violation) | -0.070 | [-0.113, -0.027] | 300 |
| nearest_neighbour - simple_order (violations) | -0.147 | [-0.253, -0.043] | 300 |
| nearest_neighbour - simple_order (utility) | +0.000 | [+0.000, +0.000] | 300 |
| nearest_neighbour - simple_order (n_activities) | +0.000 | [+0.000, +0.000] | 300 |
| nearest_neighbour - simple_order (over_budget) | +0.000 | [+0.000, +0.000] | 300 |
| validated_planner - simple_order (has_violation) | -0.720 | [-0.767, -0.667] | 300 |
| validated_planner - simple_order (violations) | -1.357 | [-1.513, -1.210] | 300 |
| validated_planner - simple_order (utility) | -0.165 | [-0.269, -0.060] | 300 |
| validated_planner - simple_order (n_activities) | +0.753 | [+0.570, +0.910] | 300 |
| validated_planner - simple_order (over_budget) | -0.270 | [-0.320, -0.220] | 300 |

### Limitations

- Trips, attractions, hours and costs are randomly generated; real catalogues are smaller and less varied.
- Travel times are the planner's own estimates (great-circle x 1.3 / 30 km/h): the same model is used to build and to judge.
- The validator is the planner's own rule set, so zero violations for validated_planner measures consistency, not real-world feasibility.
- LLM-assisted planning is not benchmarked: it needs live credentials and is non-deterministic.

### Parameters

```json
{
  "seed": 42,
  "n_trips": 300,
  "n_attractions": 14,
  "verified_hours_fraction": 0.5,
  "unknown_cost_fraction": 0.4,
  "tight_budget_fraction": 0.3
}
```

## Reading the results honestly
* `validated_planner` has **0 violations by construction**: the validator is the planner's own rule set. This shows internal consistency, not real-world feasibility (real hours, traffic and closures are not modelled).
* It also schedules **more** activities than the naive builders (they cap at ~3/day regardless of fit) but with slightly **lower total relevance score**, because it prefers what actually fits over the top-scored items.
* Geographic ordering (`nearest_neighbour`) cuts estimated travel time versus `simple_order` without changing what is selected. Travel times are the planner's own estimates (great-circle x 1.3 / 30 km/h), used both to build and to judge.
* Latency is a fraction of a millisecond per plan; it excludes ranking, the database and any LLM call.
* **Not evaluated**: LLM-assisted planning (needs credentials, non-deterministic). Its structured-output failures and fallback are covered by unit tests, not by a benchmark.
