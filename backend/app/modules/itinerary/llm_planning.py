"""LLM-assisted steps with strict validation. The LLM never produces times, prices or distances: it may
only (1) interpret a free-text request and (2) propose how to GROUP the supplied attractions into days.
Anything that fails Pydantic/ID validation raises LLMOutputError and the caller falls back to the
deterministic planner."""

from __future__ import annotations

import json
import logging

from pydantic import BaseModel, Field, ValidationError, field_validator

from app.integrations.llm.base import LLMClient, LLMError, extract_json
from app.modules.itinerary.planner import Candidate, PlanParams

log = logging.getLogger("routeaura.llm")
MAX_ATTEMPTS = 2


class LLMOutputError(Exception):
    """The model replied, but not with something we can safely use."""


class TripIntent(BaseModel):
    destination_name: str | None = Field(default=None, max_length=120)
    days: int | None = Field(default=None, ge=1, le=14)
    budget_total_inr: float | None = Field(default=None, ge=0, le=10**8)
    travelers: int | None = Field(default=None, ge=1, le=20)
    interests: list[str] = Field(default_factory=list, max_length=20)
    travel_style: str | None = None

    @field_validator("travel_style")
    @classmethod
    def _style(cls, v):
        return v if v in (None, "budget", "comfort", "luxury", "adventure", "relaxed") else None


class LLMDay(BaseModel):
    day: int = Field(ge=1, le=14)
    attraction_ids: list[str] = Field(max_length=10)
    theme: str = Field(default="", max_length=120)
    rationale: str = Field(default="", max_length=300)


class LLMPlan(BaseModel):
    days: list[LLMDay]


INTENT_SYSTEM = (
    "You extract trip requirements from a traveler's message. Reply with ONLY a JSON object with keys: "
    "destination_name (string|null), days (integer 1-14|null), budget_total_inr (number|null), travelers (integer|null), "
    "interests (array of short lowercase strings), travel_style (one of budget, comfort, luxury, adventure, relaxed, or null). "
    "Use null when the message does not say. Do not guess."
)
PLAN_SYSTEM = (
    "You are a trip-planning assistant. You are given a list of attractions (with ids) and trip constraints. "
    "Group a good subset of them into days. Reply with ONLY JSON: "
    '{"days":[{"day":1,"attraction_ids":["<id>",...],"theme":"short","rationale":"one sentence"}]}. '
    "Rules: use ONLY ids from the list, never repeat an id, at most {max_per_day} attractions per day, keep nearby "
    "attractions on the same day. Do NOT output times, prices, distances, opening hours or weather: those are computed elsewhere."
)


def _call(llm: LLMClient, system: str, user: str, model_cls: type[BaseModel], *, extra_check=None):
    last_error = ""
    for attempt in range(MAX_ATTEMPTS):
        prompt = (
            user
            if not last_error
            else f"{user}\n\nYour previous reply was rejected: {last_error}. Reply with corrected JSON only."
        )
        try:
            raw = llm.complete(system, prompt)
        except LLMError:
            raise
        try:
            obj = model_cls.model_validate(extract_json(raw))
            if extra_check:
                extra_check(obj)
            return obj
        except (ValueError, ValidationError, LLMOutputError) as exc:
            last_error = str(exc).replace("\n", " ")[:300]
            log.warning("llm output rejected (attempt %d): %s", attempt + 1, last_error)
    raise LLMOutputError(last_error or "invalid output")


def interpret_intent(llm: LLMClient, prompt: str) -> TripIntent:
    return _call(llm, INTENT_SYSTEM, prompt, TripIntent)


def validate_plan(plan: LLMPlan, allowed: set[str], days: int, max_per_day: int) -> None:
    seen: set[str] = set()
    day_numbers = [d.day for d in plan.days]
    if len(set(day_numbers)) != len(day_numbers) or any(n > days for n in day_numbers):
        raise LLMOutputError("day numbers must be unique and within the trip length")
    for d in plan.days:
        if len(d.attraction_ids) > max_per_day:
            raise LLMOutputError(f"day {d.day} has more than {max_per_day} attractions")
        for a in d.attraction_ids:
            if a not in allowed:
                raise LLMOutputError(f"unknown attraction id {a!r}")
            if a in seen:
                raise LLMOutputError(f"attraction {a!r} used more than once")
            seen.add(a)
    if not seen:
        raise LLMOutputError("plan contains no attractions")


def propose_plan(
    llm: LLMClient, cands: list[Candidate], p: PlanParams, interests: list[str], style: str | None
) -> LLMPlan:
    listing = [
        {
            "id": c.id,
            "name": c.name,
            "category": c.category,
            "visit_minutes": c.duration_min,
            "outdoor": c.is_outdoor,
            "lat": round(c.lat, 4),
            "lng": round(c.lng, 4),
            "relevance": round(c.score, 2),
        }
        for c in cands
    ]
    user = json.dumps(
        {
            "trip_days": p.days,
            "travelers": p.travelers,
            "interests": interests,
            "travel_style": style,
            "attractions": listing,
        },
        ensure_ascii=False,
    )
    allowed = {c.id for c in cands}
    return _call(
        llm,
        PLAN_SYSTEM.replace("{max_per_day}", str(p.max_per_day)),
        user,
        LLMPlan,
        extra_check=lambda plan: validate_plan(plan, allowed, p.days, p.max_per_day),
    )
