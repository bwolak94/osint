"""facebook_intel_scans table

Revision ID: 20260512120000
Revises: 20260428000000
Create Date: 2026-05-12 12:00:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260512120000"
down_revision: str | None = "20260428000000"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "facebook_intel_scans",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("query", sa.String(255), nullable=False),
        sa.Column("query_type", sa.String(50), nullable=False, server_default="name"),
        sa.Column("total_results", sa.Integer(), nullable=False),
        sa.Column("results", postgresql.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_facebook_intel_scans_owner_id", "facebook_intel_scans", ["owner_id"])
    op.create_index("ix_facebook_intel_scans_created_at", "facebook_intel_scans", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_facebook_intel_scans_created_at", table_name="facebook_intel_scans")
    op.drop_index("ix_facebook_intel_scans_owner_id", table_name="facebook_intel_scans")
    op.drop_table("facebook_intel_scans")
