import math
import random

import pytest

from app.modules.spatial.geo import EARTH_RADIUS_M, bounding_box, haversine_m, validate_lat_lng


def test_haversine_known_distances():
    assert haversine_m(10, 20, 10, 20) == 0
    assert haversine_m(0, 0, 0, 1) == pytest.approx(111_195, abs=50)  # one degree of arc
    assert haversine_m(0, 0, 0, 180) == pytest.approx(math.pi * EARTH_RADIUS_M, rel=1e-9)
    assert haversine_m(90, 0, -90, 0) == pytest.approx(math.pi * EARTH_RADIUS_M, rel=1e-9)
    # Delhi -> Jaipur great-circle is roughly 238 km
    assert haversine_m(28.6139, 77.2090, 26.9124, 75.7873) == pytest.approx(238_000, rel=0.02)


def test_haversine_symmetric_and_dateline_aware():
    assert haversine_m(10, 179.9, 10, -179.9) == pytest.approx(haversine_m(10, -179.9, 10, 179.9))
    assert haversine_m(10, 179.9, 10, -179.9) < 25_000  # short hop across the antimeridian


@pytest.mark.parametrize("lat,lng", [(91, 0), (-90.0001, 0), (0, 180.1), (0, -181), (float("nan"), 0),
                                      (0, float("inf"))])
def test_validate_rejects_bad_coordinates(lat, lng):
    with pytest.raises(ValueError):
        validate_lat_lng(lat, lng)


@pytest.mark.parametrize("lat,lng", [(90, 180), (-90, -180), (0, 0), (26.9, 75.8)])
def test_validate_accepts_boundaries(lat, lng):
    validate_lat_lng(lat, lng)


def test_bounding_box_shapes():
    min_lat, max_lat, ranges = bounding_box(26.9, 75.8, 10_000)
    assert len(ranges) == 1 and min_lat < 26.9 < max_lat
    # crosses the antimeridian -> two ranges
    _, _, wrap = bounding_box(0, 179.95, 20_000)
    assert len(wrap) == 2
    # contains a pole -> all longitudes
    _, hi, polar = bounding_box(89.9, 10, 50_000)
    assert hi == 90.0 and polar == [(-180.0, 180.0)]
    with pytest.raises(ValueError):
        bounding_box(0, 0, -1)


def test_bounding_box_never_excludes_a_point_inside_the_radius():
    """Property test: any point within the radius must lie inside the box (no false negatives)."""
    rng = random.Random(42)
    centres = [(26.9, 75.8), (0, 179.9), (0, -179.9), (89.0, 10), (-89.5, -120), (45, 0), (-33.9, 151.2)]
    for lat, lng in centres:
        for radius in (500, 5_000, 80_000, 700_000):
            min_lat, max_lat, ranges = bounding_box(lat, lng, radius)
            for _ in range(400):
                plat = max(-90, min(90, lat + rng.uniform(-8, 8)))
                plng = ((lng + rng.uniform(-15, 15) + 180) % 360) - 180
                if haversine_m(lat, lng, plat, plng) <= radius:
                    in_lng = any(lo <= plng <= hi for lo, hi in ranges)
                    assert min_lat <= plat <= max_lat and in_lng, (lat, lng, radius, plat, plng)
