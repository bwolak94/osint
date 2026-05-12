"""add performance indexes for common query patterns

Revision ID: 20260423000000
Revises: p6q7r8s9t0u1
Create Date: 2026-04-23 00:00:00.000000

"""
from alembic import op

# revision identifiers
revision = '20260423000000'
down_revision = 'p6q7r8s9t0u1'


def upgrade() -> None:
    # Use raw SQL with IF NOT EXISTS to be resilient to schema drift
    # investigations: owner_id (not user_id), status, created_at all exist
    op.execute("CREATE INDEX IF NOT EXISTS ix_investigations_status ON investigations (status)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_investigations_created_at ON investigations (created_at)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_investigations_owner_id ON investigations (owner_id)")

    # scan_results: scanner_name (not scanner_type)
    op.execute("CREATE INDEX IF NOT EXISTS ix_scan_results_investigation_id ON scan_results (investigation_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_scan_results_created_at ON scan_results (created_at)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_scan_results_scanner_name ON scan_results (scanner_name)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_scan_results_status ON scan_results (status)")

    # identities (not entities)
    op.execute("CREATE INDEX IF NOT EXISTS ix_identities_investigation_id ON identities (investigation_id)")

    # comments table exists
    op.execute("CREATE INDEX IF NOT EXISTS ix_comments_investigation_id ON comments (investigation_id)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_investigations_status")
    op.execute("DROP INDEX IF EXISTS ix_investigations_created_at")
    op.execute("DROP INDEX IF EXISTS ix_investigations_owner_id")
    op.execute("DROP INDEX IF EXISTS ix_scan_results_investigation_id")
    op.execute("DROP INDEX IF EXISTS ix_scan_results_created_at")
    op.execute("DROP INDEX IF EXISTS ix_scan_results_scanner_name")
    op.execute("DROP INDEX IF EXISTS ix_scan_results_status")
    op.execute("DROP INDEX IF EXISTS ix_identities_investigation_id")
    op.execute("DROP INDEX IF EXISTS ix_comments_investigation_id")
