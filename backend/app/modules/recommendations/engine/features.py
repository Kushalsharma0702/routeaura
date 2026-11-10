"""Feature engineering: encoding, normalisation, missing-value handling and profile construction."""

from __future__ import annotations

import math
import re
from bisect import bisect_left, bisect_right

from app.modules.recommendations.engine.config import (
    CLIMATES,
    INTEREST_SYNONYMS,
    SEASON_MONTHS,
    STYLE_CATEGORY_TOKENS,
    STYLES,
    ScoringConfig,
)
from app.modules.recommendations.engine.types import (
    AttractionRecord,
    Category,
    DestinationRecord,
    HistoryItem,
    Item,
    UserProfile,
)

Vec = dict[str, float]
MONTH_NAMES = [
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
]


# ------------------------------------------------------------------ vector helpers
def l1_normalize(v: Vec) -> Vec:
    total = sum(abs(x) for x in v.values())
    return {k: x / total for k, x in v.items() if x != 0} if total > 0 else {}


def cosine(a: Vec, b: Vec) -> float:
    """Cosine similarity of sparse vectors; 0.0 when either vector is empty."""
    if not a or not b:
        return 0.0
    dot = sum(x * b.get(k, 0.0) for k, x in a.items())
    na = math.sqrt(sum(x * x for x in a.values()))
    nb = math.sqrt(sum(x * x for x in b.values()))
    return max(0.0, min(1.0, dot / (na * nb))) if na and nb else 0.0


def season_months(start: int | None, end: int | None) -> frozenset[int] | None:
    """Months of a season given inclusive start/end months; wraps over the new year (Oct-Mar). None = unknown."""
    if start is None or end is None:
        return None
    if start <= end:
        return frozenset(range(start, end + 1))
    return frozenset(list(range(start, 13)) + list(range(1, end + 1)))


# ------------------------------------------------------------------ catalogue statistics
class CatalogStats:
    """Catalogue-level numbers used to normalise costs (min-max and percentile rank)."""

    def __init__(self, costs: list[int | None]):
        known = sorted(c for c in costs if c is not None)
        self.sorted_costs = known
        self.min = known[0] if known else None
        self.max = known[-1] if known else None

    def minmax(self, cost: int | None) -> float | None:
        if cost is None or self.min is None or self.max is None:
            return None
        return 0.5 if self.max == self.min else (cost - self.min) / (self.max - self.min)

    def percentile(self, cost: int | None) -> float | None:
        """Mid-rank percentile in [0, 1]; needs at least 2 known costs to mean anything."""
        n = len(self.sorted_costs)
        if cost is None or n < 2:
            return None
        lo, hi = bisect_left(self.sorted_costs, cost), bisect_right(self.sorted_costs, cost)
        return (lo + (hi - lo) / 2) / n


# ------------------------------------------------------------------ interests -> categories
def _stem(token: str) -> str:
    """Minimal plural stemmer: beaches->beach, cities->city, markets->market (keeps 'class', 'history')."""
    if len(token) > 4 and token.endswith("ies"):
        return token[:-3] + "y"
    if len(token) > 4 and token.endswith("es") and token[:-2].endswith(("ch", "sh", "x", "z", "ss")):
        return token[:-2]
    if len(token) > 3 and token.endswith("s") and not token.endswith("ss"):
        return token[:-1]
    return token


def tokens(text: str) -> set[str]:
    return {_stem(t) for t in re.split(r"[^a-z0-9]+", text.lower()) if t}


def match_interests(interests: list[str], categories: list[Category]) -> tuple[dict[str, list[str]], list[str]]:
    """Map free-text interests to category slugs. Returns (matched: interest -> slugs, unmatched interests)."""
    cat_tokens = {c.slug: tokens(c.slug) | tokens(c.name) for c in categories}
    matched: dict[str, list[str]] = {}
    unmatched: list[str] = []
    for interest in interests:
        its = tokens(interest)
        expanded = set(its)
        for t in its:
            expanded.update(_stem(s) for s in INTEREST_SYNONYMS.get(t, ()))
        slugs = sorted(slug for slug, ct in cat_tokens.items() if expanded & ct)
        if slugs:
            matched[interest] = slugs
        else:
            unmatched.append(interest)
    return matched, unmatched


# ------------------------------------------------------------------ items
def _style_affinities(
    comp: Vec, cost_pct: float | None, outdoor_share: float | None, is_outdoor: bool | None = None
) -> dict[str, float | None]:
    def share(tok_set: set[str]) -> float | None:
        if not comp:
            return None
        return sum(w for slug, w in comp.items() if tokens(slug) & tok_set)

    adv = share(STYLE_CATEGORY_TOKENS["adventure"])
    relaxed = share(STYLE_CATEGORY_TOKENS["relaxed"])
    if adv is not None:
        extra = (
            outdoor_share
            if outdoor_share is not None
            else (1.0 if is_outdoor else 0.0 if is_outdoor is not None else None)
        )
        adv = min(1.0, adv + 0.5 * extra) if extra is not None else adv
    p = cost_pct
    return {
        "budget": None if p is None else 1.0 - p,
        "luxury": None if p is None else p,
        "comfort": None if p is None else 1.0 - 2.0 * abs(p - 0.5),
        "adventure": adv,
        "relaxed": relaxed,
    }


