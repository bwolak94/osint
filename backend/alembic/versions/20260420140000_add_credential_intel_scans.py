"""Add credential_intel_scans table

Revision ID: h8i9j0k1l2m3
Revises: g7h8i9j0k1l2
Create Date: 2026-04-20 14:00:00.000000

Creates the credential_intel_scans table for Domain III (Modules 41-60):
Breach aggregation, hash analysis, exposure detection, and threat intelligence.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "h8i9j0k1l2m3"
down_revision = "g7h8i9j0k1l2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "credential_intel_scans",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("owner_id", sa.UUID(), nullable=False),
        # Target: email address, domain name, IP address, or hash string
        sa.Column("target", sa.String(255), nullable=False),
        # "email" | "domain" | "ip" | "hash"
        sa.Column("target_type", sa.String(20), nullable=False),
        # JSON array of module names executed
        sa.Column("modules_run", sa.JSON(), nullable=False),
        # JSON object: {module_name: {found, data, error?, status}}
        sa.Column("results", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_credential_intel_scans_owner_id", "credential_intel_scans", ["owner_id"])
    op.create_index("ix_credential_intel_scans_created_at", "credential_intel_scans", ["created_at"])


def downgrade() -> None:
    # DESTRUCTIVE: drops all credential intelligence scan records
    op.drop_index("ix_credential_intel_scans_created_at", table_name="credential_intel_scans")
    op.drop_index("ix_credential_intel_scans_owner_id", table_name="credential_intel_scans")
    op.drop_table("credential_intel_scans")
