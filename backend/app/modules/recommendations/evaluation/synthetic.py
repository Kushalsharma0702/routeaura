"""Seeded SYNTHETIC world for offline evaluation. Nothing here is real user data.

Design goal: the ground truth must not be a copy of the scoring model. Therefore
* users have *latent* tastes; the engine only sees noisy, partially missing *stated* preferences;
* items have *true* attributes; the engine only sees a version with randomly missing fields;
* ground-truth utility uses different functional forms (logistic budget fit, soft season fit, exponential
  duration fit) plus an item-popularity effect and Gaussian noise.
It still shares the same *families* of signals (categories, budget, season, climate, duration), so absolute
numbers measure robustness to noise and missing data in a world where the signals matter - not real-world
quality. See docs/research/RECOMMENDATION_EVALUATION.md.
"""

from __future__ import annotations

import math
import random
from dataclasses import asdict, dataclass

CATEGORY_WORDS = ["history", "beach", "adventure", "nature", "culture", "food", "scenic", "wellness"]
CLIMATES = ["tropical", "temperate", "cold", "arid"]


@dataclass(frozen=True)
class SyntheticConfig:
    seed: int = 42
    n_items: int = 120
    n_test_users: int = 300
    n_train_users: int = 400
    train_interactions_per_user: int = 15
    warm_interactions_per_user: int = 5
    relevant_fraction: float = 0.10  # top-10% utility items count as relevant
    catalogue_missing_rate: float = 0.15  # each of cost/duration/season/climate hidden with this probability
    category_missing_rate: float = 0.05
    stated_rate: float = 0.75  # probability a user states each optional preference
    interest_error_rate: float = 0.15  # a stated interest is wrong with this probability
    softmax_temperature: float = 0.10  # sharpness of simulated interaction sampling
    new_item_fraction: float = 0.20  # items added AFTER the training period: zero interactions (new-item cold start)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class TrueItem:
    id: str
    categories: list[int]
    cost: int  # minor units / day
    days: int
    season_start: int
    season_end: int
    climate: str
    pop: float  # latent popularity in (0, 1]


@dataclass
class TrueUser:
    id: str
    affinity: list[float]  # latent category affinity (sums to 1)
    budget: int
    climate: str
    month: int
    days: int


@dataclass
class World:
    config: SyntheticConfig
    items: list[TrueItem]
    test_users: list[TrueUser]
    train_users: list[TrueUser]
    new_item_ids: frozenset[str] = frozenset()  # items with no training interactions


def _in_season(month: int, start: int, end: int) -> bool:
    return start <= month <= end if start <= end else (month >= start or month <= end)


def utility(u: TrueUser, it: TrueItem) -> float:
    """Hidden ground-truth utility (no noise term; noise is added when relevance labels are drawn)."""
    item_vec = [1.0 if c in it.categories else 0.0 for c in range(len(CATEGORY_WORDS))]
    dot = sum(a * b for a, b in zip(u.affinity, item_vec, strict=True))
    na = math.sqrt(sum(a * a for a in u.affinity))
    nb = math.sqrt(sum(b * b for b in item_vec))
    cat = dot / (na * nb) if na and nb else 0.0
    budget = 1.0 / (1.0 + math.exp(8.0 * (it.cost / u.budget - 1.05)))
    season = 1.0 if _in_season(u.month, it.season_start, it.season_end) else 0.2
    climate = 1.0 if u.climate == it.climate else 0.3
    duration = math.exp(-abs(u.days - it.days) / 3.0)
    return 0.45 * cat + 0.15 * budget + 0.12 * season + 0.08 * climate + 0.08 * duration + 0.07 * it.pop


def _dirichlet(rng: random.Random, k: int, alpha: float) -> list[float]:
    g = [rng.gammavariate(alpha, 1.0) for _ in range(k)]
    s = sum(g) or 1.0
    return [x / s for x in g]


def make_user(rng: random.Random, uid: str) -> TrueUser:
    return TrueUser(
        id=uid,
        affinity=_dirichlet(rng, len(CATEGORY_WORDS), 0.3),
        budget=int(math.exp(rng.gauss(math.log(3500), 0.35)) * 100),
        climate=rng.choice(CLIMATES),
        month=rng.randint(1, 12),
        days=rng.randint(3, 9),
    )


