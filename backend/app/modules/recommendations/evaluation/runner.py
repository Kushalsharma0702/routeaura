"""Reproducible offline experiment: popularity vs weighted content-based vs cosine vs diversity-aware
re-ranking, on a seeded SYNTHETIC world. Every number is computed here; nothing is hard-coded."""

from __future__ import annotations

import csv
import json
import math
import random
import time
from pathlib import Path

from app.modules.recommendations.engine.config import COSINE_CONFIG, DEFAULT_CONFIG, ScoringConfig
from app.modules.recommendations.engine.features import build_destination_items, build_profile
from app.modules.recommendations.engine.ranking import intra_list_diversity, mmr_rerank, rank_content, rank_popularity
from app.modules.recommendations.engine.scoring import has_usable_signal
from app.modules.recommendations.engine.types import HistoryItem
from app.modules.recommendations.evaluation import metrics as M
from app.modules.recommendations.evaluation.synthetic import (
    SyntheticConfig,
    make_world,
    observed_catalogue,
    relevant_items,
    sample_interactions,
    stated_preferences,
)

METHODS = ["random", "popularity", "weighted", "weighted_renormalize", "cosine", "weighted_mmr"]
SCENARIOS = {
    "cold_start_stated": "Cold start: users state (noisy, partial) preferences and have NO interaction history",
    "warm_history": "Warm: as above plus 5 simulated saves per user used as interaction history",
    "no_signal": "No signal: users state nothing and have no history (content methods must fall back to popularity)",
}
LABEL = "SYNTHETIC experiment: generated data, not real users. See docs/research/RECOMMENDATION_EVALUATION.md."
RENORMALIZE = ScoringConfig(missing_policy="renormalize", model_version="content-renormalize")


def _rng(seed: int, *parts: str) -> random.Random:
    return random.Random(f"{seed}:" + ":".join(parts))  # str seeds are hashed with SHA-512: stable across runs