def _similarity_vector(cat_vec: Vec, climate: str | None, cost_norm: float | None) -> Vec:
    v = dict(cat_vec)
    if climate:
        v[f"climate:{climate}"] = 0.5
    if cost_norm is not None:
        v["cost"] = 0.3 * cost_norm
    return v


def build_destination_items(
    records: list[DestinationRecord], config: ScoringConfig, vocabulary: list[Category] | None = None
) -> tuple[list[Item], CatalogStats]:
    stats = CatalogStats([r.cost_per_day_minor for r in records])
    vocab_names = {c.slug: c.name for c in vocabulary or []}
    items: list[Item] = []
    for r in records:
        direct = l1_normalize({c.slug: 1.0 for c in r.categories})
        hist = l1_normalize({k: float(v) for k, v in r.attraction_categories.items()})
        if direct and hist:
            a = config.attraction_blend
            comp = l1_normalize({k: (1 - a) * direct.get(k, 0.0) + a * hist.get(k, 0.0) for k in {*direct, *hist}})
        else:
            comp = direct or hist
        names = {**vocab_names, **{c.slug: c.name for c in r.categories}}
        cost_norm = stats.minmax(r.cost_per_day_minor)
        items.append(
            Item(
                id=r.id,
                kind="destination",
                name=r.name,
                category_vec=comp,
                category_names=names,
                cost_minor=r.cost_per_day_minor,
                cost_norm=cost_norm,
                duration_days=r.duration_days,
                season_months=season_months(r.season_start, r.season_end),
                climate=r.climate,
                styles=_style_affinities(comp, stats.percentile(r.cost_per_day_minor), r.outdoor_share),
                vector=_similarity_vector(comp, r.climate, cost_norm),
                meta={"country": r.country},
            )
        )
    return items, stats


def build_attraction_items(records: list[AttractionRecord]) -> tuple[list[Item], CatalogStats]:
    stats = CatalogStats([r.cost_minor for r in records])
    items: list[Item] = []
    for r in records:
        comp = {r.category.slug: 1.0}
        cost_norm = stats.minmax(r.cost_minor)
        items.append(
            Item(
                id=r.id,
                kind="attraction",
                name=r.name,
                category_vec=comp,
                category_names={r.category.slug: r.category.name},
                cost_minor=r.cost_minor,
                cost_norm=cost_norm,
                duration_days=None,
                season_months=season_months(r.season_start, r.season_end),
                climate=r.climate,
                styles=_style_affinities(comp, stats.percentile(r.cost_minor), None, r.is_outdoor),
                vector=_similarity_vector(comp, r.climate, cost_norm),
                meta={"destination_id": r.destination_id, "minutes": r.minutes, "is_outdoor": r.is_outdoor},
            )
        )
    return items, stats


# ------------------------------------------------------------------ user profile
def build_profile(
    *,
    budget_per_day_minor: int | None,
    trip_days: int | None,
    interests: list[str],
    climate: str | None,
    season: str | None,
    travel_month: int | None,
    style: str | None,
    categories: list[Category],
    history: list[HistoryItem],
    config: ScoringConfig,
) -> UserProfile:
    p = UserProfile(budget_per_day_minor=budget_per_day_minor, trip_days=trip_days)

    # climate / style: "any" or unrecognised values mean "no usable preference"
    if climate and climate != "any":
        if climate in CLIMATES:
            p.climate = climate
        else:
            p.notes.append(f"Climate preference '{climate}' is not recognised and was ignored.")
    if style:
        if style in STYLES:
            p.style = style
        else:
            p.notes.append(f"Travel style '{style}' is not recognised and was ignored.")

    # season: an explicit month beats a named season
    if travel_month is not None:
        p.season_months, p.season_label = frozenset({travel_month}), MONTH_NAMES[travel_month - 1]
    elif season and season != "any":
        months = SEASON_MONTHS.get(season)
        if months:
            p.season_months, p.season_label = months, season
        else:
            p.notes.append(f"Season '{season}' is not recognised and was ignored.")

    # interests: stated vector blended with (positive) history, minus a small "avoid" signal
    clean = [i.strip().lower() for i in interests if i and i.strip()]
    p.stated_interests = clean
    p.matched_interests, p.unmatched_interests = match_interests(clean, categories)
    if p.unmatched_interests:
        p.notes.append("Interests not found in the catalogue categories: " + ", ".join(p.unmatched_interests) + ".")
    stated = l1_normalize({s: 1.0 for slugs in p.matched_interests.values() for s in slugs})

    raw: Vec = {}
    for h in history:
        for slug, w in h.category_vec.items():
            raw[slug] = raw.get(slug, 0.0) + h.weight * w
    pos = l1_normalize({k: v for k, v in raw.items() if v > 0})
    neg = l1_normalize({k: -v for k, v in raw.items() if v < 0})
    p.has_history = bool(pos or neg)

    if stated and pos:
        a = config.history_alpha
        blend = {k: a * stated.get(k, 0.0) + (1 - a) * pos.get(k, 0.0) for k in {*stated, *pos}}
    else:
        blend = dict(stated or pos)
    if blend and neg:
        blend = {k: v - config.avoid_beta * neg.get(k, 0.0) for k, v in blend.items()}
    p.interest_vec = l1_normalize({k: v for k, v in blend.items() if v > 0})
    if pos and not stated:
        p.notes.append("Interests were inferred from your saved, liked and viewed items.")
    return p
