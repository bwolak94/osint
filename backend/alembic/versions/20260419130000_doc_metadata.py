"""Add doc_metadata_checks table

Revision ID: b2c3d4e5f6a1
Revises: a1b2c3d4e5f6
Create Date: 2026-04-19

Creates the doc_metadata_checks table for the Document Metadata Extractor module.
"""

from alembic import op
import sqlalchemy as sa

revision = "b2c3d4e5f6a1"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "doc_metadata_checks",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("owner_id", sa.UUID(), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("file_hash", sa.String(64), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("mime_type", sa.String(100), nullable=False),
        sa.Column("doc_format", sa.String(20), nullable=True),
        sa.Column("author", sa.String(255), nullable=True),
        sa.Column("creator_tool", sa.String(255), nullable=True),
        sa.Column("company", sa.String(255), nullable=True),
        sa.Column("last_modified_by", sa.String(255), nullable=True),
        sa.Column("created_at_doc", sa.DateTime(timezone=True), nullable=True),
        sa.Column("modified_at_doc", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revision_count", sa.Integer(), nullable=True),
        sa.Column("has_macros", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("has_hidden_content", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("has_tracked_changes", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("gps_lat", sa.Float(), nullable=True),
        sa.Column("gps_lon", sa.Float(), nullable=True),
        sa.Column("raw_metadata", sa.JSON(), nullable=False),
        sa.Column("embedded_files", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_doc_metadata_checks_owner_id", "doc_metadata_checks", ["owner_id"])
    op.create_index("ix_doc_metadata_checks_created_at", "doc_metadata_checks", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_doc_metadata_checks_created_at", table_name="doc_metadata_checks")
    op.drop_index("ix_doc_metadata_checks_owner_id", table_name="doc_metadata_checks")
    op.drop_table("doc_metadata_checks")
