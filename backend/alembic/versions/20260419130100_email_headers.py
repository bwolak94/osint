"""Add email_header_checks table

Revision ID: c3d4e5f6a1b2
Revises: b2c3d4e5f6a1
Create Date: 2026-04-19
"""

from alembic import op
import sqlalchemy as sa

revision = "c3d4e5f6a1b2"
down_revision = "b2c3d4e5f6a1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "email_header_checks",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("owner_id", sa.UUID(), nullable=False),
        sa.Column("subject", sa.String(500), nullable=True),
        sa.Column("sender_from", sa.String(255), nullable=True),
        sa.Column("sender_reply_to", sa.String(255), nullable=True),
        sa.Column("originating_ip", sa.String(45), nullable=True),
        sa.Column("originating_country", sa.String(100), nullable=True),
        sa.Column("originating_city", sa.String(100), nullable=True),
        sa.Column("spf_result", sa.String(20), nullable=True),
        sa.Column("dkim_result", sa.String(20), nullable=True),
        sa.Column("dmarc_result", sa.String(20), nullable=True),
        sa.Column("is_spoofed", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("hops", sa.JSON(), nullable=False),
        sa.Column("raw_headers_summary", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_email_header_checks_owner_id", "email_header_checks", ["owner_id"])
    op.create_index("ix_email_header_checks_created_at", "email_header_checks", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_email_header_checks_created_at", table_name="email_header_checks")
    op.drop_index("ix_email_header_checks_owner_id", table_name="email_header_checks")
    op.drop_table("email_header_checks")
