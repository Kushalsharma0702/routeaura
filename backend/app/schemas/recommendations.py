import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.schemas.catalog import AttractionOut, DestinationOut
from app.schemas.user import Climate

Feature = Literal["interest", "budget", "duration", "climate", "season", "style"]
Priority = Literal["ignore", "low", "normal", "high"]
Strategy = Literal["weighted", "cosine", "popularity"]
Style = Literal["budget", "comfort", "luxury", "adventure", "relaxed"]
Kind = Literal["destination", "attraction"]
InteractionType = Literal["view", "click", "save", "unsave", "like", "dislike", "reaction_clear", "dismiss", "restore"]
Source = Literal["browse", "detail", "recommendation", "saved"]
Rating = Literal["relevant", "not_relevant"]
FeedbackReason = Literal[
    "not_my_interest", "too_expensive", "wrong_season", "wrong_climate", "already_visited", "other"
]


class PreferenceOverrides(BaseModel):
    """Per-request preferences. A field that is *sent* (even as null) replaces the saved value; a field
    that is not sent falls back to the user's saved preferences."""

    budget_per_day_minor: int | None = Field(default=None, ge=0, le=10**9)
    trip_duration_days: int | None = Field(default=None, ge=1, le=60)
    interests: list[str] | None = Field(default=None, max_length=20)
    preferred_climate: str | None = None
    preferred_season: str | None = Field(default=None, max_length=20)
    travel_month: int | None = Field(default=None, ge=1, le=12)
    travel_style: Style | None = None

    @field_validator("preferred_climate")
    @classmethod
    def _climate(cls, v: str | None) -> str | None:
        if v is not None and v not in Climate:
            raise ValueError(f"preferred_climate must be one of {Climate}")
        return v

    @field_validator("interests")
    @classmethod
    def _interests(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return v
        if any(len(i) > 40 for i in v):
            raise ValueError("Interest too long")
        return sorted({i.strip().lower() for i in v if i.strip()})


class RecommendationFilters(BaseModel):
    category: str | None = Field(default=None, max_length=60)
    country: str | None = Field(default=None, max_length=80)
    climate: str | None = None
    max_cost_minor: int | None = Field(default=None, ge=0)
    destination_id: uuid.UUID | None = None
    outdoor: bool | None = None


class RecommendationRequest(BaseModel):
    overrides: PreferenceOverrides = Field(default_factory=PreferenceOverrides)
    priorities: dict[Feature, Priority] = Field(default_factory=dict)
    filters: RecommendationFilters = Field(default_factory=RecommendationFilters)
    strategy: Strategy = "weighted"
    diversify: bool = True
    diversity_lambda: float | None = Field(default=None, ge=0.0, le=1.0)
    include_dismissed: bool = False
    page: int = Field(default=1, ge=1, le=100)
    page_size: int = Field(default=10, ge=1, le=50)

    @model_validator(mode="after")
    def _not_all_ignored(self):
        if self.priorities and all(
            self.priorities.get(f) == "ignore" for f in ("interest", "budget", "duration", "climate", "season", "style")
        ):
            raise ValueError("At least one feature must not be ignored")
        return self


class ComponentOut(BaseModel):
    feature: str
    label: str
    value: float | None
    weight: float
    contribution: float
    status: Literal["matched", "partial", "mismatch", "unknown", "not_applicable"]
    detail: str


class RecommendationItemOut(BaseModel):
    recommendation_item_id: uuid.UUID
    kind: Kind
    rank: int
    original_rank: int
    score: float  # relevance score (0-1) used for ranking; NOT a probability of satisfaction
    confidence: float  # share of the applicable criteria that could be evaluated with catalogue data
    destination: DestinationOut | None = None
    attraction: AttractionOut | None = None
    components: list[ComponentOut]
    reasons: list[str]
    cautions: list[str]
    missing: list[str]
    saved: bool = False
    liked: bool = False
    disliked: bool = False
    feedback: Rating | None = None


class RecommendationResponse(BaseModel):
    run_id: uuid.UUID
    kind: Kind
    strategy: str  # weighted | cosine | popularity | popularity_fallback
    model_version: str
    diversified: bool
    diversity_lambda: float | None
    total_candidates: int
    page: int
    page_size: int
    items: list[RecommendationItemOut]
    applied_preferences: dict
    effective_weights: dict[str, float]
    notes: list[str]
    disclaimer: str = (
        "Scores rank places against your stated preferences and the catalogue data. "
        "They are not probabilities of satisfaction."
    )


class InteractionIn(BaseModel):
    item_type: Kind
    item_id: uuid.UUID
    interaction_type: InteractionType
    source: Source = "browse"
    recommendation_item_id: uuid.UUID | None = None


class ItemStateOut(BaseModel):
    saved: bool
    liked: bool
    disliked: bool
    dismissed: bool


class InteractionOut(BaseModel):
    recorded: bool  # false when the event was an idempotent no-op (e.g. saving something already saved)
    state: ItemStateOut


class SavedItemOut(BaseModel):
    item_type: Kind
    destination: DestinationOut | None = None
    attraction: AttractionOut | None = None


class FeedbackIn(BaseModel):
    recommendation_item_id: uuid.UUID
    rating: Rating
    reasons: list[FeedbackReason] = Field(default_factory=list, max_length=6)
    comment: str | None = Field(default=None, max_length=500)


class FeedbackOut(BaseModel):
    recommendation_item_id: uuid.UUID
    rating: Rating
    reasons: list[str]
    comment: str | None
    updated_at: datetime


class RunSummary(BaseModel):
    run_id: uuid.UUID
    kind: Kind
    strategy: str
    model_version: str
    created_at: datetime
    total_candidates: int
    returned_count: int
    page: int
    page_size: int
    diversified: bool
    preferences: dict
    top_items: list[str]


class RunItemOut(BaseModel):
    recommendation_item_id: uuid.UUID
    kind: Kind
    item_id: uuid.UUID
    name: str | None
    rank: int
    original_rank: int
    score: float
    confidence: float
    explanation: dict
    feedback: Rating | None = None


class RunDetail(RunSummary):
    config: dict
    filters: dict
    priorities: dict
    items: list[RunItemOut]
