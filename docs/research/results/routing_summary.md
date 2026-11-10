> **SYNTHETIC experiment: generated trips and forecasts, not real users or live data. See docs/research/ROUTING_CONTEXT_EVALUATION.md.**

Seeds [42, 43, 44, 45, 46] · 60 trips/seed · 14 attractions/trip

## A. Route optimisation (same activity sets; paired reductions vs the original plan, mean over seeds ± sd across seeds)

| method | distance reduction % | travel-time reduction % | trips compared (seed 1) |
|---|---|---|---|
| nearest_neighbour | 16.4 ± 0.7 | 16.4 ± 0.8 | 60 |
| ortools_locked | 34.3 ± 2.6 | 34.3 ± 2.6 | 60 |
| ortools_free | 35.6 ± 2.0 | 35.5 ± 2.0 | 50 |

Per-method constraint and budget metrics (mean over seeds ± sd; each method judged by the same validator):

| method | violation rate | violations/trip | over-budget rate | budget dev. % | activities | utility (Σ score) | latency ms |
|---|---|---|---|---|---|---|---|
| original | 0.727 ± 0.092 | 1.410 ± 0.242 | 0.303 ± 0.062 | -16.5 ± 4.0 | 7.40 ± 0.47 | 4.99 ± 0.29 | 0.00 ± 0.00 |
| nearest_neighbour | 0.690 ± 0.072 | 1.293 ± 0.177 | 0.303 ± 0.062 | -16.5 ± 4.0 | 7.40 ± 0.47 | 4.99 ± 0.29 | 0.03 ± 0.00 |
| ortools_locked | 0.421 ± 0.052 | 0.565 ± 0.123 | 0.301 ± 0.062 | -16.6 ± 4.2 | 7.41 ± 0.46 | 5.00 ± 0.28 | 79.61 ± 34.39 |
| ortools_free | 0.037 ± 0.025 | 0.040 ± 0.028 | 0.000 ± 0.000 | -24.1 ± 2.5 | 5.84 ± 0.21 | 4.06 ± 0.16 | 63.08 ± 14.36 |

Solver outcomes summed over all seeds: {"ortools_locked": {"optimized": 268, "relaxed": 31, "infeasible": 1}, "ortools_free": {"optimized": 300}}

## B. Dijkstra vs A* (random k-NN geometric graphs, not road networks)

| metric | mean over seeds |
|---|---|
| query_pairs | 193.000 ± 1.581 |
| paths_with_equal_cost | 193.000 ± 1.581 |
| mean_nodes_expanded_dijkstra | 40.824 ± 0.698 |
| mean_nodes_expanded_astar | 20.542 ± 0.901 |
| expansion_ratio_astar_over_dijkstra | 0.503 ± 0.017 |
| mean_ms_dijkstra | 0.026 ± 0.000 |
| mean_ms_astar | 0.029 ± 0.001 |

## C. Context adaptation (pure engine, synthetic forecasts)

| metric | mean over seeds |
|---|---|
| cases | 200.0 ± 0.0 |
| issues_detected | 495.6 ± 34.4 |
| proposals_built | 365.2 ± 26.1 |
| issues_without_alternative | 130.4 ± 27.1 |
| original_plans_with_violations | 0.0 ± 0.0 |
| proposals_with_violations_feasibility_aware_choice | 154.2 ± 31.2 |
| proposals_with_violations_if_top_ranked_alternative_used | 218.6 ± 27.8 |
| latency mean (ms) | 0.117 ± 0.009 |
| latency p50 (ms) | 0.092 ± 0.008 |
| latency p95 (ms) | 0.341 ± 0.035 |
| latency max (ms) | 0.589 ± 0.079 |

## Limitations

- Travel times are the great-circle estimate (x1.3 at 30 km/h), used both to optimise and to judge: this measures ordering quality, not real road times.
- OR-Tools default mode (greedy descent) is deterministic but not guaranteed optimal; no comparison to an exact solver beyond the small brute-force unit tests.
- Original plans are the naive 'simple_order' builder, a weak baseline; improvements over a stronger heuristic would be smaller.
- Context adaptation uses synthetic forecasts and measures the pure engine; database, provider and network latency are excluded.
- Outputs are deterministic given the seed except latency fields.

## Parameters

```json
{
  "seed": 42,
  "n_trips": 60,
  "n_attractions": 14,
  "n_graphs": 20,
  "graph_nodes": 80,
  "n_context_cases": 200
}
```
