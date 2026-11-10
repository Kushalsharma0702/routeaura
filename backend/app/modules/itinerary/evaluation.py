"""Offline benchmark of itinerary construction on SYNTHETIC trips (seeded; no real users or live data).

Methods (all judged by the SAME validator, `planner.schedule_day` + `planner.validate`):
* simple_order      : top-scored attractions, a fixed number per day, in recommendation order, no constraint checks
* nearest_neighbour : same selection, geographically ordered, still no constraint checks
* validated_planner : the app's planner (time/budget-aware selection, opening-hour-aware first-fit packing)

A violation is anything `validate` reports: day overrun, opening hours, per-day limit, budget.
"""

from __future__ import annotations

import csv
import json
import math
import random
import time
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path

from app.modules.itinerary import planner as pl

LABEL = "SYNTHETIC experiment: generated trips, not real users or live data. See docs/research/ITINERARY_EVALUATION.md."
METHODS = ["simple_order", "nearest_neighbour", "validated_planner"]


@dataclass(frozen=True)
class ItineraryEvalConfig:
    seed: int = 42
    n_trips: int = 300
    n_attractions: int = 14
    verified_hours_fraction: float = 0.5  # share of attractions with admin-verified opening hours
    unknown_cost_fraction: float = 0.4
    tight_budget_fraction: float = 0.3  # trips whose budget leaves little room for activities

    def to_dict(self) -> dict:
        return asdict(self)


def make_trip(rng: random.Random, cfg: ItineraryEvalConfig):
    centre = (26.9 + rng.uniform(-0.5, 0.5), 75.8 + rng.uniform(-0.5, 0.5))
    cands = []
    for i in range(cfg.n_attractions):
        hours = None
        if rng.random() < cfg.verified_hours_fraction:
            open_h = rng.choice([8, 9, 10, 11])
            close_h = open_h + rng.choice([4, 6, 8])
            hours = {d: [[f"{open_h:02d}:00", f"{min(close_h, 23):02d}:00"]] for d in pl.DAY_KEYS}
            for d in rng.sample(pl.DAY_KEYS, rng.choice([0, 0, 1])):
                hours[d] = []  # closed one weekday
        cands.append(
            pl.Candidate(
                id=f"a{i:02d}",
                name=f"Attraction {i:02d}",
                lat=centre[0] + rng.gauss(0, 0.04),
                lng=centre[1] + rng.gauss(0, 0.04),
                duration_min=rng.choice([45, 60, 90, 120, 180]),
                cost_minor=None
                if rng.random() < cfg.unknown_cost_fraction
                else rng.choice([0, 5000, 20000, 50000, 120000]),
                score=round(rng.random(), 3),
                opening_hours=hours,
                is_outdoor=rng.random() < 0.5,
            )
        )
    days = rng.randint(1, 4)
    travelers = rng.randint(1, 4)
    living = rng.choice([200000, 320000, 450000])
    base_living = living * days * travelers
    budget = int(base_living * (1.08 if rng.random() < cfg.tight_budget_fraction else rng.uniform(1.4, 2.5)))
    p = pl.PlanParams(
        days=days,
        start_date=date(2030, 1, 7) if rng.random() < 0.8 else None,
        travelers=travelers,
        budget_total_minor=budget,
        living_per_day_minor=living,
        start=centre,
    )
    return cands, p


def _sequential(ordered: list[pl.Candidate], p: pl.PlanParams) -> list[pl.DaySchedule]:
    per_day = max(1, min(p.max_per_day, math.ceil(len(ordered) / p.days)))
    chosen = ordered[: p.days * per_day]
    return [pl.schedule_day(d + 1, chosen[d * per_day : (d + 1) * per_day], p) for d in range(p.days)]


def build(method: str, cands: list[pl.Candidate], p: pl.PlanParams) -> list[pl.DaySchedule]:
    k = max(p.days * 3, 3)  # naive methods target ~3 attractions per day
    ranked = sorted(cands, key=lambda c: (-c.score, c.name))[:k]
    if method == "simple_order":
        return _sequential(ranked, p)
    if method == "nearest_neighbour":
        return _sequential(pl.order_nearest_neighbour(ranked, p.start), p)
    if method == "validated_planner":
        return pl.plan_deterministic(cands, p)[0]
    raise ValueError(method)


def measure(method: str, cands: list[pl.Candidate], p: pl.PlanParams) -> dict:
    t = time.perf_counter()
    schedules = build(method, cands, p)
    latency_ms = (time.perf_counter() - t) * 1000
    by_id = {c.id: c for c in cands}
    summary, viols = pl.validate(schedules, by_id, p)
    kinds = {k: sum(v.type == k for v in viols) for k in ("day_overrun", "opening_hours", "max_per_day", "budget")}
    slots = [s for d in schedules for s in d.slots]
    return {
        "violations": len(viols),
        "has_violation": bool(viols),
        **{f"v_{k}": n for k, n in kinds.items()},
        "n_activities": len(slots),
        "utility": sum(by_id[s.candidate_id].score for s in slots),
        "travel_min": sum(s.travel_min for s in slots),
        "budget_deviation_pct": summary["deviation_pct"],
        "over_budget": summary["within_budget"] is False,
        "latency_ms": latency_ms,
    }


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


