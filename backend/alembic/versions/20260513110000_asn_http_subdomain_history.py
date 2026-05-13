"""Create asn_intel_scans, http_fingerprint_scans, subdomain_takeover_scans tables.

Revision ID: 20260513110000
Revises: 20260513100000
Create Date: 2026-05-13 11:00:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260513110000"
down_revision = "20260513100000"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "asn_intel_scans",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("query", sa.String(255), nullable=False),
        sa.Column("found", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("result", postgresql.JSON(), nullable=False, server_default="{}"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_asn_intel_scans_owner_id", "asn_intel_scans", ["owner_id"])
    op.create_index("ix_asn_intel_scans_created_at", "asn_intel_scans", ["created_at"])

    op.create_table(
        "http_fingerprint_scans",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("url", sa.String(500), nullable=False),
        sa.Column("security_score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("result", postgresql.JSON(), nullable=False, server_default="{}"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_http_fingerprint_scans_owner_id", "http_fingerprint_scans", ["owner_id"])
    op.create_index("ix_http_fingerprint_scans_created_at", "http_fingerprint_scans", ["created_at"])

    op.create_table(
        "subdomain_takeover_scans",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("domain", sa.String(255), nullable=False),
        sa.Column("total_subdomains", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("vulnerable_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("result", postgresql.JSON(), nullable=False, server_default="{}"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_subdomain_takeover_scans_owner_id", "subdomain_takeover_scans", ["owner_id"])
    op.create_index("ix_subdomain_takeover_scans_created_at", "subdomain_takeover_scans", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_subdomain_takeover_scans_created_at", table_name="subdomain_takeover_scans")
    op.drop_index("ix_subdomain_takeover_scans_owner_id", table_name="subdomain_takeover_scans")
    op.drop_table("subdomain_takeover_scans")

    op.drop_index("ix_http_fingerprint_scans_created_at", table_name="http_fingerprint_scans")
    op.drop_index("ix_http_fingerprint_scans_owner_id", table_name="http_fingerprint_scans")
    op.drop_table("http_fingerprint_scans")

    op.drop_index("ix_asn_intel_scans_created_at", table_name="asn_intel_scans")
    op.drop_index("ix_asn_intel_scans_owner_id", table_name="asn_intel_scans")
    op.drop_table("asn_intel_scans")
