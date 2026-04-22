"""Add osint_investigation_id to engagements for OSINT-Pentest integration

Revision ID: m3n4o5p6q7r8
Revises: l2m3n4o5p6q7
Create Date: 2026-04-22 03:00:00.000000

Adds osint_investigation_id (nullable UUID) column to the engagements table
so that a pentest engagement can be linked back to the OSINT investigation
from which it was derived. No FK constraint is added intentionally — the
investigations table lives in the OSINT module and may not always be present
in a standalone deployment.
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision = "m3n4o5p6q7r8"
down_revision = "l2m3n4o5p6q7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add osint_investigation_id to engagements if it does not already exist.
    # Using a try/except pattern so that re-running the migration on an already-
    # migrated database does not raise an error.
    with op.get_context().autocommit_block():
        op.execute(
            """
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = 'engagements'
                      AND column_name = 'osint_investigation_id'
                ) THEN
                    ALTER TABLE engagements
                        ADD COLUMN osint_investigation_id UUID NULL;

                    CREATE INDEX idx_engagements_osint
                        ON engagements (osint_investigation_id);
                END IF;
            END $$;
            """
        )


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'engagements'
                  AND column_name = 'osint_investigation_id'
            ) THEN
                DROP INDEX IF EXISTS idx_engagements_osint;
                ALTER TABLE engagements DROP COLUMN osint_investigation_id;
            END IF;
        END $$;
        """
    )
