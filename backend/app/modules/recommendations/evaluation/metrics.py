"""Ranking and list-quality metrics. Pure functions; relevance is binary unless stated otherwise."""

from __future__ import annotations

import math
import random
from collections.abc import Sequence


def precision_at_k(recommended: Sequence[str], relevant: set[str], k: int) -> float:
    """|top-k ∩ relevant| / k  (a list shorter than k is penalised: the denominator is always k)."""
    if k <= 0:
        raise ValueError("k must be positive")
    return len(set(recommended[:k]) & relevant) / k


def recall_at_k(recommended: Sequence[str], relevant: set[str], k: int) -> float | None:
    """|top-k ∩ relevant| / |relevant|; None when the user has no relevant items (excluded from averages)."""
    if not relevant:
        return None
    return len(set(recommended[:k]) & relevant) / len(relevant)


def ndcg_at_k(recommended: Sequence[str], relevance: dict[str, float], k: int) -> float | None:
    """NDCG@k with gain = relevance / log2(rank + 1). None when there is no relevant item."""
    gains = [g for g in relevance.values() if g > 0]
    if not gains:
        return None
    dcg = sum(relevance.get(item, 0.0) / math.log2(i + 2) for i, item in enumerate(recommended[:k]))
    ideal = sorted(gains, reverse=True)[:k]
    idcg = sum(g / math.log2(i + 2) for i, g in enumerate(ideal))
    return dcg / idcg if idcg > 0 else None


def catalog_coverage(lists: Sequence[Sequence[str]], catalog_size: int) -> float:
    """Share of the catalogue that appears in at least one user's list."""
    if catalog_size <= 0:
        raise ValueError("catalog_size must be positive")
    return len({i for lst in lists for i in lst}) / catalog_size


def mean(values: Sequence[float | None]) -> float | None:
    vals = [v for v in values if v is not None]
    return sum(vals) / len(vals) if vals else None


def bootstrap_ci(
    values: Sequence[float | None], *, seed: int, n_boot: int = 1000, alpha: float = 0.05
) -> tuple[float, float] | None:
    """Percentile bootstrap confidence interval of the mean (seeded, so reproducible)."""
    vals = [v for v in values if v is not None]
    if len(vals) < 2:
        return None
    rng = random.Random(seed)
    n = len(vals)
    means = sorted(sum(vals[rng.randrange(n)] for _ in range(n)) / n for _ in range(n_boot))
    return means[int(alpha / 2 * n_boot)], means[int((1 - alpha / 2) * n_boot) - 1]


def paired_bootstrap_diff(a: Sequence[float | None], b: Sequence[float | None], *, seed: int, n_boot: int = 1000):
    """Mean of (a - b) over users where both are defined, with a seeded 95% bootstrap CI."""
    diffs = [x - y for x, y in zip(a, b, strict=True) if x is not None and y is not None]
    if len(diffs) < 2:
        return None
    ci = bootstrap_ci(diffs, seed=seed, n_boot=n_boot)
    return {"mean": sum(diffs) / len(diffs), "ci95": ci, "n": len(diffs)}
