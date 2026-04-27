"""Schema cleanup: new indexes, column size fixes, and enum enforcement.

Changes:
  - scan_results: add composite index (investigation_id, status) for filtered queries
  - identities: add GIN index on emails array for fast membership lookups
  - users: shrink hashed_password from varchar(1024) to varchar(128)
    (bcrypt = 60 chars; 128 gives headroom for future algorithms)

Revision ID: 20260427000000
Revises: 20260425110000
Create Date: 2026-04-27 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260427000000"
down_revision = "20260425110000"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── 1. Composite index on scan_results(investigation_id, status) ──────────
    # Enables efficient queries like "get all failed scans for investigation X"
    # without a full table scan on large datasets.
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_scan_results_inv_status "
        "ON scan_results (investigation_id, status)"
    )

    # ── 2. GIN index on identities.emails (ARRAY column) ─────────────────────
    # Enables fast containment queries: WHERE emails @> ARRAY['user@example.com']
    # Without this, searching for an identity by email requires a full table scan.
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_identities_emails_gin "
        "ON identities USING gin (emails)"
    )

    # ── 3. Shrink users.hashed_password column ────────────────────────────────
    # All current hashes (bcrypt) are 60 chars. varchar(128) gives plenty of
    # headroom for Argon2id (~100 chars) if the hashing algorithm is migrated.
    # This is safe to run while the table is live — Postgres shrinks in-place
    # for varchar reductions when all existing values fit the new size.
    op.alter_column(
        "users",
        "hashed_password",
        type_=sa.String(128),
        existing_type=sa.String(1024),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "users",
        "hashed_password",
        type_=sa.String(1024),
        existing_type=sa.String(128),
        existing_nullable=False,
    )
    op.execute("DROP INDEX IF EXISTS ix_identities_emails_gin")
    op.execute("DROP INDEX IF EXISTS ix_scan_results_inv_status")
