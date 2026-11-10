import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

Style = Literal["budget", "comfort", "luxury", "adventure", "relaxed"]


class StartLocation(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    lat: float = Field(ge=-90, le=90, allow_inf_nan=False)
    lng: float = Field(ge=-180, le=180, allow_inf_nan=False)


class TripRequest(BaseModel):
    destination_id: uuid.UUID
    days: int | None = Field(default=None, ge=1, le=14)
    start_date: date | None = None
    end_date: date | None = None
    travelers: int = Field(default=1, ge=1, le=20)
    budget_total_minor: int | None = Field(default=None, ge=0, le=10**10)
    interests: list[str] | None = Field(default=None, max_length=20)
    travel_style: Style | None = None
    accommodation_preference: str | None = Field(default=None, max_length=20)
    start_location: StartLocation | None = None
    title: str | None = Field(default=None, max_length=160)
    prompt: str | None = Field(default=None, max_length=1000)  # natural-language request (needs an LLM)
    use_llm: bool = True

    @model_validator(mode="after")
    def _dates(self):
        if self.end_date and not self.start_date:
            raise ValueError("end_date requires start_date")
        if self.start_date and self.start_date < date.today():
            raise ValueError("start_date cannot be in the past")
        if self.start_date and self.end_date:
            n = (self.end_date - self.start_date).days + 1
            if n < 1:
                raise ValueError("end_date must not be before start_date")
            if n > 14:
                raise ValueError("A trip can be at most 14 days")
            if self.days is not None and self.days != n:
                raise ValueError("days does not match start_date/end_date")
            self.days = n
        if self.days is None and not self.prompt:
            raise ValueError("Provide days, or start_date and end_date")
        return self


class RegenerateRequest(BaseModel):
    interests: list[str] | None = Field(default=None, max_length=20)
    travel_style: Style | None = None
    budget_total_minor: int | None = Field(default=None, ge=0, le=10**10)
    use_llm: bool = True


class ItineraryUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=160)
    status: Literal["draft", "saved"] | None = None
    budget_total_minor: int | None = Field(default=None, ge=0, le=10**10)
    traveler_count: int | None = Field(default=None, ge=1, le=20)
    start_date: date | None = None


class AddActivity(BaseModel):
    attraction_id: uuid.UUID
    day_number: int = Field(ge=1, le=14)
    position: int | None = Field(default=None, ge=1)
    duration_min: int | None = Field(default=None, ge=5, le=1440)


class UpdateActivity(BaseModel):
    duration_min: int | None = Field(default=None, ge=5, le=1440)
    notes: str | None = Field(default=None, max_length=500)
    locked: bool | None = None


class DayOrder(BaseModel):
    day_number: int = Field(ge=1, le=14)
    activity_ids: list[uuid.UUID]


class ReorderRequest(BaseModel):
    days: list[DayOrder]


class AttractionBrief(BaseModel):
    id: uuid.UUID
    name: str
    category: str
    latitude: float
    longitude: float
    is_outdoor: bool


class ActivityOut(BaseModel):
    id: uuid.UUID
    attraction: AttractionBrief
    day_number: int
    position: int
    start_min: int
    end_min: int
    start_time: str
    end_time: str
    duration_min: int
    travel_min: int
    travel_m: int
    travel_source: str = "estimate"
    locked: bool = False
    wait_min: int
    cost_minor: int | None
    cost_total_minor: int | None
    hours_status: str
    source: str
    score: float | None
    explanation: dict
    notes: str | None
    warnings: list[str]


class DayOut(BaseModel):
    day_number: int
    date: date | None
    activities: list[ActivityOut]
    lunch_start_min: int | None
    ends_at: str | None


class ViolationOut(BaseModel):
    type: str
    day: int | None
    activity_id: uuid.UUID | None
    message: str


class DestinationBrief(BaseModel):
    id: uuid.UUID
    slug: str
    name: str
    latitude: float
    longitude: float


class ItineraryOut(BaseModel):
    id: uuid.UUID
    title: str
    status: str
    destination: DestinationBrief
    start_date: date | None
    days: int
    traveler_count: int
    budget_total_minor: int | None
    currency: str
    interests: list[str]
    travel_style: str | None
    accommodation_preference: str | None
    start_location: dict | None
    generation_source: str
    generation_info: dict
    current_version: int
    day_plans: list[DayOut]
    budget: dict
    violations: list[ViolationOut]
    created_at: datetime
    updated_at: datetime


class ItinerarySummary(BaseModel):
    id: uuid.UUID
    title: str
    status: str
    destination_name: str
    start_date: date | None
    days: int
    traveler_count: int
    activity_count: int
    generation_source: str
    current_version: int
    updated_at: datetime


class VersionOut(BaseModel):
    version: int
    summary: str
    created_at: datetime


class VersionDetail(VersionOut):
    snapshot: dict
