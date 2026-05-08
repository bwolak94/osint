"""merge migration heads

Revision ID: 20260428000000
Revises: 20260427000000, 20260423000000
Create Date: 2026-04-28 00:00:00.000000

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "20260428000000"
down_revision = ("20260427000000", "20260423000000")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