def make_world(cfg: SyntheticConfig) -> World:
    rng = random.Random(cfg.seed)
    order = list(range(cfg.n_items))
    rng.shuffle(order)
    items = []
    for i in range(cfg.n_items):
        n_cat = rng.choices([1, 2, 3], weights=[0.4, 0.4, 0.2])[0]
        start = rng.randint(1, 12)
        length = rng.randint(3, 8)
        items.append(
            TrueItem(
                id=f"item-{i:04d}",
                categories=sorted(rng.sample(range(len(CATEGORY_WORDS)), n_cat)),
                cost=int(math.exp(rng.gauss(math.log(3500), 0.4)) * 100),
                days=rng.randint(2, 10),
                season_start=start,
                season_end=((start + length - 2) % 12) + 1,
                climate=rng.choice(CLIMATES),
                pop=1.0 / (order[i] + 1) ** 0.8,
            )
        )
    new_ids = frozenset(it.id for it in rng.sample(items, round(cfg.new_item_fraction * len(items))))
    top = max(it.pop for it in items)
    for it in items:
        it.pop /= top
    test = [make_user(rng, f"test-{i:04d}") for i in range(cfg.n_test_users)]
    train = [make_user(rng, f"train-{i:04d}") for i in range(cfg.n_train_users)]
    return World(cfg, items, test, train, new_ids)


def sample_interactions(
    rng: random.Random, user: TrueUser, items: list[TrueItem], n: int, temperature: float
) -> list[TrueItem]:
    """Sample n distinct items with probability proportional to exp(utility / T)."""
    weights = [math.exp(utility(user, it) / temperature) for it in items]
    chosen: list[TrueItem] = []
    pool = list(range(len(items)))
    for _ in range(min(n, len(items))):
        idx = rng.choices(pool, weights=[weights[i] for i in pool])[0]
        chosen.append(items[idx])
        pool.remove(idx)
    return chosen


def relevant_items(rng: random.Random, user: TrueUser, items: list[TrueItem], cfg: SyntheticConfig) -> dict[str, float]:
    """Ground-truth relevance: the top fraction of items by noisy utility (binary gains of 1.0)."""
    scored = sorted(((utility(user, it) + rng.gauss(0, 0.07), it.id) for it in items), reverse=True)
    n = max(5, round(cfg.relevant_fraction * len(items)))
    return {item_id: 1.0 for _, item_id in scored[:n]}


def observed_catalogue(rng: random.Random, items: list[TrueItem], cfg: SyntheticConfig):
    """What the engine is allowed to see: true attributes with random fields masked out."""
    from app.modules.recommendations.engine.types import Category, DestinationRecord

    cats = [Category(w, w.title()) for w in CATEGORY_WORDS]
    hide = lambda: rng.random() < cfg.catalogue_missing_rate  # noqa: E731
    records = []
    for it in items:
        season_hidden = hide()
        records.append(
            DestinationRecord(
                id=it.id,
                name=it.id,
                categories=[] if rng.random() < cfg.category_missing_rate else [cats[c] for c in it.categories],
                cost_per_day_minor=None if hide() else it.cost,
                duration_days=None if hide() else it.days,
                season_start=None if season_hidden else it.season_start,
                season_end=None if season_hidden else it.season_end,
                climate=None if hide() else it.climate,
            )
        )
    return cats, records


def stated_preferences(rng: random.Random, user: TrueUser, cfg: SyntheticConfig, *, any_stated: bool = True) -> dict:
    """Noisy, partially missing preferences a user would state. With any_stated=False nothing is stated."""
    if not any_stated:
        return {"interests": [], "budget_per_day_minor": None, "climate": None, "travel_month": None, "trip_days": None}
    ranked = sorted(range(len(CATEGORY_WORDS)), key=lambda c: -user.affinity[c])
    interests = []
    if rng.random() < 0.9:  # almost everyone states interests
        for c in ranked[:2]:
            interests.append(
                CATEGORY_WORDS[c] if rng.random() > cfg.interest_error_rate else rng.choice(CATEGORY_WORDS)
            )
    month = user.month if rng.random() < 0.9 else ((user.month + rng.choice([-2, -1, 1, 2]) - 1) % 12) + 1
    return {
        "interests": sorted(set(interests)),
        "budget_per_day_minor": int(user.budget * math.exp(rng.gauss(0, 0.25)))
        if rng.random() < cfg.stated_rate
        else None,
        "climate": (user.climate if rng.random() < 0.85 else rng.choice(CLIMATES)) if rng.random() < 0.5 else None,
        "travel_month": month if rng.random() < 0.5 else None,
        "trip_days": max(1, user.days + rng.choice([-1, 0, 0, 1])) if rng.random() < 0.5 else None,
    }
