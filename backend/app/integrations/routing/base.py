"""Routing provider interface. A provider returns a travel matrix between points, with the SOURCE and
FETCH TIME attached so every downstream number can be labelled (and judged for freshness)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Protocol

Point = tuple[float, float]  # (lat, lng)


class RoutingError(Exception):
    pass


@dataclass
class TravelMatrix:
    distance_m: list[list[int]]
    duration_min: list[list[int]]
    source: str  # "estimate" | "osrm" | ...
    fetched_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    live_traffic: bool = False  # True only if the provider really models traffic
    notes: list[str] = field(default_factory=list)

    def leg(self, i: int, j: int) -> tuple[int, int]:
        return self.distance_m[i][j], self.duration_min[i][j]


class RoutingProvider(Protocol):
    name: str

    def matrix(self, points: list[Point]) -> TravelMatrix: ...
