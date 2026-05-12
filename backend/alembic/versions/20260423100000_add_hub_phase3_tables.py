"""Add Hub Phase 3 tables: hub_task_checkpoints, hub_episodic_memory, hub_rag_eval_dataset, hub_rag_eval_runs

Revision ID: o5p6q7r8s9t0
Revises: n4o5p6q7r8s9
Create Date: 2026-04-23 10:00:00.000000

Creates four new tables required by Hub Phase 3 features:
  - hub_task_checkpoints    PostgreSQL-backed state snapshots for HubAgentGraph crash recovery
  - hub_episodic_memory     Dismissed synergy signal records with SHA-256 context hash + cooldown
  - hub_rag_eval_dataset    Labelled Q&A examples for RAG quality evaluation
  - hub_rag_eval_runs       Aggregate metric scores per evaluation run (drift detection)
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "o5p6q7r8s9t0"
down_revision = "n4o5p6q7r8s9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # hub_task_checkpoints
    # PostgreSQL-backed HubState snapshots for crash recovery and HITL resume.
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS hub_task_checkpoints (
            id              VARCHAR(36)   PRIMARY KEY,
            task_id         VARCHAR(36)   NOT NULL,
            checkpoint_id   VARCHAR(36)   NOT NULL,
            step_name       VARCHAR(128)  NOT NULL,
            state_json      TEXT          NOT NULL,
            created_at      TIMESTAMPTZ   NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_hub_task_checkpoints_task_id "
        "ON hub_task_checkpoints (task_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_hub_task_checkpoints_created_at "
        "ON hub_task_checkpoints (created_at DESC)"
    )

    # ------------------------------------------------------------------
    # hub_episodic_memory
    # Dismissed synergy signal records; prevents re-surfacing within cooldown.
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS hub_episodic_memory (
            id              VARCHAR(36)   PRIMARY KEY,
            user_id         VARCHAR(255)  NOT NULL,
            event_type      VARCHAR(128)  NOT NULL,
            signal_id       VARCHAR(36)   NOT NULL,
            context_hash    VARCHAR(16)   NOT NULL,
            reason          VARCHAR(255)  NOT NULL DEFAULT 'user_dismissed',
            created_at      TIMESTAMPTZ   NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_hub_episodic_memory_user_id "
        "ON hub_episodic_memory (user_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_hub_episodic_memory_context_hash "
        "ON hub_episodic_memory (context_hash)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_hub_episodic_memory_created_at "
        "ON hub_episodic_memory (created_at DESC)"
    )

    # ------------------------------------------------------------------
    # hub_rag_eval_dataset
    # Labelled Q&A examples used by the nightly RAG evaluation runner.
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS hub_rag_eval_dataset (
            id               VARCHAR(36)   PRIMARY KEY,
            query            TEXT          NOT NULL,
            user_context     TEXT          NOT NULL DEFAULT '',
            expected_answer  TEXT          NOT NULL,
            source_doc_ids   JSONB         NOT NULL DEFAULT '[]',
            created_at       TIMESTAMPTZ   NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_hub_rag_eval_dataset_created_at "
        "ON hub_rag_eval_dataset (created_at DESC)"
    )

    # ------------------------------------------------------------------
    # hub_rag_eval_runs
    # Aggregate metric scores per evaluation run; used for drift detection.
    # Columns: faithfulness, answer_relevance, context_recall (0.0-1.0 floats).
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS hub_rag_eval_runs (
            id                VARCHAR(36)  PRIMARY KEY,
            run_at            TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
            faithfulness      FLOAT        NOT NULL DEFAULT 0.0,
            answer_relevance  FLOAT        NOT NULL DEFAULT 0.0,
            context_recall    FLOAT        NOT NULL DEFAULT 0.0,
            example_count     INTEGER      NOT NULL DEFAULT 0,
            metadata          JSONB        NOT NULL DEFAULT '{}'
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_hub_rag_eval_runs_run_at "
        "ON hub_rag_eval_runs (run_at DESC)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS hub_rag_eval_runs")
    op.execute("DROP TABLE IF EXISTS hub_rag_eval_dataset")
    op.execute("DROP TABLE IF EXISTS hub_episodic_memory")
    op.execute("DROP TABLE IF EXISTS hub_task_checkpoints")
