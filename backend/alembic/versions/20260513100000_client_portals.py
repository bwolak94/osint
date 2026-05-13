"""Create client_portals table.

Revision ID: 20260513100000
Revises: 20260512160000
Create Date: 2026-05-13 10:00:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260513100000"
down_revision = "20260512160000"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "client_portals",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("client_name", sa.String(255), nullable=False),
        sa.Column("engagement_id", sa.String(255), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="active"),
        sa.Column("access_token", sa.String(64), nullable=False),
        sa.Column("allowed_sections", postgresql.JSON(), nullable=False, server_default="[]"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("view_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_client_portals_owner_id", "client_portals", ["owner_id"])
    op.create_index("ix_client_portals_created_at", "client_portals", ["created_at"])
    op.create_unique_constraint("uq_client_portals_access_token", "client_portals", ["access_token"])


def downgrade() -> None:
    op.drop_constraint("uq_client_portals_access_token", "client_portals", type_="unique")
    op.drop_index("ix_client_portals_created_at", table_name="client_portals")
    op.drop_index("ix_client_portals_owner_id", table_name="client_portals")
    op.drop_table("client_portals")
