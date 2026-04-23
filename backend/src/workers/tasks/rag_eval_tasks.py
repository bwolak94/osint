"""Celery tasks for RAG evaluation pipeline.

Two tasks:
  - run_rag_evaluation_task: nightly full evaluation + drift check
  - check_rag_metric_drift_task: on-demand drift check only

Both are routed to the `light` queue (network-bound, not CPU-intensive).
"""

from __future__ import annotations

import structlog

from src.workers.celery_app import celery_app

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Helper: build runner with default dependencies
# ---------------------------------------------------------------------------


def _build_runner() -> object:
    """Construct RagEvalRunner with default adapter wiring.

    Returns the runner instance. Kept as a separate function so that
    individual components can be swapped in tests.
    """
    from src.adapters.rag_evaluation.dataset import EvalDataset
    from src.adapters.rag_evaluation.evaluators import (
        AnswerRelevanceEvaluator,
        ContextRecallEvaluator,
        FaithfulnessEvaluator,
    )
    from src.adapters.rag_evaluation.runner import RagEvalRunner

    # llm_judge=None → stub returns 0.0; inject a real judge at runtime via
    # environment-level factory or dependency override.
    evaluators = (
        FaithfulnessEvaluator(llm_judge=None),
        AnswerRelevanceEvaluator(llm_judge=None),
        ContextRecallEvaluator(llm_judge=None),
    )
    dataset = EvalDataset()

    # Retriever is imported lazily to avoid heavy imports at module load time.
    from src.adapters.rag.retriever import build_default_retriever  # type: ignore[import-not-found]

    retriever = build_default_retriever()
    return RagEvalRunner(retriever=retriever, evaluators=evaluators, dataset=dataset)


async def _default_alert(metric: str, baseline: float, current: float) -> None:
    """Default alert handler — structured log only.

    Replace with a real notification adapter (Slack, PagerDuty, etc.) in production.
    """
    logger.error(
        "rag_metric_drift_alert",
        metric=metric,
        baseline=round(baseline, 4),
        current=round(current, 4),
        drop_pct=round((baseline - current) / baseline * 100, 2) if baseline else 0,
    )


# ---------------------------------------------------------------------------
# Celery tasks
# ---------------------------------------------------------------------------


@celery_app.task(
    name="src.workers.tasks.rag_eval_tasks.run_rag_evaluation_task",
    queue="light",
    bind=True,
    max_retries=2,
    default_retry_delay=300,
)
def run_rag_evaluation_task(self: object) -> dict[str, float]:  # type: ignore[type-arg]
    """Nightly task: run full RAG evaluation and check for metric drift.

    Loads labelled examples, performs retrieval + LLM-as-a-Judge scoring,
    persists results, then triggers drift comparison against 7-day baseline.
    """
    import asyncio

    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
    from sqlalchemy.orm import sessionmaker

    from src.config import get_settings

    settings = get_settings()
    log = logger.bind(task="run_rag_evaluation_task")

    async def _run() -> dict[str, float]:
        engine = create_async_engine(settings.database_url, echo=False)
        async_session: sessionmaker[AsyncSession] = sessionmaker(  # type: ignore[type-arg]
            engine, class_=AsyncSession, expire_on_commit=False
        )

        runner = _build_runner()

        async with async_session() as session:
            log.info("rag_evaluation_started")
            current_scores: dict[str, float] = await runner.run_evaluation(session)  # type: ignore[union-attr]
            log.info("rag_evaluation_finished", scores=current_scores)

            await runner.check_metric_drift(  # type: ignore[union-attr]
                db_session=session,
                current_scores=current_scores,
                alert_fn=_default_alert,
            )

        await engine.dispose()
        return current_scores

    return asyncio.get_event_loop().run_until_complete(_run())


@celery_app.task(
    name="src.workers.tasks.rag_eval_tasks.check_rag_metric_drift_task",
    queue="light",
    bind=True,
    max_retries=2,
    default_retry_delay=120,
)
def check_rag_metric_drift_task(
    self: object,  # type: ignore[type-arg]
    current_scores: dict[str, float],
) -> None:
    """On-demand task: compare provided scores against 7-day baseline.

    Args:
        current_scores: Dict of metric_name → score from a recent evaluation run.
    """
    import asyncio

    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
    from sqlalchemy.orm import sessionmaker

    from src.config import get_settings

    settings = get_settings()
    log = logger.bind(task="check_rag_metric_drift_task")

    async def _run() -> None:
        engine = create_async_engine(settings.database_url, echo=False)
        async_session: sessionmaker[AsyncSession] = sessionmaker(  # type: ignore[type-arg]
            engine, class_=AsyncSession, expire_on_commit=False
        )
        runner = _build_runner()

        async with async_session() as session:
            log.info("drift_check_started", current_scores=current_scores)
            await runner.check_metric_drift(  # type: ignore[union-attr]
                db_session=session,
                current_scores=current_scores,
                alert_fn=_default_alert,
            )
            log.info("drift_check_complete")

        await engine.dispose()

    asyncio.get_event_loop().run_until_complete(_run())
