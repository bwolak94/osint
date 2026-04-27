"""Add GIN indexes on JSONB columns for fast key-path queries.

Revision ID: 20260425110000
Revises: 20260425100000
Create Date: 2026-04-25 11:00:00.000000
"""

from alembic import op

revision = "20260425110000"
down_revision = "20260425100000"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # GIN index on investigations.seed_inputs — enables @> containment queries
    # e.g. WHERE seed_inputs @> '{"scheduled_rescan": {}}'
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_investigations_seed_inputs_gin "
        "ON investigations USING gin (seed_inputs jsonb_path_ops)"
    )

    # GIN index on scan_results.raw_data — enables fast key-existence checks
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_scan_results_raw_data_gin "
        "ON scan_results USING gin (raw_data jsonb_path_ops)"
    )

    # GIN index on identities.metadata — enables metadata field lookups
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_identities_metadata_gin "
        "ON identities USING gin (metadata jsonb_path_ops)"
    )

    # B-tree index on scan_results(investigation_id, scanner_name) for N+1-free list queries
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_scan_results_inv_scanner "
        "ON scan_results (investigation_id, scanner_name)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_investigations_seed_inputs_gin")
    op.execute("DROP INDEX IF EXISTS ix_scan_results_raw_data_gin")
    op.execute("DROP INDEX IF EXISTS ix_identities_metadata_gin")  # column: metadata
    op.execute("DROP INDEX IF EXISTS ix_scan_results_inv_scanner")
