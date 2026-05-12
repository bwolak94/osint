"""LLM-as-a-Judge evaluators for RAG pipeline quality assessment.

Implements Faithfulness, AnswerRelevance, and ContextRecall evaluators.
All evaluators accept an injected llm_judge (DIP) and stub _call_judge
returning 0.0 by default — a real LLM is injected at runtime.
"""

from __future__ import annotations

from typing import Any, Protocol, TypedDict

import structlog

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Dataset schema
# ---------------------------------------------------------------------------


class EvalExample(TypedDict):
    query: str
    user_context: str
    expected_answer: str
    source_doc_ids: list[str]


class EvalResult(TypedDict):
    faithfulness: float
    answer_relevance: float
    context_recall: float
    latency_ms: float


# ---------------------------------------------------------------------------
# LLM judge protocol
# ---------------------------------------------------------------------------


class LLMJudge(Protocol):
    """Protocol for an async LLM judge callable."""

    async def __call__(self, prompt: str) -> float:
        """Return a float score in [0, 1] for the given evaluation prompt."""
        ...


# ---------------------------------------------------------------------------
# Base evaluator
# ---------------------------------------------------------------------------


class BaseEvaluator:
    """Base class for LLM-as-a-Judge evaluators.

    Subclasses implement _build_prompt and call self._call_judge internally.
    A real LLM is injected via the llm_judge constructor argument; the
    default stub always returns 0.0 so tests can run without network access.
    """

    def __init__(self, llm_judge: LLMJudge | None = None) -> None:
        self._llm_judge = llm_judge
        self._log = logger.bind(evaluator=self.__class__.__name__)

    async def _call_judge(self, prompt: str) -> float:
        """Call the injected LLM judge, or return stub value 0.0."""
        if self._llm_judge is None:
            self._log.debug("llm_judge not injected — returning stub score 0.0")
            return 0.0
        return await self._llm_judge(prompt)

    def _build_prompt(self, **kwargs: Any) -> str:  # noqa: ANN401
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Faithfulness evaluator
# ---------------------------------------------------------------------------


class FaithfulnessEvaluator(BaseEvaluator):
    """Measures whether the answer is grounded in the retrieved documents.

    A faithful answer contains only claims that can be traced back to the
    retrieved context — it does not hallucinate facts.
    """

    def _build_prompt(self, query: str, answer: str, docs: list[str]) -> str:
        context_block = "\n---\n".join(docs)
        return (
            f"You are an expert evaluator.\n\n"
            f"Query: {query}\n\n"
            f"Retrieved context:\n{context_block}\n\n"
            f"Answer: {answer}\n\n"
            f"Rate how faithfully the answer is grounded in the retrieved context "
            f"on a scale from 0.0 (completely hallucinated) to 1.0 (fully grounded). "
            f"Respond with only a float number."
        )

    async def evaluate(
        self,
        query: str,
        answer: str,
        docs: list[str],
        reference: str | None = None,
    ) -> float:
        """Return faithfulness score in [0, 1]."""
        prompt = self._build_prompt(query=query, answer=answer, docs=docs)
        score = await self._call_judge(prompt)
        self._log.info("faithfulness evaluated", query=query[:80], score=score)
        return score


# ---------------------------------------------------------------------------
# Answer relevance evaluator
# ---------------------------------------------------------------------------


class AnswerRelevanceEvaluator(BaseEvaluator):
    """Measures whether the answer directly addresses the original query.

    An irrelevant answer might be factually correct but fail to respond to
    what the user actually asked.
    """

    def _build_prompt(self, query: str, answer: str) -> str:
        return (
            f"You are an expert evaluator.\n\n"
            f"Query: {query}\n\n"
            f"Answer: {answer}\n\n"
            f"Rate how directly and completely the answer addresses the query "
            f"on a scale from 0.0 (completely irrelevant) to 1.0 (perfectly relevant). "
            f"Respond with only a float number."
        )

    async def evaluate(
        self,
        query: str,
        answer: str,
        docs: list[str],
        reference: str | None = None,
    ) -> float:
        """Return answer relevance score in [0, 1]."""
        prompt = self._build_prompt(query=query, answer=answer)
        score = await self._call_judge(prompt)
        self._log.info("answer_relevance evaluated", query=query[:80], score=score)
        return score


# ---------------------------------------------------------------------------
# Context recall evaluator
# ---------------------------------------------------------------------------


class ContextRecallEvaluator(BaseEvaluator):
    """Measures how much of the expected answer is covered by retrieved docs.

    Requires a reference/expected answer to compute recall. If no reference
    is provided the score defaults to 0.0.
    """

    def _build_prompt(self, query: str, docs: list[str], reference: str) -> str:
        context_block = "\n---\n".join(docs)
        return (
            f"You are an expert evaluator.\n\n"
            f"Query: {query}\n\n"
            f"Expected answer: {reference}\n\n"
            f"Retrieved context:\n{context_block}\n\n"
            f"Rate how much of the expected answer is covered by the retrieved context "
            f"on a scale from 0.0 (none of the expected answer is supported) "
            f"to 1.0 (all of the expected answer is supported). "
            f"Respond with only a float number."
        )

    async def evaluate(
        self,
        query: str,
        answer: str,
        docs: list[str],
        reference: str | None = None,
    ) -> float:
        """Return context recall score in [0, 1]."""
        if reference is None:
            self._log.warning(
                "context_recall requires a reference answer — returning 0.0",
                query=query[:80],
            )
            return 0.0
        prompt = self._build_prompt(query=query, docs=docs, reference=reference)
        score = await self._call_judge(prompt)
        self._log.info("context_recall evaluated", query=query[:80], score=score)
        return score
