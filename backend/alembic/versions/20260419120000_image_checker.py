"""Add image_checks table

Revision ID: a1b2c3d4e5f6
Revises: None
Create Date: 2026-04-19

This is the initial migration. It creates the image_checks table used by the
OSINT Image Checker module to persist extracted image metadata per user.
"""

from alembic import op
import sqlalchemy as sa

# ---------------------------------------------------------------------------
# Alembic revision metadata
# ---------------------------------------------------------------------------
revision = "a1b2c3d4e5f6"
down_revision = None  # First migration — no prior revision
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "image_checks",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("owner_id", sa.UUID(), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("file_hash", sa.String(64), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("mime_type", sa.String(100), nullable=False),
        # Full extracted EXIF/metadata dict — never null, defaults to {}
        sa.Column("metadata", sa.JSON(), nullable=False),
        # GPS sub-dict {lat, lon, altitude, gps_timestamp, maps_url} or NULL
        sa.Column("gps_data", sa.JSON(), nullable=True),
        sa.Column("camera_make", sa.String(100), nullable=True),
        sa.Column("camera_model", sa.String(100), nullable=True),
        # DateTimeOriginal from EXIF — NULL when image has no EXIF timestamp
        sa.Column("taken_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # Index for fast per-user queries (primary access pattern)
    op.create_index("ix_image_checks_owner_id", "image_checks", ["owner_id"])
    # Index for ordering by creation time (used in list endpoint)
    op.create_index("ix_image_checks_created_at", "image_checks", ["created_at"])


def downgrade() -> None:
    # DESTRUCTIVE: drops all image check records
    op.drop_index("ix_image_checks_created_at", table_name="image_checks")
    op.drop_index("ix_image_checks_owner_id", table_name="image_checks")
    op.drop_table("image_checks")
