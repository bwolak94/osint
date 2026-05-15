"""Create evidence_items table for persistent evidence locker storage.

Replaces the in-memory _evidence_store dict with a proper Postgres table
supporting chain-of-custody (JSONB), tamper-evident hashing, and per-user ACLs.

Revision ID: 20260515120000
Revises: 20260513110000
Create Date: 2026-05-15 12:00:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY, JSONB

revision = "20260515120000"
down_revision = "20260513110000"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "evidence_items",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("type", sa.String(50), nullable=False),
        sa.Column("description", sa.Text, nullable=False, server_default=""),
        sa.Column("investigation_id", sa.String(100), nullable=True),
        sa.Column("tags", ARRAY(sa.String), nullable=False, server_default="{}"),
        sa.Column("chain_of_custody", JSONB, nullable=False, server_default="[]"),
        sa.Column("hash_sha256", sa.String(64), nullable=True),
        sa.Column("content_hash_verified", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("size_bytes", sa.Integer, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(100), nullable=False),
        sa.Column("sealed", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("is_admissible", sa.Boolean, nullable=False, server_default="true"),
        sa.CheckConstraint(
            "type IN ('screenshot','document','url','note','artifact','log','pcap','network_capture','memory_dump')",
            name="ck_evidence_type",
        ),
    )
    op.create_index("ix_evidence_items_investigation_id", "evidence_items", ["investigation_id"])
    op.create_index("ix_evidence_items_created_by", "evidence_items", ["created_by"])
    op.create_index("ix_evidence_items_created_by_inv", "evidence_items", ["created_by", "investigation_id"])


def downgrade() -> None:
    # Destructive: drops all evidence records. Back up the table before running.
    op.drop_index("ix_evidence_items_created_by_inv", table_name="evidence_items")
    op.drop_index("ix_evidence_items_created_by", table_name="evidence_items")
    op.drop_index("ix_evidence_items_investigation_id", table_name="evidence_items")
    op.drop_table("evidence_items")
