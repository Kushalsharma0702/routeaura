"""Weighted content-based scoring with transparent handling of missing data.

score = sum_f( w_f * v_f ) / sum_f( w_f )     over the features the *user* specified (the applicable set)

* A feature the user did not specify is "not applicable": it takes no weight (weights renormalise).
* A feature the user specified but the catalogue cannot answer is "unknown". Under the default
  `lower_bound` policy it contributes 0 (never a free maximum) and `confidence` reports how much of the
  applicable weight was backed by data; under `renormalize` it is dropped from the average.
* A clearly over-budget item has its final score multiplied by `budget_incompatible_multiplier`.

The score ranks items against each other. It is NOT a probability that the user will like an item.
"""

from __future__ import annotations

from app.modules.recommendations.engine.config import (
    CLIMATE_SIMILARITY,
    FEATURES,
    ScoringConfig,
)
from app.modules.recommendations.engine.features import cosine
from app.modules.recommendations.engine.types import Component, Item, ScoredItem, UserProfile

LABELS = {
    "interest": "Interests",
    "budget": "Budget",
    "duration": "Trip length",
    "climate": "Climate",
    "season": "Travel season",
    "style": "Travel style",
}
MONTH = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def inr(minor: int) -> str:
    return f"₹{minor / 100:,.0f}"


def status_for(v: float | None) -> str:
    return "unknown" if v is None else "matched" if v >= 0.75 else "partial" if v >= 0.25 else "mismatch"


def months_range_text(months: frozenset[int]) -> str:
    """Compact month text: {10,11,12,1,2,3} -> 'Oct-Mar' (wraps over the new year); {1..12} -> 'year-round'."""
    if len(months) >= 12:
        return "year-round"
    runs: list[tuple[int, int]] = []
    for start in sorted(m for m in months if ((m - 2) % 12) + 1 not in months):
        end = start
        while (end % 12) + 1 in months:
            end = (end % 12) + 1
        runs.append((start, end))
    return ", ".join(MONTH[a - 1] if a == b else f"{MONTH[a - 1]}-{MONTH[b - 1]}" for a, b in runs)


# ---- feature compatibility functions: each returns (value in [0,1] | None, human-readable detail) ----
def interest_fit(p: UserProfile, item: Item) -> tuple[float | None, str]:
    if not item.category_vec:
        return None, "This place has no categories on record, so interest fit could not be assessed."
    v = cosine(p.interest_vec, item.category_vec)
    overlap = [s for s in item.category_vec if s in p.interest_vec]
    names = [item.category_names.get(s, s.replace("-", " ").title()) for s in overlap]
    hits = [i for i, slugs in p.matched_interests.items() if set(slugs) & set(item.category_vec)]
    if not overlap:
        return v, "None of its categories match your interests."
    via = f"your interest in {', '.join(hits)}" if hits else "places you saved, liked or viewed"
    lead = "Matches" if v >= 0.75 else "Partly matches"
    return v, f"{lead} {via} ({', '.join(names)})."


def budget_fit(p: UserProfile, item: Item, cfg: ScoringConfig) -> tuple[float | None, str]:
    b = p.budget_per_day_minor
    assert b is not None
    if item.cost_minor is None:
        what = "daily cost" if item.kind == "destination" else "entry fee"
        return None, f"No {what} estimate on record, so budget fit could not be assessed."
    c = item.cost_minor
    if item.kind == "destination":
        if c <= b:
            return 1.0, f"Estimated {inr(c)}/day is within your {inr(b)}/day budget."
        over = (c - b) / b if b > 0 else float("inf")
        v = max(0.0, 1.0 - over / cfg.budget_overrun_tolerance) if cfg.budget_overrun_tolerance > 0 else 0.0
        return (
            v,
            f"Estimated {inr(c)}/day is {over:.0%} above your {inr(b)}/day budget."
            if b > 0
            else f"Estimated {inr(c)}/day exceeds your zero budget.",
        )
    share = (c / b) if b > 0 else (0.0 if c == 0 else float("inf"))
    full = cfg.attraction_budget_full_share
    v = 1.0 if share <= full else max(0.0, 1.0 - (share - full) / (1.0 - full))
    return (
        v,
        f"Entry fee {inr(c)} is {share:.0%} of your {inr(b)} daily budget."
        if b > 0
        else f"Entry fee {inr(c)} against a zero budget.",
    )


def duration_fit(p: UserProfile, item: Item, cfg: ScoringConfig) -> tuple[float | None, str]:
    t = p.trip_days
    assert t is not None
    if item.duration_days is None:
        return None, "No recommended trip length on record, so duration fit could not be assessed."
    d = item.duration_days
    if abs(t - d) <= cfg.duration_slack_days:
        return 1.0, f"Recommended {d} days is close to your {t}-day trip."
    v = min(t, d) / max(t, d)
    return v, f"Recommended {d} days vs your {t}-day trip ({'longer' if d > t else 'shorter'} than you planned)."


