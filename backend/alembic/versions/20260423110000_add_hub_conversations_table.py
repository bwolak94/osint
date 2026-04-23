"""Add hub_conversations table for agent conversation history persistence

Revision ID: p6q7r8s9t0u1
Revises: o5p6q7r8s9t0
Create Date: 2026-04-23 11:00:00.000000

Stores completed Hub agent conversations (query + result + thoughts) so the
frontend can show a per-user history panel without hitting Redis (which has
a 1-hour TTL).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "p6q7r8s9t0u1"
down_revision = "o5p6q7r8s9t0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS hub_conversations (
            id              UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id         VARCHAR(256)  NOT NULL,
            task_id         VARCHAR(36)   NOT NULL,
            module          VARCHAR(64)   NOT NULL DEFAULT 'chat',
            query           TEXT          NOT NULL,
            result          TEXT,
            error           TEXT,
            thoughts        JSONB         NOT NULL DEFAULT '[]',
            result_metadata JSONB         NOT NULL DEFAULT '{}',
            created_at      TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
            completed_at    TIMESTAMPTZ,
            CONSTRAINT uq_hub_conversations_task_id UNIQUE (task_id)
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_hub_conversations_user_id "
        "ON hub_conversations (user_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_hub_conversations_completed_at "
        "ON hub_conversations (completed_at DESC)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS hub_conversations")
