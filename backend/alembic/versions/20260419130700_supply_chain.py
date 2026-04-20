"""Add supply_chain_scans table

Revision ID: c3d4e5f6a1b3
Revises: b2c3d4e5f6a2
Create Date: 2026-04-19
"""

from alembic import op
import sqlalchemy as sa

revision = "c3d4e5f6a1b3"
down_revision = "b2c3d4e5f6a2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "supply_chain_scans",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("owner_id", sa.UUID(), nullable=False),
        sa.Column("target", sa.String(255), nullable=False),
        sa.Column("target_type", sa.String(20), nullable=False),
        sa.Column("total_packages", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_cves", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("packages", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_supply_chain_scans_owner_id", "supply_chain_scans", ["owner_id"])
    op.create_index("ix_supply_chain_scans_created_at", "supply_chain_scans", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_supply_chain_scans_created_at", table_name="supply_chain_scans")
    op.drop_index("ix_supply_chain_scans_owner_id", table_name="supply_chain_scans")
    op.drop_table("supply_chain_scans")
