"""Add domain_permutation_scans table

Revision ID: e5f6a1b2c3d4
Revises: d4e5f6a1b2c3
Create Date: 2026-04-19
"""

from alembic import op
import sqlalchemy as sa

revision = "e5f6a1b2c3d4"
down_revision = "d4e5f6a1b2c3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "domain_permutation_scans",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("owner_id", sa.UUID(), nullable=False),
        sa.Column("target_domain", sa.String(255), nullable=False),
        sa.Column("total_permutations", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("registered_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("permutations", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_domain_permutation_scans_owner_id", "domain_permutation_scans", ["owner_id"])
    op.create_index("ix_domain_permutation_scans_created_at", "domain_permutation_scans", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_domain_permutation_scans_created_at", table_name="domain_permutation_scans")
    op.drop_index("ix_domain_permutation_scans_owner_id", table_name="domain_permutation_scans")
    op.drop_table("domain_permutation_scans")
