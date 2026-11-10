"""Pure geospatial helpers: no database, no I/O. Independently unit-testable.

Reference implementation for the SQL backends: they must agree with `haversine_m`.
"""
import math

EARTH_RADIUS_M = 6_371_008.8  # mean Earth radius (IUGG); PostGIS sphere uses 6371008.7714


def validate_lat_lng(lat: float, lng: float) -> None:
    if not (math.isfinite(lat) and math.isfinite(lng)):
        raise ValueError("coordinates must be finite numbers")
    if not -90 <= lat <= 90:
        raise ValueError("latitude must be between -90 and 90")
    if not -180 <= lng <= 180:
        raise ValueError("longitude must be between -180 and 180")


def haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = p2 - p1
    dlmb = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(min(1.0, math.sqrt(a)))


def bounding_box(lat: float, lng: float, radius_m: float) -> tuple[float, float, list[tuple[float, float]]]:
    """Box that contains every point within `radius_m` of (lat, lng).

    Returns (min_lat, max_lat, lng_ranges). `lng_ranges` has two entries when the box crosses
    the antimeridian, and covers all longitudes when it contains a pole.
    """
    validate_lat_lng(lat, lng)
    if radius_m < 0:
        raise ValueError("radius must be non-negative")
    dlat = math.degrees(radius_m / EARTH_RADIUS_M)
    min_lat, max_lat = max(-90.0, lat - dlat), min(90.0, lat + dlat)
    if min_lat <= -90.0 or max_lat >= 90.0:  # pole inside the circle: every longitude qualifies
        return min_lat, max_lat, [(-180.0, 180.0)]
    dlng = math.degrees(radius_m / (EARTH_RADIUS_M * math.cos(math.radians(lat))))
    if dlng >= 180.0:
        return min_lat, max_lat, [(-180.0, 180.0)]
    lo, hi = lng - dlng, lng + dlng
    if lo < -180.0:
        return min_lat, max_lat, [(lo + 360.0, 180.0), (-180.0, hi)]
    if hi > 180.0:
        return min_lat, max_lat, [(lo, 180.0), (-180.0, hi - 360.0)]
    return min_lat, max_lat, [(lo, hi)]
