"""Baseline schema.

The baseline revision creates every table from the SQLAlchemy models (single source of truth),
including indexes and foreign keys. All later schema changes must be added as normal Alembic
revisions: `alembic revision --autogenerate -m "..."`.

Revision ID: 0001_baseline
Revises:
Create Date: 2026-11-17
"""
from alembic import op

import app.models  # noqa: F401
from app.core.database import Base

revision = "0001_baseline"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        # PostGIS is enabled for future geometry columns (supplier locations / service areas).
        op.execute("CREATE EXTENSION IF NOT EXISTS postgis")
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    Base.metadata.drop_all(bind=op.get_bind())
