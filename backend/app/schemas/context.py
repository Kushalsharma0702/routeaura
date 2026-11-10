import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class ReportIn(BaseModel):
    """Something the traveler tells us. Stored and labelled as `user_reported`; never mistaken for provider data."""

    type: Literal["closure", "delay", "spent"]
    activity_id: uuid.UUID | None = None  # closure
    day_number: int | None = Field(default=None, ge=1, le=14)  # delay
    current_time_min: int | None = Field(default=None, ge=0, le=24 * 60)
    completed_activity_ids: list[uuid.UUID] = Field(default_factory=list, max_length=50)
    spent_minor: int | None = Field(default=None, ge=0, le=10**10)  # spent

    @model_validator(mode="after")
    def _needs(self):
        if self.type == "closure" and not self.activity_id:
            raise ValueError("closure reports need activity_id")
        if self.type == "delay" and (self.day_number is None or self.current_time_min is None):
            raise ValueError("delay reports need day_number and current_time_min")
        if self.type == "spent" and self.spent_minor is None:
            raise ValueError("spent reports need spent_minor")
        return self


class SnapshotOut(BaseModel):
    id: uuid.UUID
    kind: str
    day_number: int | None
    source: str
    payload: dict
    fetched_at: datetime
    age_minutes: int
    fresh: bool


class ContextStatusOut(BaseModel):
    weather_provider: str
    weather_configured: bool
    needs_dates: bool
    max_age_minutes: int
    snapshots: list[SnapshotOut]
    stale_days: list[int]
    notes: list[str]


class ProposalOut(BaseModel):
    id: uuid.UUID
    itinerary_id: uuid.UUID
    status: str
    trigger: dict
    changes: list[dict]
    preview: dict
    base_version: int
    material: bool
    applied_version: int | None
    created_at: datetime
    decided_at: datetime | None


class AdaptResultOut(BaseModel):
    issues: list[dict]
    proposals: list[ProposalOut]
    unresolved: list[dict]
    stale_days: list[int]
    notes: list[str]
    latency_ms: float
