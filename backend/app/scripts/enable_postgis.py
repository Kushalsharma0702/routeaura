"""Enable PostGIS on an existing database (idempotent). Requires the extension to be installed
on the server and a role allowed to CREATE EXTENSION."""
import sys

from sqlalchemy import text

from app.database.session import get_engine
from app.modules.spatial.backends import postgis_enabled

TABLES = ("destinations", "attractions")


def main() -> int:
    engine = get_engine()
    with engine.begin() as conn:
        if not conn.execute(text("SELECT 1 FROM pg_available_extensions WHERE name='postgis'")).scalar():
            print("PostGIS is not installed on this PostgreSQL server", file=sys.stderr)
            return 1
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
        for t in TABLES:
            conn.execute(text(
                f"ALTER TABLE {t} ADD COLUMN IF NOT EXISTS location geography(Point,4326) "
                "GENERATED ALWAYS AS (ST_SetSRID(ST_MakePoint(longitude::float8, latitude::float8),"
                "4326)::geography) STORED"))
            conn.execute(text(f"CREATE INDEX IF NOT EXISTS ix_{t}_location ON {t} USING GIST (location)"))
    print("PostGIS enabled:", postgis_enabled(engine))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
