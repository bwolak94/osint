"""wigle_scans table

Revision ID: e5f6a1b2c3d5
Revises: d4e5f6a1b2c4
Create Date: 2026-04-19 13:09:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "e5f6a1b2c3d5"
down_revision: str | None = "d4e5f6a1b2c4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "wigle_scans",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("query", sa.String(255), nullable=False),
        sa.Column("query_type", sa.String(10), nullable=False),
        sa.Column("total_results", sa.Integer(), nullable=False),
        sa.Column("results", postgresql.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_wigle_scans_owner_id", "wigle_scans", ["owner_id"])
    op.create_index("ix_wigle_scans_created_at", "wigle_scans", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_wigle_scans_created_at", table_name="wigle_scans")
    op.drop_index("ix_wigle_scans_owner_id", table_name="wigle_scans")
    op.drop_table("wigle_scans")
