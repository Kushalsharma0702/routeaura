"""Plain data classes shared by the engine. No database or framework imports: the engine must stay
independently testable and usable by the evaluation module on synthetic catalogues."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

Kind = Literal["destination", "attraction"]


@dataclass(frozen=True)
class Category:
    slug: str
    name: str


@dataclass
class DestinationRecord:
    id: str
    name: str
    country: str = ""
    categories: list[Category] = field(default_factory=list)
    cost_per_day_minor: int | None = None
    duration_days: int | None = None
    season_start: int | None = None
    season_end: int | None = None
    climate: str | None = None
    attraction_categories: dict[str, int] = field(default_factory=dict)  # slug -> published attractions
    outdoor_share: float | None = None


@dataclass
class AttractionRecord:
    id: str
    name: str
    destination_id: str
    category: Category
    cost_minor: int | None = None
    minutes: int | None = None
    is_outdoor: bool | None = None
    climate: str | None = None  # inherited from the destination
    season_start: int | None = None  # inherited from the destination
    season_end: int | None = None


@dataclass
class Item:
    """Feature-engineered recommendable item."""

    id: str
    kind: Kind
    name: str
    category_vec: dict[str, float]  # slug -> weight, L1-normalised; empty = unknown
    category_names: dict[str, str]
    cost_minor: int | None
    cost_norm: float | None  # min-max over the catalogue, None if unknown
    duration_days: int | None
    season_months: frozenset[int] | None
    climate: str | None
    styles: dict[str, float | None]
    vector: dict[str, float]  # similarity space used by MMR / diversity
    meta: dict = field(default_factory=dict)


@dataclass
class UserProfile:
    budget_per_day_minor: int | None = None
    trip_days: int | None = None
    interest_vec: dict[str, float] = field(default_factory=dict)  # final, after history blending
    stated_interests: list[str] = field(default_factory=list)
    matched_interests: dict[str, list[str]] = field(default_factory=dict)  # interest -> category slugs
    unmatched_interests: list[str] = field(default_factory=list)
    climate: str | None = None
    season_months: frozenset[int] | None = None
    season_label: str | None = None
    style: str | None = None
    has_history: bool = False
    notes: list[str] = field(default_factory=list)

    @property
    def applicable(self) -> dict[str, bool]:
        return {
            "interest": bool(self.interest_vec),
            "budget": self.budget_per_day_minor is not None,
            "duration": self.trip_days is not None,
            "climate": self.climate is not None,
            "season": self.season_months is not None,
            "style": self.style is not None,
        }


@dataclass
class HistoryItem:
    """Aggregated, already time-decayed signed evidence about one item the user interacted with."""

    weight: float
    category_vec: dict[str, float]


@dataclass
class Component:
    feature: str
    label: str
    value: float | None
    weight: float  # normalised over the features applicable to this user
    contribution: float  # weight * value (0 when unknown)
    status: Literal["matched", "partial", "mismatch", "unknown", "not_applicable"]
    detail: str

    def to_dict(self) -> dict:
        return {
            "feature": self.feature,
            "label": self.label,
            "value": None if self.value is None else round(self.value, 4),
            "weight": round(self.weight, 4),
            "contribution": round(self.contribution, 4),
            "status": self.status,
            "detail": self.detail,
        }


@dataclass
class ScoredItem:
    item: Item
    score: float  # relevance score in [0, 1]; NOT a probability
    confidence: float  # share of the applicable weight backed by known data
    components: list[Component]
    multiplier: float = 1.0
    reasons: list[str] = field(default_factory=list)
    cautions: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    original_rank: int | None = None
    rank: int | None = None
