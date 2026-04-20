"""Add cloud_exposure_scans table

Revision ID: f6a1b2c3d4e5
Revises: e5f6a1b2c3d4
Create Date: 2026-04-19
"""

from alembic import op
import sqlalchemy as sa

revision = "f6a1b2c3d4e5"
down_revision = "e5f6a1b2c3d4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "cloud_exposure_scans",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("owner_id", sa.UUID(), nullable=False),
        sa.Column("target", sa.String(255), nullable=False),
        sa.Column("total_buckets", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("public_buckets", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("sensitive_findings", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("buckets", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_cloud_exposure_scans_owner_id", "cloud_exposure_scans", ["owner_id"])
    op.create_index("ix_cloud_exposure_scans_created_at", "cloud_exposure_scans", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_cloud_exposure_scans_created_at", table_name="cloud_exposure_scans")
    op.drop_index("ix_cloud_exposure_scans_owner_id", table_name="cloud_exposure_scans")
    op.drop_table("cloud_exposure_scans")
