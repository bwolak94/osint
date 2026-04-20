"""Add socmint_scans table

Revision ID: g7h8i9j0k1l2
Revises: f6a1b2c3d4e7
Create Date: 2026-04-20 13:00:00.000000

Creates the socmint_scans table used by the SOCMINT (Social Media Intelligence) module
to persist aggregated multi-module scan results per user.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "g7h8i9j0k1l2"
down_revision = "f6a1b2c3d4e7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "socmint_scans",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("owner_id", sa.UUID(), nullable=False),
        # Target identifier: username, email, phone, or profile URL
        sa.Column("target", sa.String(255), nullable=False),
        # "username" | "email" | "phone" | "url"
        sa.Column("target_type", sa.String(20), nullable=False),
        # JSON array of SOCMINT module names that were executed
        sa.Column("modules_run", sa.JSON(), nullable=False),
        # JSON object: {module_name: {found, data, error?, status}}
        sa.Column("results", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # Index for fast per-user queries (primary access pattern)
    op.create_index("ix_socmint_scans_owner_id", "socmint_scans", ["owner_id"])
    # Index for ordering by creation time (used in list endpoint)
    op.create_index("ix_socmint_scans_created_at", "socmint_scans", ["created_at"])


def downgrade() -> None:
    # DESTRUCTIVE: drops all SOCMINT scan records
    op.drop_index("ix_socmint_scans_created_at", table_name="socmint_scans")
    op.drop_index("ix_socmint_scans_owner_id", table_name="socmint_scans")
    op.drop_table("socmint_scans")
