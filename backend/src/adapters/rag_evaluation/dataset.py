"""Dataset management for RAG evaluation.

Provides EvalDataset for persisting evaluation examples and run results
to the hub_rag_eval_dataset and hub_rag_eval_runs tables respectively.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters.rag_evaluation.evaluators import EvalExample

logger = structlog.get_logger(__name__)


class EvalDataset:
    """Manages RAG evaluation dataset storage and retrieval.

    All persistence is performed against two tables:
      - hub_rag_eval_dataset: individual labelled Q&A examples
      - hub_rag_eval_runs: aggregate metric scores per evaluation run
    """

    # ------------------------------------------------------------------
    # Dataset example management
    # ------------------------------------------------------------------

    async def add_example(
        self,
        db_session: AsyncSession,
        example: EvalExample,
    ) -> str:
        """Insert a labelled evaluation example and return its UUID.

        Args:
            db_session: Active async SQLAlchemy session.
            example: Typed dict containing query, context, expected answer,
                     and source document ids.

        Returns:
            String UUID of the inserted record.
        """
        example_id = str(uuid.uuid4())
        now = datetime.now(UTC)

        stmt = text(
            """
            INSERT INTO hub_rag_eval_dataset
                (id, query, user_context, expected_answer, source_doc_ids, created_at)
            VALUES
                (:id, :query, :user_context, :expected_answer,
                 :source_doc_ids::jsonb, :created_at)
            """
        )
        await db_session.execute(
            stmt,
            {
                "id": example_id,
                "query": example["query"],
                "user_context": example["user_context"],
                "expected_answer": example["expected_answer"],
                "source_doc_ids": _json_dumps(example["source_doc_ids"]),
                "created_at": now,
            },
        )
        await db_session.commit()

        logger.info("rag_eval_example_added", example_id=example_id)
        return example_id

    async def load_examples(
        self,
        db_session: AsyncSession,
        limit: int = 100,
    ) -> list[EvalExample]:
        """Load evaluation examples ordered by creation time (newest last).

        Args:
            db_session: Active async SQLAlchemy session.
            limit: Maximum number of rows to return.

        Returns:
            List of EvalExample typed dicts.
        """
        stmt = text(
            """
            SELECT query, user_context, expected_answer, source_doc_ids
            FROM hub_rag_eval_dataset
            ORDER BY created_at ASC
            LIMIT :limit
            """
        )
        result = await db_session.execute(stmt, {"limit": limit})
        rows = result.mappings().all()

        examples: list[EvalExample] = [
            EvalExample(
                query=row["query"],
                user_context=row["user_context"],
                expected_answer=row["expected_answer"],
                source_doc_ids=row["source_doc_ids"] or [],
            )
            for row in rows
        ]
        logger.info("rag_eval_examples_loaded", count=len(examples))
        return examples

    # ------------------------------------------------------------------
    # Run result persistence
    # ------------------------------------------------------------------

    async def record_run(
        self,
        db_session: AsyncSession,
        run_id: str,
        results: dict[str, float],
    ) -> None:
        """Persist aggregate metric scores for a single evaluation run.

        Args:
            db_session: Active async SQLAlchemy session.
            run_id: Caller-supplied run identifier (UUID string recommended).
            results: Mapping of metric name → mean score for this run.
        """
        now = datetime.now(UTC)

        stmt = text(
            """
            INSERT INTO hub_rag_eval_runs
                (run_id, metrics, evaluated_at)
            VALUES
                (:run_id, :metrics::jsonb, :evaluated_at)
            ON CONFLICT (run_id) DO UPDATE
                SET metrics = EXCLUDED.metrics,
                    evaluated_at = EXCLUDED.evaluated_at
            """
        )
        await db_session.execute(
            stmt,
            {
                "run_id": run_id,
                "metrics": _json_dumps(results),
                "evaluated_at": now,
            },
        )
        await db_session.commit()

        logger.info("rag_eval_run_recorded", run_id=run_id, metrics=results)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _json_dumps(value: Any) -> str:  # noqa: ANN401
    """Serialize a Python object to a JSON string for PostgreSQL jsonb columns."""
    import json

    return json.dumps(value)