def climate_fit(p: UserProfile, item: Item, cfg: ScoringConfig) -> tuple[float | None, str]:
    u = p.climate
    if item.climate is None:
        return None, "No climate on record, so climate fit could not be assessed."
    if item.climate == "any":
        return cfg.climate_any_score, "Climate varies / is not specific."
    if item.climate == u:
        return 1.0, f"{item.climate.title()} climate matches your preference."
    sim = CLIMATE_SIMILARITY.get(frozenset({u, item.climate}), 0.0)
    return sim, f"{item.climate.title()} climate differs from your preferred {u} climate."


def season_fit(p: UserProfile, item: Item) -> tuple[float | None, str]:
    wanted = p.season_months
    assert wanted is not None
    if item.season_months is None:
        return None, "No best-season information on record, so season fit could not be assessed."
    inside = wanted & item.season_months
    v = len(inside) / len(wanted)
    best = months_range_text(item.season_months)
    if v == 1.0:
        return v, f"{p.season_label.capitalize()} falls within its best season ({best})."
    if v == 0.0:
        return v, f"{p.season_label.capitalize()} is outside its best season ({best})."
    return v, f"{v:.0%} of {p.season_label} overlaps its best season ({best})."


def style_fit(p: UserProfile, item: Item) -> tuple[float | None, str]:
    v = item.styles.get(p.style or "")
    if v is None:
        return None, f"Not enough data to judge fit with a {p.style} travel style."
    return v, f"{'Good' if v >= 0.75 else 'Moderate' if v >= 0.25 else 'Weak'} fit for a {p.style} travel style."


def _compute(feature: str, p: UserProfile, item: Item, cfg: ScoringConfig) -> tuple[float | None, str]:
    return {
        "interest": lambda: interest_fit(p, item),
        "budget": lambda: budget_fit(p, item, cfg),
        "duration": lambda: duration_fit(p, item, cfg),
        "climate": lambda: climate_fit(p, item, cfg),
        "season": lambda: season_fit(p, item),
        "style": lambda: style_fit(p, item),
    }[feature]()


def has_usable_signal(profile: UserProfile, cfg: ScoringConfig, kind: str = "destination") -> bool:
    """True when at least one weighted feature applies to this user and item kind. Trip length does not
    apply to attractions. When False the caller must fall back to a non-personalised ranking."""
    return any(
        on and cfg.weights.get(feat, 0) > 0 and not (feat == "duration" and kind == "attraction")
        for feat, on in profile.applicable.items()
    )


def score_item(profile: UserProfile, item: Item, cfg: ScoringConfig) -> ScoredItem:
    applicable_flags = profile.applicable
    base: dict[str, float] = {}
    for f in FEATURES:
        if not applicable_flags[f] or cfg.weights.get(f, 0) <= 0:
            continue
        if f == "duration" and item.kind != "destination":
            continue  # trip length is a property of destinations only
        base[f] = cfg.weights[f]
    total_w = sum(base.values())

    values: dict[str, tuple[float | None, str]] = {f: _compute(f, profile, item, cfg) for f in base}
    known_w = sum(w for f, w in base.items() if values[f][0] is not None)
    denom = total_w if cfg.missing_policy == "lower_bound" else known_w

    components: list[Component] = []
    score = 0.0
    for f in FEATURES:
        if f not in base:
            why = (
                "Trip length only applies to destinations."
                if f == "duration" and item.kind != "destination"
                else "Not used: you didn't set this preference."
                if not applicable_flags[f]
                else "Not used: this feature has no weight."
            )
            components.append(Component(f, LABELS[f], None, 0.0, 0.0, "not_applicable", why))
            continue
        v, detail = values[f]
        w_norm = base[f] / total_w
        contrib = 0.0 if v is None or denom == 0 else base[f] * v / denom
        score += contrib
        components.append(Component(f, LABELS[f], v, w_norm, contrib, status_for(v), detail))

    multiplier = 1.0
    b = next((c for c in components if c.feature == "budget"), None)
    if b is not None and b.value == 0.0:
        multiplier = cfg.budget_incompatible_multiplier
        score *= multiplier

    confidence = known_w / total_w if total_w > 0 else 0.0
    applicable = [c for c in components if c.status != "not_applicable"]
    reasons = [
        c.detail for c in sorted((c for c in applicable if c.status == "matched"), key=lambda c: -c.contribution)
    ]
    cautions = [c.detail for c in applicable if c.status in ("partial", "mismatch")]
    if multiplier < 1.0:
        cautions.append(f"Clearly over budget, so its score was reduced by {1 - multiplier:.0%}.")
    missing = [c.detail for c in applicable if c.status == "unknown"]
    return ScoredItem(
        item=item,
        score=max(0.0, min(1.0, score)),
        confidence=confidence,
        components=components,
        multiplier=multiplier,
        reasons=reasons,
        cautions=cautions,
        missing=missing,
    )
