"""Tests for QdrantHybridSearcher — hybrid search with RRF fusion."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.adapters.qdrant.search import QdrantHybridSearcher


def _make_point(score: float, payload: dict) -> MagicMock:
    point = MagicMock()
    point.score = score
    point.payload = payload
    return point


def _make_searcher(points: list | None = None) -> tuple[QdrantHybridSearcher, AsyncMock]:
    client = AsyncMock()

    query_result = MagicMock()
    query_result.points = points or []
    client.query_points.return_value = query_result

    dense_encoder = AsyncMock()
    dense_encoder.encode.return_value = [0.1] * 1536

    sparse_encoder = AsyncMock()
    sparse_encoder.encode_sparse.return_value = {
        "indices": [1, 2, 3],
        "values": [0.5, 0.3, 0.2],
    }

    searcher = QdrantHybridSearcher(
        client=client,
        dense_encoder=dense_encoder,
        sparse_encoder=sparse_encoder,
        user_id="u-test",
    )
    return searcher, client


class TestQdrantHybridSearcher:
    async def test_returns_empty_list_when_no_results(self) -> None:
        searcher, _ = _make_searcher(points=[])
        results = await searcher.retrieve("test query", top_k=5)
        assert results == []

    async def test_maps_points_to_retrieved_docs(self) -> None:
        point = _make_point(
            score=0.88,
            payload={
                "doc_id": "doc-1",
                "chunk_index": 0,
                "text": "Hello world",
                "source": "https://example.com",
                "tags": ["ai"],
            },
        )
        searcher, _ = _make_searcher(points=[point])
        results = await searcher.retrieve("hello", top_k=5)
        assert len(results) == 1
        doc = results[0]
        assert doc["doc_id"] == "doc-1"
        assert doc["score"] == pytest.approx(0.88)
        assert doc["text"] == "Hello world"
        assert "ai" in doc["tags"]

    async def test_query_points_called_with_rrf_fusion(self) -> None:
        searcher, client = _make_searcher()
        await searcher.retrieve("test", top_k=3)
        client.query_points.assert_called_once()
        call_kwargs = client.query_points.call_args[1]
        assert "rrf" in str(call_kwargs.get("query", "")).lower()

    async def test_user_filter_applied(self) -> None:
        searcher, client = _make_searcher()
        await searcher.retrieve("test", top_k=5)
        call_kwargs = client.query_points.call_args[1]
        # Filter must be present in prefetch entries
        prefetch = call_kwargs["prefetch"]
        assert len(prefetch) == 2
        assert all("filter" in p for p in prefetch)

    async def test_dense_encoder_called(self) -> None:
        searcher, _ = _make_searcher()
        await searcher.retrieve("encode this", top_k=5)
        searcher._dense_encoder.encode.assert_called_once_with("encode this")

    async def test_sparse_encoder_called(self) -> None:
        searcher, _ = _make_searcher()
        await searcher.retrieve("encode this sparse", top_k=5)
        searcher._sparse_encoder.encode_sparse.assert_called_once_with("encode this sparse")

    async def test_top_k_limit_passed(self) -> None:
        searcher, client = _make_searcher()
        await searcher.retrieve("query", top_k=7)
        call_kwargs = client.query_points.call_args[1]
        assert call_kwargs["limit"] == 7

    async def test_missing_payload_fields_defaulted(self) -> None:
        """Points with empty payload must not raise."""
        point = _make_point(score=0.5, payload={})
        searcher, _ = _make_searcher(points=[point])
        results = await searcher.retrieve("query", top_k=5)
        assert len(results) == 1
        assert results[0]["doc_id"] == ""
        assert results[0]["text"] == ""
        assert results[0]["tags"] == []
