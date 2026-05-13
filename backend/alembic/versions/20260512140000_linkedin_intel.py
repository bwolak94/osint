"""Create linkedin_intel_scans table.

Revision ID: 20260512140000
Revises: 20260512130000
Create Date: 2026-05-12 14:00:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260512140000"
down_revision = "20260512130000"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "linkedin_intel_scans",
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
    op.create_index("ix_linkedin_intel_scans_owner_id", "linkedin_intel_scans", ["owner_id"])
    op.create_index("ix_linkedin_intel_scans_created_at", "linkedin_intel_scans", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_linkedin_intel_scans_created_at", table_name="linkedin_intel_scans")
    op.drop_index("ix_linkedin_intel_scans_owner_id", table_name="linkedin_intel_scans")
    op.drop_table("linkedin_intel_scans")
