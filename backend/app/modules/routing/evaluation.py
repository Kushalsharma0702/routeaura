"""Offline benchmark of route optimisation and context adaptation on SYNTHETIC data (seeded; no live data).

Part A, route optimisation: the same activity set per trip, three orderings judged by the same scheduler/validator
  original          : the plan as first built (top-scored activities in recommendation order, ~3 per day)
  nearest_neighbour : activities re-ordered per day with a greedy nearest-neighbour heuristic (days unchanged)
  ortools_locked    : OR-Tools, all activities locked (identical set; may reassign days/order)
  ortools_free      : OR-Tools, optional activities may be dropped (relevance vs. travel trade-off)
Part B, shortest paths: Dijkstra vs A* on random geometric graphs (parity and search effort).
Part C, context adaptation: latency and effect of the pure adaptation engine on synthetic forecasts.
"""

from __future__ import annotations

import csv
import json
import math
import random
import statistics
import time
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from app.integrations.routing.providers import EstimateRouting
from app.integrations.weather.base import DayForecast
from app.modules.context import engine as ce
from app.modules.itinerary import planner as pl
from app.modules.itinerary.evaluation import ItineraryEvalConfig, build, make_trip
from app.modules.routing import graph as g
from app.modules.routing import optimizer as op

LABEL = "SYNTHETIC experiment: generated trips and forecasts, not real users or live data. See docs/research/ROUTING_CONTEXT_EVALUATION.md."
METHODS = ["original", "nearest_neighbour", "ortools_locked", "ortools_free"]
EST = EstimateRouting()


@dataclass(frozen=True)
class RoutingEvalConfig:
    seed: int = 42
    n_trips: int = 60
    n_attractions: int = 14
    n_graphs: int = 20
    graph_nodes: int = 80
    n_context_cases: int = 200

    def to_dict(self) -> dict:
        return asdict(self)


def _mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def _ci(xs, seed, n_boot=1000):
    xs = [x for x in xs if x is not None]
    if len(xs) < 2:
        return None
    rng = random.Random(seed)
    means = sorted(sum(xs[rng.randrange(len(xs))] for _ in xs) / len(xs) for _ in range(n_boot))
    return [means[int(0.025 * n_boot)], means[int(0.975 * n_boot) - 1]]


def _opt_problem(cands: list[pl.Candidate], p: pl.PlanParams, locked: bool):
    pts = [p.start] + [(c.lat, c.lng) for c in cands]
    matrix = EST.matrix(pts)
    p.leg = op.leg_from_matrix(pts, matrix)
    acts = [
        op.OptActivity(
            id=c.id,
            name=c.name,
            lat=c.lat,
            lng=c.lng,
            duration_min=c.duration_min,
            cost_total_minor=None if c.cost_minor is None else c.cost_minor * p.travelers,
            score=c.score,
            locked=locked,
            candidate=c,
        )
        for c in cands
    ]
    return acts, matrix