def run_experiment(cfg: ItineraryEvalConfig, n_boot: int = 1000) -> dict:
    rng = random.Random(f"{cfg.seed}:trips")
    trips = [make_trip(rng, cfg) for _ in range(cfg.n_trips)]
    rows = {m: [measure(m, c, p) for c, p in trips] for m in METHODS}
    metrics = [
        "violations",
        "has_violation",
        "v_day_overrun",
        "v_opening_hours",
        "v_max_per_day",
        "v_budget",
        "n_activities",
        "utility",
        "travel_min",
        "budget_deviation_pct",
        "over_budget",
        "latency_ms",
    ]
    out = {}
    for m, rs in rows.items():
        out[m] = {
            k: {
                "mean": _mean([float(r[k]) if r[k] is not None else None for r in rs]),
                "ci95": _ci([float(r[k]) if r[k] is not None else None for r in rs], cfg.seed, n_boot),
            }
            for k in metrics
        }
    # paired differences vs simple_order
    paired = {}
    for m in ("nearest_neighbour", "validated_planner"):
        for k in ("has_violation", "violations", "utility", "n_activities", "over_budget"):
            d = [float(a[k]) - float(b[k]) for a, b in zip(rows[m], rows["simple_order"], strict=True)]
            paired[f"{m} - simple_order ({k})"] = {"mean": _mean(d), "ci95": _ci(d, cfg.seed, n_boot), "n": len(d)}
    return {
        "label": LABEL,
        "dataset": cfg.to_dict(),
        "n_bootstrap": n_boot,
        "methods": out,
        "paired_differences": paired,
        "limitations": [
            "Trips, attractions, hours and costs are randomly generated; real catalogues are smaller and less varied.",
            "Travel times are the planner's own estimates (great-circle x 1.3 / 30 km/h): the same model is used to build and to judge.",
            "The validator is the planner's own rule set, so zero violations for validated_planner measures consistency, not real-world feasibility.",
            "LLM-assisted planning is not benchmarked: it needs live credentials and is non-deterministic.",
        ],
    }


def run_seeds(seeds: list[int], base: ItineraryEvalConfig, n_boot: int = 1000) -> dict:
    runs = [run_experiment(ItineraryEvalConfig(**{**base.to_dict(), "seed": s}), n_boot) for s in seeds]
    agg = {}
    for m in METHODS:
        agg[m] = {}
        for k in runs[0]["methods"][m]:
            vals = [r["methods"][m][k]["mean"] for r in runs if r["methods"][m][k]["mean"] is not None]
            mu = sum(vals) / len(vals) if vals else None
            sd = math.sqrt(sum((v - mu) ** 2 for v in vals) / (len(vals) - 1)) if vals and len(vals) > 1 else None
            agg[m][k] = {"mean": mu, "sd_across_seeds": sd}
    return {"label": LABEL, "seeds": seeds, "aggregate_across_seeds": agg, "runs": runs}


def write_outputs(result: dict, out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    jp, cp, mp = out_dir / "itinerary_results.json", out_dir / "itinerary_results.csv", out_dir / "itinerary_summary.md"
    jp.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    with cp.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["seed", "method", "metric", "mean", "ci95_low", "ci95_high"])
        for run in result["runs"]:
            for m, row in run["methods"].items():
                for k, v in row.items():
                    ci = v["ci95"] or [None, None]
                    w.writerow([run["dataset"]["seed"], m, k, v["mean"], ci[0], ci[1]])
    run0 = result["runs"][0]
    cols = [
        ("has_violation", "trips with a violation"),
        ("violations", "violations/trip"),
        ("v_day_overrun", "day overruns"),
        ("v_opening_hours", "opening-hour"),
        ("v_budget", "budget"),
        ("over_budget", "over budget"),
        ("budget_deviation_pct", "mean budget dev. %"),
        ("n_activities", "activities"),
        ("utility", "utility (Σ score)"),
        ("travel_min", "travel min"),
        ("latency_ms", "latency ms"),
    ]

    def fmt(v: dict) -> str:
        if v["mean"] is None:
            return "n/a"
        sd = v["sd_across_seeds"]
        return f"{v['mean']:.3f}" + (f" ± {sd:.3f}" if sd is not None else "")

    lines = [
        f"> **{LABEL}**",
        "",
        f"Seeds {result['seeds']} · {run0['dataset']['n_trips']} trips/seed · {run0['dataset']['n_attractions']} attractions/trip",
        "",
        "Mean over seeds ± sd across seeds.",
        "",
        "| method | " + " | ".join(c[1] for c in cols) + " |",
        "|---|" + "---|" * len(cols),
    ]
    for m in METHODS:
        lines.append(f"| {m} | " + " | ".join(fmt(result["aggregate_across_seeds"][m][k]) for k, _ in cols) + " |")
    lines += [
        "",
        f"### Paired differences (seed {run0['dataset']['seed']}, 95% bootstrap CI)",
        "",
        "| comparison | mean | 95% CI | n |",
        "|---|---|---|---|",
    ]
    for name, d in run0["paired_differences"].items():
        lines.append(f"| {name} | {d['mean']:+.3f} | [{d['ci95'][0]:+.3f}, {d['ci95'][1]:+.3f}] | {d['n']} |")
    lines += (
        ["", "### Limitations", ""]
        + [f"- {x}" for x in run0["limitations"]]
        + ["", "### Parameters", "", "```json", json.dumps(run0["dataset"], indent=2), "```", ""]
    )
    mp.write_text("\n".join(lines))
    return [jp, cp, mp]
