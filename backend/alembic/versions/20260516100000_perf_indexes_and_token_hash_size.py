"""Performance indexes, token_hash column widening, and partial index on refresh token expiry.

- token_hash: String(64) -> String(128) — headroom for future hash algorithm changes
- ix_refresh_tokens_active_expires: partial index on (token_hash, expires_at) WHERE is_revoked=false
- ix_scan_results_inv_created: composite index on (investigation_id, created_at)
- ix_scan_results_scanner_name: standalone index on scanner_name for admin/cross-investigation queries

Revision ID: 20260516100000
Revises: 20260515120000
Create Date: 2026-05-16 10:00:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260516100000"
down_revision = "20260515120000"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Widen token_hash to 128 chars to accommodate future hash algorithm changes
    op.alter_column(
        "refresh_tokens",
        "token_hash",
        existing_type=sa.String(64),
        type_=sa.String(128),
        nullable=False,
    )

    # Partial index for fast token validity lookups (skips revoked tokens)
    op.create_index(
        "ix_refresh_tokens_active_expires",
        "refresh_tokens",
        ["token_hash", "expires_at"],
        postgresql_where=sa.text("is_revoked = false"),
    )

    # Composite index for time-ordered scan result listing per investigation
    op.create_index(
        "ix_scan_results_inv_created",
        "scan_results",
        ["investigation_id", "created_at"],
    )

    # Standalone scanner_name index for admin/cross-investigation queries
    op.create_index(
        "ix_scan_results_scanner_name",
        "scan_results",
        ["scanner_name"],
    )


def downgrade() -> None:
    op.drop_index("ix_scan_results_scanner_name", table_name="scan_results")
    op.drop_index("ix_scan_results_inv_created", table_name="scan_results")
    op.drop_index("ix_refresh_tokens_active_expires", table_name="refresh_tokens")

    op.alter_column(
        "refresh_tokens",
        "token_hash",
        existing_type=sa.String(128),
        type_=sa.String(64),
        nullable=False,
    )
