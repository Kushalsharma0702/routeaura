import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class WeightsIn(BaseModel):
    distance: float = Field(default=1.0, ge=0, le=100)
    time: float = Field(default=1.0, ge=0, le=100)
    cost: float = Field(default=0.5, ge=0, le=100)
    preference: float = Field(default=1.0, ge=0, le=100)
    taxi_rupees_per_km: float = Field(default=12.0, ge=0, le=1000)


class OptimizeRequest(BaseModel):
    weights: WeightsIn = Field(default_factory=WeightsIn)
    improve: bool = False  # slower guided local search (not deterministic across runs)
    time_limit_ms: int = Field(default=1500, ge=200, le=10000)


class PlanStop(BaseModel):
    id: uuid.UUID
    name: str
    lat: float
    lng: float
    start_time: str | None = None
    duration_min: int
    travel_min: int | None = None
    travel_m: int | None = None
    locked: bool = False


class PlanDay(BaseModel):
    day: int
    stops: list[PlanStop]


class PlanView(BaseModel):
    days: list[PlanDay]
    metrics: dict


class OptimizationOut(BaseModel):
    id: uuid.UUID
    itinerary_id: uuid.UUID
    status: str  # optimized | relaxed | infeasible
    applied: bool
    base_version: int
    weights: dict
    routing: dict  # source, notes, live_traffic, fetched_at
    before: PlanView
    after: PlanView | None
    delta: dict | None
    changes: list[str]
    dropped: list[dict]
    notes: list[str]
    solver_ms: float | None
    created_at: datetime
    applied_at: datetime | None
