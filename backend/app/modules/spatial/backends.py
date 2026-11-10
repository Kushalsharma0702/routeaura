"""Spatial query backends. Both expose the same two SQL expressions so repositories can
compose them with any other filter:

- `distance_m(table, lat, lng)`: SQL expression, metres on a sphere
- `within(table, lat, lng, radius_m)`: SQL boolean condition

`PostgisBackend` uses a GiST-indexed `location geography` column (ST_DWithin);
`HaversineBackend` uses a bounding-box prefilter on indexed lat/lng plus haversine in SQL and
works on plain PostgreSQL. Choose via SPATIAL_BACKEND=auto|postgis|haversine.
"""
from typing import Protocol

from sqlalchemy import ColumnElement, Engine, and_, cast, func, literal, literal_column, or_, text
from sqlalchemy.orm import Session
from sqlalchemy.types import UserDefinedType

from app.core.config import get_settings
from app.modules.spatial.geo import EARTH_RADIUS_M, bounding_box


class Geography(UserDefinedType):
    cache_ok = True

    def get_col_spec(self, **kw) -> str:
        return "geography"


class SpatialBackend(Protocol):
    name: str

    def distance_m(self, table, lat: float, lng: float) -> ColumnElement[float]: ...
    def within(self, table, lat: float, lng: float, radius_m: float) -> ColumnElement[bool]: ...


class HaversineBackend:
    name = "haversine"

    def distance_m(self, table, lat: float, lng: float) -> ColumnElement[float]:
        lat1, lng1 = func.radians(literal(lat)), literal(lng)
        lat2 = func.radians(table.c.latitude)
        dphi = lat2 - lat1
        dlmb = func.radians(table.c.longitude - lng1)
        a = func.power(func.sin(dphi / 2), 2) + func.cos(lat1) * func.cos(lat2) * func.power(
            func.sin(dlmb / 2), 2
        )
        return 2 * EARTH_RADIUS_M * func.asin(func.least(1.0, func.sqrt(a)))

    def within(self, table, lat: float, lng: float, radius_m: float) -> ColumnElement[bool]:
        min_lat, max_lat, lng_ranges = bounding_box(lat, lng, radius_m)
        box = and_(
            table.c.latitude.between(min_lat, max_lat),
            or_(*[table.c.longitude.between(lo, hi) for lo, hi in lng_ranges]),
        )
        return and_(box, self.distance_m(table, lat, lng) <= radius_m)


class PostgisBackend:
    name = "postgis"

    @staticmethod
    def _location(table):
        # `location` is a database-generated column, deliberately not mapped on the ORM models
        return literal_column(f'"{table.name}".location', Geography())

    @staticmethod
    def _point(lat: float, lng: float):
        return cast(func.ST_SetSRID(func.ST_MakePoint(lng, lat), 4326), Geography())

    def distance_m(self, table, lat: float, lng: float) -> ColumnElement[float]:
        # use_spheroid=false => sphere, consistent with the haversine reference
        return func.ST_Distance(self._location(table), self._point(lat, lng), False)

    def within(self, table, lat: float, lng: float, radius_m: float) -> ColumnElement[bool]:
        return func.ST_DWithin(self._location(table), self._point(lat, lng), radius_m, False)


def postgis_available(engine: Engine) -> bool:
    """True when the PostgreSQL server ships the PostGIS extension (installed or installable)."""
    with engine.connect() as conn:
        return conn.execute(text("SELECT 1 FROM pg_available_extensions WHERE name = 'postgis'")).scalar() is not None


def postgis_enabled(engine_or_session: Engine | Session) -> bool:
    """True when the extension and the generated `location` columns are installed."""
    sql = text(
        "SELECT count(*) FROM information_schema.columns "
        "WHERE column_name = 'location' AND table_name IN ('destinations', 'attractions')"
    )
    if isinstance(engine_or_session, Session):
        return (engine_or_session.execute(sql).scalar() or 0) >= 2
    with engine_or_session.connect() as conn:
        return (conn.execute(sql).scalar() or 0) >= 2


_cached: SpatialBackend | None = None


def get_spatial_backend(db: Session) -> SpatialBackend:
    global _cached
    mode = get_settings().spatial_backend
    if mode == "haversine":
        return HaversineBackend()
    if mode == "postgis":
        return PostgisBackend()
    if _cached is None:
        _cached = PostgisBackend() if postgis_enabled(db) else HaversineBackend()
    return _cached


def reset_backend_cache() -> None:
    global _cached
    _cached = None