def run_experiment(cfg: SyntheticConfig, *, k: int = 10, mmr_lambda: float = 0.7, n_boot: int = 1000) -> dict:
    started = time.perf_counter()
    world = make_world(cfg)
    cats, records = observed_catalogue(_rng(cfg.seed, "observe"), world.items, cfg)
    items, _ = build_destination_items(records, DEFAULT_CONFIG, cats)
    by_id = {it.id: it for it in items}

    # popularity is learned from a disjoint training population
    counts: dict[str, float] = {t.id: 0.0 for t in world.items}
    trained_items = [t for t in world.items if t.id not in world.new_item_ids]  # new items are unseen in training
    for u in world.train_users:
        for it in sample_interactions(
            _rng(cfg.seed, "train", u.id), u, trained_items, cfg.train_interactions_per_user, cfg.softmax_temperature
        ):
            counts[it.id] += 1.0
    cold_items = {i for i, c in counts.items() if c == 0}

    per_user: dict[str, dict[str, dict[str, list]]] = {
        s: {m: {"p": [], "r": [], "ndcg": [], "ild": [], "cold_r": [], "lists": []} for m in METHODS} for s in SCENARIOS
    }
    for user in world.test_users:
        relevance = relevant_items(_rng(cfg.seed, "rel", user.id), user, world.items, cfg)
        relevant = set(relevance)
        relevant_cold = relevant & cold_items
        warm_rng = _rng(cfg.seed, "warm", user.id)
        warm_items = sample_interactions(
            warm_rng, user, world.items, cfg.warm_interactions_per_user, cfg.softmax_temperature
        )
        history = [HistoryItem(1.0, by_id[w.id].category_vec) for w in warm_items if by_id[w.id].category_vec]
        stated = stated_preferences(_rng(cfg.seed, "stated", user.id), user, cfg)

        for scenario in SCENARIOS:
            sp = (
                stated if scenario != "no_signal" else stated_preferences(random.Random(0), user, cfg, any_stated=False)
            )
            hist = history if scenario == "warm_history" else []

            def profile(c: ScoringConfig, sp=sp, hist=hist):
                return build_profile(
                    budget_per_day_minor=sp["budget_per_day_minor"],
                    trip_days=sp["trip_days"],
                    interests=sp["interests"],
                    climate=sp["climate"],
                    season=None,
                    travel_month=sp["travel_month"],
                    style=None,
                    categories=cats,
                    history=hist,
                    config=c,
                )

            pop = rank_popularity(items, counts)

            def content(c: ScoringConfig, pop=pop):
                p = profile(c)
                return rank_content(p, items, c) if has_usable_signal(p, c) else pop

            rankings = {
                "random": None,
                "popularity": pop,
                "weighted": content(DEFAULT_CONFIG),
                "weighted_renormalize": content(RENORMALIZE),
                "cosine": content(COSINE_CONFIG),
            }
            rankings["weighted_mmr"] = (
                mmr_rerank(list(rankings["weighted"]), k, mmr_lambda) if rankings["weighted"] is not pop else pop
            )
            for method in METHODS:
                if method == "random":
                    ids = [i.id for i in items]
                    _rng(cfg.seed, "random", user.id, scenario).shuffle(ids)
                else:
                    ids = [s.item.id for s in rankings[method]]
                top = ids[:k]
                d = per_user[scenario][method]
                d["p"].append(M.precision_at_k(top, relevant, k))
                d["r"].append(M.recall_at_k(top, relevant, k))
                d["ndcg"].append(M.ndcg_at_k(top, relevance, k))
                d["ild"].append(intra_list_diversity([by_id[i] for i in top]))
                d["cold_r"].append(M.recall_at_k(top, relevant_cold, k) if relevant_cold else None)
                d["lists"].append(top)

    metric_keys = {
        f"precision@{k}": "p",
        f"recall@{k}": "r",
        f"ndcg@{k}": "ndcg",
        "intra_list_diversity": "ild",
        f"cold_item_recall@{k}": "cold_r",
    }
    results: dict = {}
    for scenario, desc in SCENARIOS.items():
        methods_out = {}
        for method in METHODS:
            d = per_user[scenario][method]
            row = {}
            for name, key in metric_keys.items():
                ci = M.bootstrap_ci(d[key], seed=cfg.seed, n_boot=n_boot)
                row[name] = {"mean": M.mean(d[key]), "ci95": list(ci) if ci else None}
            row["catalog_coverage"] = M.catalog_coverage(d["lists"], len(items))
            methods_out[method] = row
        pu = per_user[scenario]
        results[scenario] = {
            "description": desc,
            "n_users": len(world.test_users),
            "methods": methods_out,
            "paired_differences": {
                f"weighted - popularity (precision@{k})": M.paired_bootstrap_diff(
                    pu["weighted"]["p"], pu["popularity"]["p"], seed=cfg.seed, n_boot=n_boot
                ),
                f"weighted - popularity (ndcg@{k})": M.paired_bootstrap_diff(
                    pu["weighted"]["ndcg"], pu["popularity"]["ndcg"], seed=cfg.seed, n_boot=n_boot
                ),
                f"cosine - popularity (ndcg@{k})": M.paired_bootstrap_diff(
                    pu["cosine"]["ndcg"], pu["popularity"]["ndcg"], seed=cfg.seed, n_boot=n_boot
                ),
                f"weighted - cosine (ndcg@{k})": M.paired_bootstrap_diff(
                    pu["weighted"]["ndcg"], pu["cosine"]["ndcg"], seed=cfg.seed, n_boot=n_boot
                ),
                f"weighted_mmr - weighted (precision@{k})": M.paired_bootstrap_diff(
                    pu["weighted_mmr"]["p"], pu["weighted"]["p"], seed=cfg.seed, n_boot=n_boot
                ),
                "weighted_mmr - weighted (intra_list_diversity)": M.paired_bootstrap_diff(
                    pu["weighted_mmr"]["ild"], pu["weighted"]["ild"], seed=cfg.seed, n_boot=n_boot
                ),
                f"weighted - weighted_renormalize (ndcg@{k})": M.paired_bootstrap_diff(
                    pu["weighted"]["ndcg"], pu["weighted_renormalize"]["ndcg"], seed=cfg.seed, n_boot=n_boot
                ),
            },
        }
    observed_missing = {
        f: sum(getattr(r, f) is None for r in records) / len(records)
        for f in ("cost_per_day_minor", "duration_days", "season_start", "climate")
    }
    observed_missing["categories"] = sum(not r.categories for r in records) / len(records)
    return {
        "label": LABEL,
        "dataset": cfg.to_dict(),
        "k": k,
        "mmr_lambda": mmr_lambda,
        "n_bootstrap": n_boot,
        "scoring_config": DEFAULT_CONFIG.to_dict(),
        "catalogue": {
            "n_items": len(items),
            "n_cold_items_in_training": len(cold_items),
            "observed_missing_rates": observed_missing,
            "n_relevant_per_user": max(5, round(cfg.relevant_fraction * len(items))),
        },
        "scenarios": results,
        "runtime_seconds": round(time.perf_counter() - started, 2),
    }


