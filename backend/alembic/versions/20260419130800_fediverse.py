"""fediverse_scans table

Revision ID: d4e5f6a1b2c4
Revises: c3d4e5f6a1b3
Create Date: 2026-04-19 13:08:00.000000
"""
from __future__ import annotations
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "d4e5f6a1b2c4"
down_revision: str | None = "c3d4e5f6a1b3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "fediverse_scans",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("query", sa.String(255), nullable=False),
        sa.Column("total_results", sa.Integer(), nullable=False),
        sa.Column("platforms_searched", postgresql.JSON(), nullable=False),
        sa.Column("results", postgresql.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_fediverse_scans_owner_id", "fediverse_scans", ["owner_id"])
    op.create_index("ix_fediverse_scans_created_at", "fediverse_scans", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_fediverse_scans_created_at", table_name="fediverse_scans")
    op.drop_index("ix_fediverse_scans_owner_id", table_name="fediverse_scans")
    op.drop_table("fediverse_scans")
