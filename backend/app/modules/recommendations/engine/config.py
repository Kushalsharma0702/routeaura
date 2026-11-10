"""Scoring configuration and the documented heuristic constants of the recommendation engine.

Everything here is a *design decision*, not a learned parameter. They are exposed so experiments can
vary them, and the effective configuration of every run is stored in `recommendation_runs.config`.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Literal

FEATURES = ("interest", "budget", "duration", "climate", "season", "style")
STYLES = ("budget", "comfort", "luxury", "adventure", "relaxed")
CLIMATES = ("tropical", "temperate", "cold", "arid")

# Explicit user priorities scale the base weight of a feature ("ignore" removes it).
PRIORITY_MULTIPLIERS = {"ignore": 0.0, "low": 0.5, "normal": 1.0, "high": 2.0}

# Month sets for named seasons (northern-hemisphere / Indian-subcontinent convention). Seasons overlap
# on purpose (e.g. Feb is both winter and spring). A numeric `travel_month` is always preferred.
SEASON_MONTHS: dict[str, frozenset[int]] = {
    "winter": frozenset({11, 12, 1, 2}),
    "spring": frozenset({2, 3}),
    "summer": frozenset({4, 5, 6}),
    "monsoon": frozenset({7, 8, 9}),
    "autumn": frozenset({10, 11}),
}

# Judgement-based similarity between climate types (symmetric; identical = 1.0).
CLIMATE_SIMILARITY: dict[frozenset[str], float] = {
    frozenset({"tropical", "temperate"}): 0.4,
    frozenset({"tropical", "arid"}): 0.25,
    frozenset({"tropical", "cold"}): 0.0,
    frozenset({"temperate", "cold"}): 0.5,
    frozenset({"temperate", "arid"}): 0.4,
    frozenset({"cold", "arid"}): 0.15,
}

# Free-text interest -> category-name tokens. Interests are matched to catalogue categories by
# (lightly stemmed) token overlap with the category slug, plus these synonyms.
INTEREST_SYNONYMS: dict[str, tuple[str, ...]] = {
    "temple": ("culture",),
    "monastery": ("culture",),
    "spiritual": ("culture", "religion"),
    "festival": ("culture",),
    "heritage": ("history",),
    "fort": ("history",),
    "palace": ("history",),
    "museum": ("history",),
    "architecture": ("history",),
    "trek": ("adventure",),
    "trekking": ("adventure",),
    "hiking": ("adventure",),
    "mountain": ("adventure",),
    "rafting": ("adventure",),
    "sport": ("adventure",),
    "cuisine": ("food",),
    "street": ("food",),
    "shopping": ("market",),
    "bazaar": ("market",),
    "sea": ("beach",),
    "coast": ("beach",),
    "island": ("beach",),
    "sightseeing": ("scenic",),
    "view": ("scenic",),
    "viewpoint": ("scenic",),
    "photography": ("scenic",),
    "lake": ("nature",),
    "backwater": ("nature",),
    "forest": ("nature",),
    "animal": ("wildlife",),
    "safari": ("wildlife",),
}

# Category tokens that characterise travel styles.
STYLE_CATEGORY_TOKENS = {"adventure": {"adventure"}, "relaxed": {"beach", "nature", "wildlife", "scenic"}}


@dataclass(frozen=True)
class ScoringConfig:
    weights: dict[str, float] = field(
        default_factory=lambda: {
            "interest": 0.35,
            "budget": 0.20,
            "season": 0.15,
            "duration": 0.10,
            "climate": 0.10,
            "style": 0.10,
        }
    )
    # "lower_bound": a feature the user cares about but the catalogue cannot answer counts as 0, so
    #   missing data can never raise a score (confidence reports the coverage separately).
    # "renormalize": unknown features are dropped and the remaining weights rescaled (optimistic).
    missing_policy: Literal["lower_bound", "renormalize"] = "lower_bound"
    budget_overrun_tolerance: float = 0.5  # cost 50% over budget scores 0 on the budget feature
    budget_incompatible_multiplier: float = 0.6  # overall score multiplier when clearly over budget
    duration_slack_days: int = 1  # +-1 day counts as a perfect duration match
    climate_any_score: float = 0.75  # destination climate "any"
    attraction_budget_full_share: float = 0.25  # entry fee <= 25% of the daily budget: full score
    history_alpha: float = 0.7  # weight of stated interests vs interaction history
    avoid_beta: float = 0.3  # strength of the negative-history ("avoid") signal
    attraction_blend: float = 0.5  # share of the destination category vector from its attractions
    mmr_lambda: float = 0.7  # relevance vs diversity in MMR re-ranking
    model_version: str = "content-v1"

    def with_priorities(self, priorities: dict[str, str]) -> ScoringConfig:
        w = dict(self.weights)
        for feature, level in priorities.items():
            if feature in w:
                w[feature] = w[feature] * PRIORITY_MULTIPLIERS[level]
        return replace(self, weights=w)

    def to_dict(self) -> dict:
        return {
            "weights": dict(self.weights),
            "missing_policy": self.missing_policy,
            "budget_overrun_tolerance": self.budget_overrun_tolerance,
            "budget_incompatible_multiplier": self.budget_incompatible_multiplier,
            "duration_slack_days": self.duration_slack_days,
            "climate_any_score": self.climate_any_score,
            "attraction_budget_full_share": self.attraction_budget_full_share,
            "history_alpha": self.history_alpha,
            "avoid_beta": self.avoid_beta,
            "attraction_blend": self.attraction_blend,
            "mmr_lambda": self.mmr_lambda,
            "model_version": self.model_version,
        }


DEFAULT_CONFIG = ScoringConfig()
# Interest-similarity only: the "cosine similarity" strategy of the evaluation.
COSINE_CONFIG = ScoringConfig(
    weights={"interest": 1.0, "budget": 0, "season": 0, "duration": 0, "climate": 0, "style": 0},
    model_version="cosine-v1",
)
