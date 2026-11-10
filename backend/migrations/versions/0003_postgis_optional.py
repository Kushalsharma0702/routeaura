"""Optional PostGIS: geography columns + GiST indexes when the extension is available.

Plain latitude/longitude columns remain the source of truth. On PostgreSQL without PostGIS
this migration is a no-op and the app uses the portable haversine backend. To enable PostGIS
later, install the extension and run `python -m app.scripts.enable_postgis` (same SQL).

Revision ID: 0003
Revises: 0002
"""
from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

TABLES = ("destinations", "attractions")


def upgrade() -> None:
    bind = op.get_bind()
    available = bind.execute(
        sa.text("SELECT 1 FROM pg_available_extensions WHERE name = 'postgis'")
    ).scalar()
    if not available:
        return
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")
    for t in TABLES:
        op.execute(
            f"ALTER TABLE {t} ADD COLUMN IF NOT EXISTS location geography(Point,4326) "
            "GENERATED ALWAYS AS (ST_SetSRID(ST_MakePoint(longitude::float8, latitude::float8), 4326)"
            "::geography) STORED"
        )
        op.execute(f"CREATE INDEX IF NOT EXISTS ix_{t}_location ON {t} USING GIST (location)")


def downgrade() -> None:
    for t in TABLES:
        op.execute(f"DROP INDEX IF EXISTS ix_{t}_location")
        op.execute(f"ALTER TABLE {t} DROP COLUMN IF EXISTS location")
    # The extension itself is left installed (other objects may depend on it).
