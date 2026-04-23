"""Searcher agent — web research and knowledge-base retrieval.

Responsibilities:
- Accept query from Supervisor state
- Retrieve semantically relevant docs from Qdrant (via injected retriever)
- Produce a grounded, summarised result
- Emit Chain-of-Thought to thoughts list (streamed to UI)

Design: retriever is injected via kwargs (Dependency Inversion Principle).
Tests pass a mock retriever; production passes the real QdrantSearcher.
"""

from __future__ import annotations

from typing import Any, Protocol

import structlog

from src.adapters.hub.state import HubMessage, HubState, RetrievedDoc

log = structlog.get_logger(__name__)

_MAX_DOCS = 5
_MIN_SCORE = 0.60


class DocumentRetriever(Protocol):
    """Interface for semantic document retrieval (Phase 1: Qdrant hybrid search)."""

    async def retrieve(self, query: str, top_k: int) -> list[RetrievedDoc]: ...


def _format_context(docs: list[RetrievedDoc]) -> str:
    """Build a context string from retrieved document chunks."""
    if not docs:
        return "(No relevant documents found in knowledge base.)"
    parts = []
    for i, doc in enumerate(docs, 1):
        parts.append(f"[{i}] Source: {doc['source']}\n{doc['text']}")
    return "\n\n".join(parts)


def _build_answer(query: str, context: str) -> str:
    """Synthesise an answer from the retrieved context.

    Phase 1: Returns context-grounded answer template.
    Phase 3: Replace with LLM call (RAG answer generation).
    """
    return (
        f"Based on the knowledge base, here is what I found about '{query}':\n\n"
        f"{context}"
    )


async def searcher_agent(
    state: HubState,
    retriever: DocumentRetriever | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Retrieve relevant documents and synthesise an answer.

    Args:
        state:     Shared HubState.
        retriever: Injected DocumentRetriever (real or mock).
        **kwargs:  Ignored — allows uniform agent signature.

    Returns:
        Partial HubState update dict.
    """
    task_id = state.get("task_id", "?")
    query = state.get("query", "")

    await log.ainfo("searcher_start", task_id=task_id)

    thoughts: list[str] = list(state.get("thoughts") or [])
    messages: list[HubMessage] = list(state.get("messages") or [])

    # ── Retrieval ──────────────────────────────────────────────────────────
    thoughts.append(f"Searcher: retrieving top-{_MAX_DOCS} documents for query…")

    docs: list[RetrievedDoc] = []
    if retriever is not None:
        try:
            raw_docs = await retriever.retrieve(query, top_k=_MAX_DOCS)
            docs = [d for d in raw_docs if d.get("score", 0.0) >= _MIN_SCORE]
        except Exception as exc:
            await log.awarning("retriever_error", task_id=task_id, error=str(exc))
            thoughts.append(f"Searcher: retrieval error — {exc}. Proceeding without context.")

    thoughts.append(f"Searcher: {len(docs)} relevant documents found (score ≥ {_MIN_SCORE}).")

    # ── Answer synthesis ───────────────────────────────────────────────────
    context = _format_context(docs)
    answer = _build_answer(query, context)
    thoughts.append("Searcher: answer synthesised from retrieved context.")

    messages.append(HubMessage(role="assistant", content=answer, name="searcher"))

    await log.ainfo("searcher_done", task_id=task_id, docs_used=len(docs))

    return {
        "retrieved_docs": docs,
        "result": answer,
        "result_metadata": {"agent": "searcher", "docs_retrieved": len(docs)},
        "thoughts": thoughts,
        "messages": messages,
        "current_agent": "done",
        "completed": True,
        "error": None,
    }
