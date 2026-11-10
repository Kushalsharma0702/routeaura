from __future__ import annotations

import httpx

from app.core.config import get_settings
from app.integrations.routing.base import Point, RoutingError, RoutingProvider, TravelMatrix
from app.modules.spatial.geo import haversine_m

DETOUR = 1.3
SPEED_KMH = 30.0


class EstimateRouting:
    """Always available. Great-circle distance x 1.3 at 30 km/h. An ESTIMATE, never presented as live data."""

    name = "estimate"

    def matrix(self, points: list[Point]) -> TravelMatrix:
        n = len(points)
        dist = [[0] * n for _ in range(n)]
        dur = [[0] * n for _ in range(n)]
        for i in range(n):
            for j in range(n):
                if i != j:
                    m = haversine_m(*points[i], *points[j]) * DETOUR
                    dist[i][j] = int(m)
                    dur[i][j] = max(1, round(m / 1000.0 / SPEED_KMH * 60))
        return TravelMatrix(
            dist,
            dur,
            "estimate",
            notes=[f"great-circle x {DETOUR} at {SPEED_KMH:g} km/h; not road routing and no traffic"],
        )


class OsrmRouting:
    """OSRM `table` service (self-hosted recommended; the public demo server is not for production use).
    Durations/distances are the router's free-flow road values: no live traffic."""

    name = "osrm"

    def __init__(self, base_url: str, timeout: float = 15.0, client: httpx.Client | None = None):
        self.base_url, self.timeout, self._client = base_url.rstrip("/"), timeout, client

    def matrix(self, points: list[Point]) -> TravelMatrix:
        if len(points) < 2:
            return TravelMatrix([[0]], [[0]], "osrm", notes=["single point"])
        coords = ";".join(f"{lng:.6f},{lat:.6f}" for lat, lng in points)
        url = f"{self.base_url}/table/v1/driving/{coords}"
        try:
            r = (self._client or httpx).get(url, params={"annotations": "duration,distance"}, timeout=self.timeout)
            r.raise_for_status()
            body = r.json()
            if body.get("code") != "Ok":
                raise RoutingError(f"osrm returned {body.get('code')}")
            dur, dist = body["durations"], body["distances"]
            if any(v is None for row in dur for v in row) or any(v is None for row in dist for v in row):
                raise RoutingError("osrm could not route between some points")
            return TravelMatrix(
                [[int(v) for v in row] for row in dist],
                [[max(0, round(v / 60)) for v in row] for row in dur],
                "osrm",
                notes=["road network free-flow estimate from OSRM; no live traffic"],
            )
        except (httpx.HTTPError, KeyError, ValueError) as exc:
            raise RoutingError(f"osrm request failed: {type(exc).__name__}") from exc


class ResilientRouting:
    """Uses the configured provider and falls back to the estimate if it fails, recording why."""

    def __init__(self, primary: RoutingProvider, fallback: RoutingProvider):
        self.primary, self.fallback, self.name = primary, fallback, primary.name

    def matrix(self, points: list[Point]) -> TravelMatrix:
        try:
            return self.primary.matrix(points)
        except RoutingError as exc:
            m = self.fallback.matrix(points)
            m.notes.append(f"{self.primary.name} unavailable ({exc}); using the estimate instead")
            return m


def get_routing() -> RoutingProvider:
    s = get_settings()
    est = EstimateRouting()
    if s.routing_provider == "osrm" and s.osrm_base_url:
        return ResilientRouting(OsrmRouting(s.osrm_base_url), est)
    return est
