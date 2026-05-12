"""RAG evaluation runner.

Orchestrates retrieval, multi-metric evaluation, and drift detection
across a labelled dataset of Q&A examples.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Awaitable, Callable
from typing import Any, Protocol

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters.rag_evaluation.dataset import EvalDataset
from src.adapters.rag_evaluation.evaluators import (
    AnswerRelevanceEvaluator,
    ContextRecallEvaluator,
    EvalExample,
    EvalResult,
    FaithfulnessEvaluator,
)

logger = structlog.get_logger(__name__)

# Drift threshold: alert when a metric drops more than this fraction vs baseline
_DRIFT_THRESHOLD = 0.05

# How many days of history to use for the baseline average
_BASELINE_DAYS = 7


# ---------------------------------------------------------------------------
# Retriever protocol
# ---------------------------------------------------------------------------


class Retriever(Protocol):
    """Protocol for RAG retriever implementations."""

    async def retrieve(self, query: str) -> tuple[str, list[str]]:
        """Return (generated_answer, list_of_context_doc_texts) for the query."""
        ...


# ---------------------------------------------------------------------------
# Alert function type
# ---------------------------------------------------------------------------

AlertFn = Callable[[str, float, float], Awaitable[None]]


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


class RagEvalRunner:
    """Runs the full RAG evaluation pipeline against a labelled dataset.

    All dependencies are injected (retriever, evaluators, dataset) so that
    the runner remains fully testable without live infrastructure.

    Args:
        retriever: Retriever implementation that returns (answer, docs).
        evaluators: Tuple of (faithfulness, answer_relevance, context_recall).
        dataset: EvalDataset instance for loading examples and storing results.
    """

    def __init__(
        self,
        retriever: Retriever,
        evaluators: tuple[
            FaithfulnessEvaluator,
            AnswerRelevanceEvaluator,
            ContextRecallEvaluator,
        ],
        dataset: EvalDataset,
    ) -> None:
        self._retriever = retriever
        self._faithfulness_eval, self._relevance_eval, self._recall_eval = evaluators
        self._dataset = dataset
        self._log = logger.bind(runner="RagEvalRunner")

    async def run_evaluation(self, db_session: AsyncSession) -> dict[str, float]:
        """Load examples, run retrieval + all three evaluators, return mean scores.

        Also persists the run results to hub_rag_eval_runs via the dataset adapter.

        Args:
            db_session: Active async SQLAlchemy session.

        Returns:
            Dict with keys faithfulness, answer_relevance, context_recall,
            and latency_ms (mean per example).
        """
        examples = await self._dataset.load_examples(db_session)
        if not examples:
            self._log.warning("no_eval_examples_found — skipping run")
            return {"faithfulness": 0.0, "answer_relevance": 0.0, "context_recall": 0.0, "latency_ms": 0.0}

        partial_results: list[EvalResult] = []

        for example in examples:
            result = await self._evaluate_single(example)
            partial_results.append(result)

        mean_scores = _mean_scores(partial_results)
        run_id = str(uuid.uuid4())
        await self._dataset.record_run(db_session, run_id, mean_scores)

        self._log.info(
            "rag_evaluation_complete",
            run_id=run_id,
            n_examples=len(examples),
            scores=mean_scores,
        )
        return mean_scores

    async def check_metric_drift(
        self,
        db_session: AsyncSession,
        current_scores: dict[str, float],
        alert_fn: AlertFn,
    ) -> None:
        """Compare current scores against 7-day baseline and alert on drops.

        Fetches recent runs from hub_rag_eval_runs, computes the mean of each
        metric over the last _BASELINE_DAYS days, and calls alert_fn for any
        metric that has dropped more than _DRIFT_THRESHOLD (5 %).

        Args:
            db_session: Active async SQLAlchemy session.
            current_scores: Output of run_evaluation for the current run.
            alert_fn: Async callable(metric_name, baseline_value, current_value).
        """
        from sqlalchemy import text

        stmt = text(
            """
            SELECT metrics
            FROM hub_rag_eval_runs
            WHERE evaluated_at >= NOW() - INTERVAL ':days days'
            ORDER BY evaluated_at DESC
            """.replace(":days days", f"{_BASELINE_DAYS} days")
        )
        result = await db_session.execute(stmt)
        rows = result.scalars().all()

        if not rows:
            self._log.info("no_baseline_runs_found — skipping drift check")
            return

        # Aggregate baseline per metric
        baseline_accum: dict[str, list[float]] = {}
        for metrics_json in rows:
            if not isinstance(metrics_json, dict):
                continue
            for metric, value in metrics_json.items():
                if isinstance(value, float | int):
                    baseline_accum.setdefault(metric, []).append(float(value))

        for metric, values in baseline_accum.items():
            if not values:
                continue
            baseline = sum(values) / len(values)
            current = current_scores.get(metric)
            if current is None:
                continue
            drop = baseline - current
            if baseline > 0 and (drop / baseline) > _DRIFT_THRESHOLD:
                self._log.warning(
                    "rag_metric_drift_detected",
                    metric=metric,
                    baseline=baseline,
                    current=current,
                    drop_pct=round(drop / baseline * 100, 2),
                )
                await alert_fn(metric, baseline, current)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _evaluate_single(self, example: EvalExample) -> EvalResult:
        t0 = time.monotonic()
        answer, docs = await self._retriever.retrieve(example["query"])
        reference = example["expected_answer"]

        faithfulness = await self._faithfulness_eval.evaluate(
            query=example["query"], answer=answer, docs=docs, reference=reference
        )
        answer_relevance = await self._relevance_eval.evaluate(
            query=example["query"], answer=answer, docs=docs, reference=reference
        )
        context_recall = await self._recall_eval.evaluate(
            query=example["query"], answer=answer, docs=docs, reference=reference
        )
        latency_ms = (time.monotonic() - t0) * 1000

        return EvalResult(
            faithfulness=faithfulness,
            answer_relevance=answer_relevance,
            context_recall=context_recall,
            latency_ms=latency_ms,
        )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _mean_scores(results: list[EvalResult]) -> dict[str, float]:
    """Compute per-metric means across all evaluation results."""
    if not results:
        return {"faithfulness": 0.0, "answer_relevance": 0.0, "context_recall": 0.0, "latency_ms": 0.0}

    keys: list[str] = ["faithfulness", "answer_relevance", "context_recall", "latency_ms"]
    return {
        key: sum(r[key] for r in results) / len(results)  # type: ignore[literal-required]
        for key in keys
    }