def part_a(cfg: RoutingEvalConfig) -> dict:
    rng = random.Random(f"{cfg.seed}:routing-trips")
    icfg = ItineraryEvalConfig(seed=cfg.seed, n_attractions=cfg.n_attractions)
    rows: dict[str, list[dict]] = {m: [] for m in METHODS}
    statuses = {"ortools_locked": {}, "ortools_free": {}}
    for _ in range(cfg.n_trips):
        cands, p = make_trip(rng, icfg)
        original = build("simple_order", cands, p)  # list[DaySchedule]
        ids_by_day = [[s.candidate_id for s in d.slots] for d in original]
        chosen = [c for c in cands if any(c.id in d for d in ids_by_day)]
        if len(chosen) < 2:
            continue
        by_id = {c.id: c for c in chosen}
        pts = [p.start] + [(c.lat, c.lng) for c in chosen]
        matrix = EST.matrix(pts)
        p.leg = op.leg_from_matrix(pts, matrix)
        acts = {
            c.id: op.OptActivity(
                c.id,
                c.name,
                c.lat,
                c.lng,
                c.duration_min,
                None if c.cost_minor is None else c.cost_minor * p.travelers,
                c.score,
                True,
                c,
            )
            for c in chosen
        }

        def metrics(days, latency):
            ev = op.evaluate(days, acts, p)
            return {
                "distance_m": ev["distance_m"],
                "travel_min": ev["travel_min"],
                "violations": len(ev["violations"]),
                "has_violation": len(ev["violations"]) > 0,
                "over_budget": ev["budget"]["within_budget"] is False,
                "budget_deviation_pct": ev["budget"]["deviation_pct"],
                "n_activities": ev["n_activities"],
                "utility": ev["utility"],
                "latency_ms": latency,
            }

        t = time.perf_counter()
        rows["original"].append(metrics(ids_by_day, 0.0))
        nn_days = [[c.id for c in pl.order_nearest_neighbour([by_id[i] for i in ids], p.start)] for ids in ids_by_day]
        rows["nearest_neighbour"].append(metrics(nn_days, (time.perf_counter() - t) * 1000))
        for name, locked in (("ortools_locked", True), ("ortools_free", False)):
            oa = [
                op.OptActivity(
                    a.id, a.name, a.lat, a.lng, a.duration_min, a.cost_total_minor, a.score, locked, a.candidate
                )
                for a in acts.values()
            ]
            res = op.optimize(oa, p, matrix)
            statuses[name][res.status] = statuses[name].get(res.status, 0) + 1
            if res.status == "infeasible":
                continue  # no plan to evaluate; counted in `statuses`
            rows[name].append(metrics(res.days, res.solver_ms))
    keys = [
        "distance_m",
        "travel_min",
        "violations",
        "has_violation",
        "over_budget",
        "budget_deviation_pct",
        "n_activities",
        "utility",
        "latency_ms",
    ]
    summary = {
        m: {
            k: {
                "mean": _mean([float(r[k]) if r[k] is not None else None for r in rs]),
                "ci95": _ci([float(r[k]) if r[k] is not None else None for r in rs], cfg.seed),
            }
            for k in keys
        }
        | {"n_trips": len(rs)}
        for m, rs in rows.items()
    }
    return {"summary": summary, "solver_status_counts": statuses}


def part_a_paired(cfg: RoutingEvalConfig) -> dict:
    """Paired per-trip reductions (only trips where the method returned a plan)."""
    rng = random.Random(f"{cfg.seed}:routing-trips")
    icfg = ItineraryEvalConfig(seed=cfg.seed, n_attractions=cfg.n_attractions)
    out = {m: {"dist": [], "time": []} for m in ("nearest_neighbour", "ortools_locked", "ortools_free")}
    for _ in range(cfg.n_trips):
        cands, p = make_trip(rng, icfg)
        original = build("simple_order", cands, p)
        ids_by_day = [[s.candidate_id for s in d.slots] for d in original]
        chosen = [c for c in cands if any(c.id in d for d in ids_by_day)]
        if len(chosen) < 2:
            continue
        pts = [p.start] + [(c.lat, c.lng) for c in chosen]
        matrix = EST.matrix(pts)
        p.leg = op.leg_from_matrix(pts, matrix)
        by_id = {c.id: c for c in chosen}
        acts = {
            c.id: op.OptActivity(c.id, c.name, c.lat, c.lng, c.duration_min, None, c.score, True, c) for c in chosen
        }
        base = op.evaluate(ids_by_day, acts, p)
        if base["distance_m"] == 0 or base["travel_min"] == 0:
            continue

        def add(m, days, sub=None):
            ev = op.evaluate(days, acts, p)
            if sub is not None and ev["n_activities"] != base["n_activities"]:
                return  # only compare identical activity sets
            out[m]["dist"].append(100 * (base["distance_m"] - ev["distance_m"]) / base["distance_m"])
            out[m]["time"].append(100 * (base["travel_min"] - ev["travel_min"]) / base["travel_min"])

        add(
            "nearest_neighbour",
            [[c.id for c in pl.order_nearest_neighbour([by_id[i] for i in ids], p.start)] for ids in ids_by_day],
        )
        for name, locked in (("ortools_locked", True), ("ortools_free", False)):
            oa = [
                op.OptActivity(a.id, a.name, a.lat, a.lng, a.duration_min, None, a.score, locked, a.candidate)
                for a in acts.values()
            ]
            res = op.optimize(oa, p, matrix)
            if res.status != "infeasible":
                add(name, res.days, sub=True)
    return {
        m: {
            "n": len(v["dist"]),
            "distance_reduction_pct": {"mean": _mean(v["dist"]), "ci95": _ci(v["dist"], cfg.seed)},
            "travel_time_reduction_pct": {"mean": _mean(v["time"]), "ci95": _ci(v["time"], cfg.seed)},
        }
        for m, v in out.items()
    }


