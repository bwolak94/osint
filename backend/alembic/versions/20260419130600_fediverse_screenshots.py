"""Add screenshot placeholder - links stealer to supply chain chain

Revision ID: b2c3d4e5f6a2
Revises: a1b2c3d4e5f7
Create Date: 2026-04-19

This is a placeholder migration to maintain the alembic chain between
stealer_log_checks and supply_chain_scans.
"""

from alembic import op
import sqlalchemy as sa

revision = "b2c3d4e5f6a2"
down_revision = "a1b2c3d4e5f7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass  # Placeholder - chain link between stealer logs and supply chain


def downgrade() -> None:
    pass
