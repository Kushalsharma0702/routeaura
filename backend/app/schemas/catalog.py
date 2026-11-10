import re
import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.user import Climate

Lat = Annotated[float, Field(ge=-90, le=90, allow_inf_nan=False)]
Lng = Annotated[float, Field(ge=-180, le=180, allow_inf_nan=False)]
Source = Literal["admin", "seed", "provider"]
DAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
_HHMM = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
_URL = re.compile(r"^https?://[^\s]+$")


def _images(v: list[str]) -> list[str]:
    if len(v) > 12:
        raise ValueError("At most 12 images")
    for u in v:
        if not _URL.match(u) or len(u) > 500:
            raise ValueError("Images must be http(s) URLs")
    return v


class CategoryIn(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    description: str | None = Field(default=None, max_length=300)


class CategoryUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=80)
    description: str | None = Field(default=None, max_length=300)


class CategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    slug: str
    name: str
    description: str | None = None


class CategoryBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    slug: str
    name: str


class DestinationBase(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    country: str = Field(min_length=2, max_length=80)
    region: str | None = Field(default=None, max_length=80)
    description: str = Field(default="", max_length=5000)
    latitude: Lat
    longitude: Lng
    estimated_cost_per_day_minor: int | None = Field(default=None, ge=0, le=10**9)
    recommended_duration_days: int | None = Field(default=None, ge=1, le=60)
    best_season_start_month: int | None = Field(default=None, ge=1, le=12)
    best_season_end_month: int | None = Field(default=None, ge=1, le=12)
    climate: str | None = None
    climate_notes: str | None = Field(default=None, max_length=300)
    accessibility_notes: str | None = Field(default=None, max_length=500)
    images: list[str] = Field(default_factory=list)
    is_published: bool = False

    _img = field_validator("images")(_images)

    @field_validator("climate")
    @classmethod
    def _climate(cls, v: str | None) -> str | None:
        if v is not None and v not in Climate:
            raise ValueError(f"climate must be one of {Climate}")
        return v

    @model_validator(mode="after")
    def _season(self):
        if (self.best_season_start_month is None) != (self.best_season_end_month is None):
            raise ValueError("Set both best_season_start_month and best_season_end_month, or neither")
        return self


class DestinationCreate(DestinationBase):
    category_ids: list[uuid.UUID] = Field(default_factory=list, max_length=10)


class DestinationUpdate(BaseModel):
    """PATCH semantics: only the fields sent are changed."""

    name: str | None = Field(default=None, min_length=2, max_length=120)
    country: str | None = Field(default=None, min_length=2, max_length=80)
    region: str | None = Field(default=None, max_length=80)
    description: str | None = Field(default=None, max_length=5000)
    latitude: Lat | None = None
    longitude: Lng | None = None
    estimated_cost_per_day_minor: int | None = Field(default=None, ge=0, le=10**9)
    recommended_duration_days: int | None = Field(default=None, ge=1, le=60)
    best_season_start_month: int | None = Field(default=None, ge=1, le=12)
    best_season_end_month: int | None = Field(default=None, ge=1, le=12)
    climate: str | None = None
    climate_notes: str | None = Field(default=None, max_length=300)
    accessibility_notes: str | None = Field(default=None, max_length=500)
    images: list[str] | None = None
    is_published: bool | None = None
    category_ids: list[uuid.UUID] | None = Field(default=None, max_length=10)

    @field_validator("images")
    @classmethod
    def _img(cls, v):
        return None if v is None else _images(v)

    @field_validator("climate")
    @classmethod
    def _climate(cls, v: str | None) -> str | None:
        if v is not None and v not in Climate:
            raise ValueError(f"climate must be one of {Climate}")
        return v


class DestinationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    slug: str
    name: str
    country: str
    region: str | None
    description: str
    latitude: float
    longitude: float
    estimated_cost_per_day_minor: int | None
    currency: str
    recommended_duration_days: int | None
    best_season_start_month: int | None
    best_season_end_month: int | None
    climate: str | None
    climate_notes: str | None
    accessibility_notes: str | None
    images: list[str]
    is_published: bool
    source: str  # "seed"/"admin" values are curated estimates; only "provider" is sourced data
    categories: list[CategoryBrief]
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None
    attraction_count: int = 0
    distance_m: float | None = None


OpeningHours = dict[str, list[list[str]]]


def _validate_hours(v: OpeningHours | None) -> OpeningHours | None:
    if v is None:
        return v
    for day, spans in v.items():
        if day not in DAYS:
            raise ValueError(f"Unknown day '{day}' (use {DAYS})")
        for span in spans:
            if len(span) != 2 or not all(_HHMM.match(t) for t in span):
                raise ValueError("Each span must be [\"HH:MM\", \"HH:MM\"]")
            if span[0] >= span[1]:
                raise ValueError("Opening time must be before closing time")
    return v


class AttractionBase(BaseModel):
    category_id: uuid.UUID
    name: str = Field(min_length=2, max_length=140)
    description: str = Field(default="", max_length=5000)
    latitude: Lat
    longitude: Lng
    estimated_cost_minor: int | None = Field(default=None, ge=0, le=10**9)
    typical_duration_minutes: int = Field(default=90, ge=5, le=1440)
    opening_hours: OpeningHours | None = None
    is_outdoor: bool = False
    accessibility_notes: str | None = Field(default=None, max_length=500)
    images: list[str] = Field(default_factory=list)
    is_published: bool = False

    _img = field_validator("images")(_images)
    _hours = field_validator("opening_hours")(_validate_hours)


class AttractionCreate(AttractionBase):
    destination_id: uuid.UUID


class AttractionUpdate(BaseModel):
    category_id: uuid.UUID | None = None
    name: str | None = Field(default=None, min_length=2, max_length=140)
    description: str | None = Field(default=None, max_length=5000)
    latitude: Lat | None = None
    longitude: Lng | None = None
    estimated_cost_minor: int | None = Field(default=None, ge=0, le=10**9)
    typical_duration_minutes: int | None = Field(default=None, ge=5, le=1440)
    opening_hours: OpeningHours | None = None
    is_outdoor: bool | None = None
    accessibility_notes: str | None = Field(default=None, max_length=500)
    images: list[str] | None = None
    is_published: bool | None = None

    _hours = field_validator("opening_hours")(_validate_hours)

    @field_validator("images")
    @classmethod
    def _img(cls, v):
        return None if v is None else _images(v)


class AttractionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    destination_id: uuid.UUID
    slug: str
    name: str
    description: str
    category: CategoryBrief
    latitude: float
    longitude: float
    estimated_cost_minor: int | None
    currency: str
    typical_duration_minutes: int
    opening_hours: OpeningHours | None
    opening_hours_source: str | None  # null = unknown; never assumed
    is_outdoor: bool
    accessibility_notes: str | None
    images: list[str]
    is_published: bool
    source: str
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None
    distance_m: float | None = None


DestinationSort = Literal["name", "-name", "cost", "-cost", "duration", "newest", "distance"]
AttractionSort = Literal["name", "-name", "cost", "-cost", "duration", "newest", "distance"]
