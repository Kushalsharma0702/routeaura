"""Ranking strategies: weighted/cosine ordering, popularity baseline and MMR diversity re-ranking."""

from __future__ import annotations

from collections.abc import Iterable

from app.modules.recommendations.engine.config import ScoringConfig
from app.modules.recommendations.engine.features import cosine
from app.modules.recommendations.engine.scoring import score_item
from app.modules.recommendations.engine.types import Item, ScoredItem, UserProfile


def sort_key(s: ScoredItem):
    # deterministic: higher score, higher confidence, then name/id
    return (-round(s.score, 12), -round(s.confidence, 12), s.item.name.lower(), s.item.id)


def rank_content(profile: UserProfile, items: Iterable[Item], cfg: ScoringConfig) -> list[ScoredItem]:
    scored = sorted((score_item(profile, it, cfg) for it in items), key=sort_key)
    for i, s in enumerate(scored, 1):
        s.original_rank = s.rank = i
    return scored


def rank_popularity(items: Iterable[Item], popularity: dict[str, float]) -> list[ScoredItem]:
    """Non-personalised baseline: order by aggregate interaction weight (normalised to [0, 1])."""
    items = list(items)
    top = max((popularity.get(it.id, 0.0) for it in items), default=0.0)
    out: list[ScoredItem] = []
    for it in items:
        raw = popularity.get(it.id, 0.0)
        s = ScoredItem(item=it, score=(raw / top) if top > 0 else 0.0, confidence=0.0, components=[])
        if raw > 0:
            s.reasons.append("Popular with other travelers.")
        else:
            s.missing.append("No interaction data for this place yet.")
        out.append(s)
    out.sort(key=sort_key)
    for i, s in enumerate(out, 1):
        s.original_rank = s.rank = i
    return out


def mmr_rerank(ranked: list[ScoredItem], k: int, lam: float, pool_factor: int = 5) -> list[ScoredItem]:
    """Maximal Marginal Relevance (Carbonell & Goldstein, 1998).

    Greedily picks the item maximising  lam * relevance - (1 - lam) * max_cosine_to_already_selected.
    Only the top `pool_factor * k` candidates are considered, so relevance is preserved and cost stays bounded.
    lam = 1 reproduces the input order; smaller lam trades relevance for variety. Relevance is the
    item's score, which already lies in [0, 1].
    """
    if not 0.0 <= lam <= 1.0:
        raise ValueError("lambda must be within [0, 1]")
    pool = ranked[: max(k * pool_factor, k)]
    selected: list[ScoredItem] = []
    remaining = list(pool)
    while remaining and len(selected) < k:
        best, best_val = None, None
        for cand in remaining:
            sim = max((cosine(cand.item.vector, s.item.vector) for s in selected), default=0.0)
            val = lam * cand.score - (1 - lam) * sim
            key = (-val, sort_key(cand))
            if best is None or key < best_val:
                best, best_val = cand, key
        selected.append(best)  # type: ignore[arg-type]
        remaining.remove(best)  # type: ignore[arg-type]
    for i, s in enumerate(selected, 1):
        s.rank = i
    return selected


def intra_list_diversity(items: list[Item]) -> float:
    """Mean pairwise (1 - cosine) distance within a list; 0 for lists shorter than 2."""
    n = len(items)
    if n < 2:
        return 0.0
    total = sum(1.0 - cosine(items[i].vector, items[j].vector) for i in range(n) for j in range(i + 1, n))
    return total / (n * (n - 1) / 2)
