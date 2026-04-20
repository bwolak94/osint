"""Add tech_recon_scans table

Revision ID: f6a1b2c3d4e7
Revises: e5f6a1b2c3d5
Create Date: 2026-04-20 12:00:00.000000

Creates the tech_recon_scans table used by the Technical Reconnaissance module
to persist aggregated multi-module scan results per user.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# ---------------------------------------------------------------------------
# Alembic revision metadata
# ---------------------------------------------------------------------------
revision = "f6a1b2c3d4e7"
down_revision = "e5f6a1b2c3d5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tech_recon_scans",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("owner_id", sa.UUID(), nullable=False),
        # Domain or IP address that was scanned
        sa.Column("target", sa.String(255), nullable=False),
        # "domain" or "ip"
        sa.Column("target_type", sa.String(10), nullable=False),
        # JSON array of module names that were executed
        sa.Column("modules_run", sa.JSON(), nullable=False),
        # JSON object: {module_name: {found, data, error?, status}}
        sa.Column("results", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # Index for fast per-user queries (primary access pattern)
    op.create_index("ix_tech_recon_scans_owner_id", "tech_recon_scans", ["owner_id"])
    # Index for ordering by creation time (used in list endpoint)
    op.create_index("ix_tech_recon_scans_created_at", "tech_recon_scans", ["created_at"])


def downgrade() -> None:
    # DESTRUCTIVE: drops all tech recon scan records
    op.drop_index("ix_tech_recon_scans_created_at", table_name="tech_recon_scans")
    op.drop_index("ix_tech_recon_scans_owner_id", table_name="tech_recon_scans")
    op.drop_table("tech_recon_scans")