def run_seeds(seeds: list[int], base: SyntheticConfig, **kw) -> dict:
    runs = [run_experiment(SyntheticConfig(**{**base.to_dict(), "seed": s}), **kw) for s in seeds]
    k = runs[0]["k"]
    agg: dict = {}
    for scenario in SCENARIOS:
        agg[scenario] = {}
        for method in METHODS:
            row = {}
            for metric in (
                f"precision@{k}",
                f"recall@{k}",
                f"ndcg@{k}",
                "intra_list_diversity",
                f"cold_item_recall@{k}",
            ):
                vals = [r["scenarios"][scenario]["methods"][method][metric]["mean"] for r in runs]
                vals = [v for v in vals if v is not None]
                m = sum(vals) / len(vals) if vals else None
                sd = math.sqrt(sum((v - m) ** 2 for v in vals) / (len(vals) - 1)) if vals and len(vals) > 1 else None
                row[metric] = {"mean": m, "sd_across_seeds": sd}
            cov = [r["scenarios"][scenario]["methods"][method]["catalog_coverage"] for r in runs]
            row["catalog_coverage"] = {"mean": sum(cov) / len(cov), "sd_across_seeds": None}
            agg[scenario][method] = row
    return {"label": LABEL, "seeds": seeds, "aggregate_across_seeds": agg, "runs": runs}


# ------------------------------------------------------------------ output
def write_outputs(result: dict, out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path, csv_path, md_path = out_dir / "results.json", out_dir / "results.csv", out_dir / "summary.md"
    json_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    with csv_path.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["seed", "scenario", "method", "metric", "mean", "ci95_low", "ci95_high"])
        for run in result["runs"]:
            for scenario, sc in run["scenarios"].items():
                for method, row in sc["methods"].items():
                    for metric, v in row.items():
                        if isinstance(v, dict):
                            ci = v["ci95"] or [None, None]
                            w.writerow([run["dataset"]["seed"], scenario, method, metric, v["mean"], ci[0], ci[1]])
                        else:
                            w.writerow([run["dataset"]["seed"], scenario, method, metric, v, None, None])
    md_path.write_text(render_markdown(result))
    return [json_path, csv_path, md_path]


def render_markdown(result: dict) -> str:
    run0 = result["runs"][0]
    k = run0["k"]

    def fmt(v: dict) -> str:
        if v["mean"] is None:
            return "n/a"
        sd = v.get("sd_across_seeds")
        return f"{v['mean']:.3f}" + (f" ± {sd:.3f}" if sd is not None else "")

    lines = [
        f"> **{LABEL}**",
        "",
        f"Seeds: {result['seeds']} · users/seed: {run0['dataset']['n_test_users']} · items: {run0['dataset']['n_items']} · K = {k} · MMR λ = {run0['mmr_lambda']}",
        "",
        "Values are the mean over seeds ± the standard deviation across seeds (each seed's value is itself a mean over users).",
        "",
    ]
    cols = [
        f"precision@{k}",
        f"recall@{k}",
        f"ndcg@{k}",
        "intra_list_diversity",
        "catalog_coverage",
        f"cold_item_recall@{k}",
    ]
    for scenario, desc in SCENARIOS.items():
        lines += [
            f"### {scenario}",
            f"_{desc}_",
            "",
            "| method | " + " | ".join(cols) + " |",
            "|---|" + "---|" * len(cols),
        ]
        for method in METHODS:
            row = result["aggregate_across_seeds"][scenario][method]
            lines.append(f"| {method} | " + " | ".join(fmt(row[c]) for c in cols) + " |")
        lines.append("")
    lines += [
        "### Paired differences (per-user, seed " + str(run0["dataset"]["seed"]) + ", 95% bootstrap CI)",
        "",
        "| scenario | comparison | mean difference | 95% CI | n users |",
        "|---|---|---|---|---|",
    ]
    for scenario, sc in run0["scenarios"].items():
        for name, d in sc["paired_differences"].items():
            if d:
                lines.append(
                    f"| {scenario} | {name} | {d['mean']:+.4f} | [{d['ci95'][0]:+.4f}, {d['ci95'][1]:+.4f}] | {d['n']} |"
                )
    lines += [
        "",
        "### Run parameters",
        "",
        "```json",
        json.dumps(
            {"dataset": run0["dataset"], "catalogue": run0["catalogue"], "scoring_config": run0["scoring_config"]},
            indent=2,
            sort_keys=True,
        ),
        "```",
        "",
    ]
    return "\n".join(lines)