def part_b(cfg: RoutingEvalConfig) -> dict:
    rng = random.Random(f"{cfg.seed}:graphs")
    exp_d = exp_a = parity = pairs = 0
    t_d = t_a = 0.0
    for gi in range(cfg.n_graphs):
        coords = {i: (26.8 + rng.random() * 0.5, 75.6 + rng.random() * 0.5) for i in range(cfg.graph_nodes)}
        graph = g.knn_graph(coords, 4)
        h = g.haversine_heuristic(coords)
        for _ in range(10):
            a, b = rng.sample(sorted(coords), 2)
            try:
                t = time.perf_counter()
                rd = g.dijkstra(graph, a, b)
                t_d += time.perf_counter() - t
                t = time.perf_counter()
                ra = g.astar(graph, a, b, h)
                t_a += time.perf_counter() - t
            except g.NoPath:
                continue
            pairs += 1
            exp_d += rd.expanded
            exp_a += ra.expanded
            parity += math.isclose(rd.cost, ra.cost, rel_tol=1e-9)
    return {
        "query_pairs": pairs,
        "paths_with_equal_cost": parity,
        "mean_nodes_expanded_dijkstra": exp_d / pairs,
        "mean_nodes_expanded_astar": exp_a / pairs,
        "expansion_ratio_astar_over_dijkstra": exp_a / exp_d,
        "mean_ms_dijkstra": 1000 * t_d / pairs,
        "mean_ms_astar": 1000 * t_a / pairs,
        "note": "k-nearest-neighbour graphs over random points (not road networks); heuristic = great-circle distance (admissible: edges are x1.3).",
    }


