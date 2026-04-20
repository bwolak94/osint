"""Add stealer_log_checks table

Revision ID: a1b2c3d4e5f7
Revises: f6a1b2c3d4e5
Create Date: 2026-04-19
"""

from alembic import op
import sqlalchemy as sa

revision = "a1b2c3d4e5f7"
down_revision = "f6a1b2c3d4e5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "stealer_log_checks",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("owner_id", sa.UUID(), nullable=False),
        sa.Column("query", sa.String(255), nullable=False),
        sa.Column("query_type", sa.String(20), nullable=False),
        sa.Column("total_infections", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("infections", sa.JSON(), nullable=False),
        sa.Column("sources_checked", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_stealer_log_checks_owner_id", "stealer_log_checks", ["owner_id"])
    op.create_index("ix_stealer_log_checks_created_at", "stealer_log_checks", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_stealer_log_checks_created_at", table_name="stealer_log_checks")
    op.drop_index("ix_stealer_log_checks_owner_id", table_name="stealer_log_checks")
    op.drop_table("stealer_log_checks")
