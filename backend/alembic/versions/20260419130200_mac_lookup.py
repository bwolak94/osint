"""Add mac_lookups table

Revision ID: d4e5f6a1b2c3
Revises: c3d4e5f6a1b2
Create Date: 2026-04-19
"""

from alembic import op
import sqlalchemy as sa

revision = "d4e5f6a1b2c3"
down_revision = "c3d4e5f6a1b2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "mac_lookups",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("owner_id", sa.UUID(), nullable=False),
        sa.Column("mac_address", sa.String(17), nullable=False),
        sa.Column("oui_prefix", sa.String(8), nullable=True),
        sa.Column("manufacturer", sa.String(255), nullable=True),
        sa.Column("manufacturer_country", sa.String(100), nullable=True),
        sa.Column("device_type", sa.String(100), nullable=True),
        sa.Column("is_private", sa.Boolean(), nullable=True),
        sa.Column("is_multicast", sa.Boolean(), nullable=True),
        sa.Column("raw_data", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_mac_lookups_owner_id", "mac_lookups", ["owner_id"])
    op.create_index("ix_mac_lookups_created_at", "mac_lookups", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_mac_lookups_created_at", table_name="mac_lookups")
    op.drop_index("ix_mac_lookups_owner_id", table_name="mac_lookups")
    op.drop_table("mac_lookups")