def part_c(cfg: RoutingEvalConfig) -> dict:
    rng = random.Random(f"{cfg.seed}:context")
    icfg = ItineraryEvalConfig(seed=cfg.seed, n_attractions=cfg.n_attractions)
    now = datetime(2030, 1, 7, 12, 0, tzinfo=UTC)
    lat, issues_n, proposals_n, viol_before, bad_picked, bad_naive = [], 0, 0, 0, 0, 0
    for _ in range(cfg.n_context_cases):
        cands, p = make_trip(rng, icfg)
        p.start_date = date(2030, 1, 8)
        plan = build("validated_planner", cands, p)
        by_id = {c.id: c for c in cands}
        days = {d + 1: [_stop(by_id[s.candidate_id], rng) for s in sched.slots] for d, sched in enumerate(plan)}
        used = {s.attraction_id for ss in days.values() for s in ss}
        pool = [_stop(c, rng) for c in cands if c.id not in used]
        forecasts = {
            d: DayForecast(
                date(2030, 1, 7 + d),
                rng.choice([0.0, 1.0, 9.0, 20.0]),
                rng.choice([10, 40, 70, 95]),
                rng.uniform(15, 44),
                None,
                "synthetic",
                now - timedelta(minutes=rng.choice([5, 30, 100, 400])),
            )
            for d in days
        }
        t = time.perf_counter()
        found, stale, _ = ce.detect_weather(days, forecasts, now, ce.Thresholds())
        proposals = []
        for issue in found:
            old = next(s for s in days[issue.day] if s.id == issue.activity_id)
            alts = ce.rank_alternatives(old, pool, day=issue.day, start_date=p.start_date, indoor_only=True, limit=6)
            naive = (
                ce.simulate({d: [alts[0][0] if s.id == old.id else s for s in ss] for d, ss in days.items()}, p)
                if alts
                else None
            )
            picked = ce.pick_replacement(days, old, alts, p) if alts else None
            if picked:
                new = {d: [picked[0] if s.id == old.id else s for s in ss] for d, ss in days.items()}
                sim = ce.simulate(new, p)
                proposals.append(sim)
                bad_picked += bool(sim["violations"])
                bad_naive += bool(naive["violations"])
        lat.append((time.perf_counter() - t) * 1000)
        issues_n += len(found)
        proposals_n += len(proposals)
        before = ce.simulate(days, p)
        viol_before += bool(before["violations"])
    lat.sort()
    return {
        "cases": cfg.n_context_cases,
        "issues_detected": issues_n,
        "proposals_built": proposals_n,
        "issues_without_alternative": issues_n - proposals_n,
        "latency_ms": {
            "mean": statistics.fmean(lat),
            "p50": lat[len(lat) // 2],
            "p95": lat[int(len(lat) * 0.95) - 1],
            "max": lat[-1],
        },
        "original_plans_with_violations": viol_before,
        "proposals_with_violations_feasibility_aware_choice": bad_picked,
        "proposals_with_violations_if_top_ranked_alternative_used": bad_naive,
        "note": "Pure engine only: no database, no provider call. Forecasts older than 180 min are ignored by design.",
    }


def _stop(c: pl.Candidate, rng: random.Random) -> ce.Stop:
    return ce.Stop(
        id=c.id,
        attraction_id=c.id,
        name=c.name,
        lat=c.lat,
        lng=c.lng,
        category=f"c{hash(c.id) % 3}",
        is_outdoor=c.is_outdoor,
        duration_min=c.duration_min,
        cost_minor=c.cost_minor,
        score=c.score,
        locked=False,
        candidate=c,
    )


def run_experiment(cfg: RoutingEvalConfig) -> dict:
    return {
        "label": LABEL,
        "dataset": cfg.to_dict(),
        "route_optimization": part_a(cfg),
        "route_optimization_paired": part_a_paired(cfg),
        "shortest_paths": part_b(cfg),
        "context_adaptation": part_c(cfg),
        "limitations": [
            "Travel times are the great-circle estimate (x1.3 at 30 km/h), used both to optimise and to judge: this measures ordering quality, not real road times.",
            "OR-Tools default mode (greedy descent) is deterministic but not guaranteed optimal; no comparison to an exact solver beyond the small brute-force unit tests.",
            "Original plans are the naive 'simple_order' builder, a weak baseline; improvements over a stronger heuristic would be smaller.",
            "Context adaptation uses synthetic forecasts and measures the pure engine; database, provider and network latency are excluded.",
            "Outputs are deterministic given the seed except latency fields.",
        ],
    }


def run_seeds(seeds: list[int], base: RoutingEvalConfig) -> dict:
    runs = [run_experiment(RoutingEvalConfig(**{**base.to_dict(), "seed": s})) for s in seeds]
    return {"label": LABEL, "seeds": seeds, "runs": runs}


def write_outputs(result: dict, out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    jp, cp, mp = out_dir / "routing_results.json", out_dir / "routing_results.csv", out_dir / "routing_summary.md"
    jp.write_text(json.dumps(result, indent=2, sort_keys=True, default=float) + "\n")
    with cp.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["seed", "method", "metric", "mean", "ci95_low", "ci95_high"])
        for run in result["runs"]:
            for m, row in run["route_optimization"]["summary"].items():
                for k, v in row.items():
                    if isinstance(v, dict):
                        ci = v["ci95"] or [None, None]
                        w.writerow([run["dataset"]["seed"], m, k, v["mean"], ci[0], ci[1]])
            for m, row in run["route_optimization_paired"].items():
                for k in ("distance_reduction_pct", "travel_time_reduction_pct"):
                    ci = row[k]["ci95"] or [None, None]
                    w.writerow([run["dataset"]["seed"], m, "paired_" + k, row[k]["mean"], ci[0], ci[1]])
    runs = result["runs"]

    def avg(path):
        vals = [path(r) for r in runs]
        vals = [v for v in vals if v is not None]
        mu = sum(vals) / len(vals) if vals else None
        sd = math.sqrt(sum((v - mu) ** 2 for v in vals) / (len(vals) - 1)) if vals and len(vals) > 1 else None
        return mu, sd

    def f(mu_sd, d=2):
        mu, sd = mu_sd
        return "n/a" if mu is None else f"{mu:.{d}f}" + (f" ± {sd:.{d}f}" if sd is not None else "")

    L = [
        f"> **{LABEL}**",
        "",
        f"Seeds {result['seeds']} · {runs[0]['dataset']['n_trips']} trips/seed · {runs[0]['dataset']['n_attractions']} attractions/trip",
        "",
        "## A. Route optimisation (same activity sets; paired reductions vs the original plan, mean over seeds ± sd across seeds)",
        "",
        "| method | distance reduction % | travel-time reduction % | trips compared (seed 1) |",
        "|---|---|---|---|",
    ]
    for m in ("nearest_neighbour", "ortools_locked", "ortools_free"):
        L.append(
            f"| {m} | {f(avg(lambda r, m=m: r['route_optimization_paired'][m]['distance_reduction_pct']['mean']), 1)} | "
            f"{f(avg(lambda r, m=m: r['route_optimization_paired'][m]['travel_time_reduction_pct']['mean']), 1)} | {runs[0]['route_optimization_paired'][m]['n']} |"
        )
    L += [
        "",
        "Per-method constraint and budget metrics (mean over seeds ± sd; each method judged by the same validator):",
        "",
        "| method | violation rate | violations/trip | over-budget rate | budget dev. % | activities | utility (Σ score) | latency ms |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for m in METHODS:
        g_ = lambda k, m=m: avg(lambda r: r["route_optimization"]["summary"][m][k]["mean"])  # noqa: E731
        L.append(
            f"| {m} | {f(g_('has_violation'), 3)} | {f(g_('violations'), 3)} | {f(g_('over_budget'), 3)} | {f(g_('budget_deviation_pct'), 1)} | {f(g_('n_activities'), 2)} | {f(g_('utility'), 2)} | {f(g_('latency_ms'), 2)} |"
        )
    sc = {m: {} for m in ("ortools_locked", "ortools_free")}
    for r in runs:
        for m, d in r["route_optimization"]["solver_status_counts"].items():
            for k, v in d.items():
                sc[m][k] = sc[m].get(k, 0) + v
    L += [
        "",
        f"Solver outcomes summed over all seeds: {json.dumps(sc)}",
        "",
        "## B. Dijkstra vs A* (random k-NN geometric graphs, not road networks)",
        "",
        "| metric | mean over seeds |",
        "|---|---|",
    ]
    for k in (
        "query_pairs",
        "paths_with_equal_cost",
        "mean_nodes_expanded_dijkstra",
        "mean_nodes_expanded_astar",
        "expansion_ratio_astar_over_dijkstra",
        "mean_ms_dijkstra",
        "mean_ms_astar",
    ):
        L.append(f"| {k} | {f(avg(lambda r, k=k: r['shortest_paths'][k]), 3)} |")
    L += [
        "",
        "## C. Context adaptation (pure engine, synthetic forecasts)",
        "",
        "| metric | mean over seeds |",
        "|---|---|",
    ]
    for k in (
        "cases",
        "issues_detected",
        "proposals_built",
        "issues_without_alternative",
        "original_plans_with_violations",
        "proposals_with_violations_feasibility_aware_choice",
        "proposals_with_violations_if_top_ranked_alternative_used",
    ):
        L.append(f"| {k} | {f(avg(lambda r, k=k: r['context_adaptation'][k]), 1)} |")
    for k in ("mean", "p50", "p95", "max"):
        L.append(f"| latency {k} (ms) | {f(avg(lambda r, k=k: r['context_adaptation']['latency_ms'][k]), 3)} |")
    L += (
        ["", "## Limitations", ""]
        + [f"- {x}" for x in runs[0]["limitations"]]
        + ["", "## Parameters", "", "```json", json.dumps(runs[0]["dataset"], indent=2), "```", ""]
    )
    mp.write_text("\n".join(L))
    return [jp, cp, mp]
