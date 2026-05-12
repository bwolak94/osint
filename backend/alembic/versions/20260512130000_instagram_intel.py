"""Create instagram_intel_scans table.

Revision ID: 20260512130000
Revises: 20260512120000
Create Date: 2026-05-12 13:00:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260512130000"
down_revision = "20260512120000"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "instagram_intel_scans",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("query", sa.String(255), nullable=False),
        sa.Column("query_type", sa.String(50), nullable=False, server_default="username"),
        sa.Column("total_results", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("results", postgresql.JSON(), nullable=False, server_default="[]"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_instagram_intel_scans_owner_id", "instagram_intel_scans", ["owner_id"])
    op.create_index("ix_instagram_intel_scans_created_at", "instagram_intel_scans", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_instagram_intel_scans_created_at", table_name="instagram_intel_scans")
    op.drop_index("ix_instagram_intel_scans_owner_id", table_name="instagram_intel_scans")
    op.drop_table("instagram_intel_scans")
