"""Add imint_scans table

Revision ID: i9j0k1l2m3n4
Revises: h8i9j0k1l2m3
Create Date: 2026-04-20 15:00:00.000000

Creates the imint_scans table for Domain IV (Modules 61-80):
Image forensics, geospatial intelligence, satellite analysis, sun chronolocation,
ADS-B/AIS tracking, deepfake detection, and visual landmark matching.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "i9j0k1l2m3n4"
down_revision = "h8i9j0k1l2m3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "imint_scans",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("owner_id", sa.UUID(), nullable=False),
        # Target: image URL, "lat,lon" coordinate string, or plain URL
        sa.Column("target", sa.String(2048), nullable=False),
        # "image_url" | "coordinates" | "url"
        sa.Column("target_type", sa.String(20), nullable=False),
        # JSON array of module names executed
        sa.Column("modules_run", sa.JSON(), nullable=False),
        # JSON object: {module_name: {found, data, error?, status}}
        sa.Column("results", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_imint_scans_owner_id", "imint_scans", ["owner_id"])
    op.create_index("ix_imint_scans_created_at", "imint_scans", ["created_at"])


def downgrade() -> None:
    # DESTRUCTIVE: drops all IMINT/GEOINT scan records
    op.drop_index("ix_imint_scans_created_at", table_name="imint_scans")
    op.drop_index("ix_imint_scans_owner_id", table_name="imint_scans")
    op.drop_table("imint_scans")
