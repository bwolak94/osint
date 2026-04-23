"""Tests for the knowledge base ingestion pipeline."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.adapters.knowledge.ingestion import _make_point_id, ingest_document


class TestMakePointId:
    def test_deterministic_for_same_inputs(self) -> None:
        id1 = _make_point_id("doc-abc", 0)
        id2 = _make_point_id("doc-abc", 0)
        assert id1 == id2

    def test_different_chunk_index_produces_different_id(self) -> None:
        id1 = _make_point_id("doc-abc", 0)
        id2 = _make_point_id("doc-abc", 1)
        assert id1 != id2

    def test_different_doc_id_produces_different_id(self) -> None:
        id1 = _make_point_id("doc-abc", 0)
        id2 = _make_point_id("doc-xyz", 0)
        assert id1 != id2

    def test_returns_valid_uuid_string(self) -> None:
        point_id = _make_point_id("doc-test", 5)
        # Should be parseable as UUID
        parsed = uuid.UUID(point_id)
        assert str(parsed) == point_id


class TestIngestDocumentMockMode:
    async def test_plain_text_ingestion_no_qdrant(self) -> None:
        result = await ingest_document(
            content="Hello world this is a test document with enough words.",
            source="test.txt",
            user_id="u-1",
            mime_type="text/plain",
        )
        assert result["doc_id"] != ""
        assert result["chunks_processed"] >= 1
        assert result["source"] == "test.txt"

    async def test_empty_content_returns_zero_chunks(self) -> None:
        result = await ingest_document(
            content="",
            source="empty.txt",
            user_id="u-1",
            mime_type="text/plain",
        )
        assert result["chunks_processed"] == 0

    async def test_markdown_content_ingested(self) -> None:
        md = "# Heading\n\nSome **important** content here for testing purposes."
        result = await ingest_document(
            content=md,
            source="doc.md",
            user_id="u-1",
            mime_type="text/markdown",
        )
        assert result["chunks_processed"] >= 1

    async def test_qdrant_client_called_with_points(self) -> None:
        mock_qdrant = AsyncMock()
        long_text = " ".join([f"word{i}" for i in range(600)])

        result = await ingest_document(
            content=long_text,
            source="big.txt",
            user_id="u-1",
            mime_type="text/plain",
            qdrant_client=mock_qdrant,
        )
        mock_qdrant.upsert.assert_awaited_once()
        call_kwargs = mock_qdrant.upsert.call_args[1]
        assert call_kwargs["collection_name"] == "knowledge"
        assert len(call_kwargs["points"]) >= 1

    async def test_minio_client_called_for_raw_storage(self) -> None:
        mock_minio = AsyncMock()
        result = await ingest_document(
            content="Some content for storage.",
            source="test.txt",
            user_id="u-1",
            mime_type="text/plain",
            minio_client=mock_minio,
        )
        mock_minio.put_object.assert_awaited_once()

    async def test_qdrant_error_propagates(self) -> None:
        mock_qdrant = AsyncMock()
        mock_qdrant.upsert.side_effect = RuntimeError("qdrant down")
        with pytest.raises(RuntimeError, match="qdrant down"):
            await ingest_document(
                content="test content for error handling",
                source="test.txt",
                user_id="u-1",
                mime_type="text/plain",
                qdrant_client=mock_qdrant,
            )

    async def test_minio_error_is_non_fatal(self) -> None:
        """MinIO failures should not abort ingestion — Qdrant is source of truth."""
        mock_qdrant = AsyncMock()
        mock_minio = AsyncMock()
        mock_minio.put_object.side_effect = RuntimeError("minio down")

        # Should not raise
        result = await ingest_document(
            content="content for minio error test",
            source="test.txt",
            user_id="u-1",
            mime_type="text/plain",
            qdrant_client=mock_qdrant,
            minio_client=mock_minio,
        )
        assert result["chunks_processed"] >= 1

    async def test_doc_id_is_unique_per_call(self) -> None:
        result1 = await ingest_document(
            content="content one two three", source="a.txt", user_id="u-1", mime_type="text/plain"
        )
        result2 = await ingest_document(
            content="content one two three", source="a.txt", user_id="u-1", mime_type="text/plain"
        )
        assert result1["doc_id"] != result2["doc_id"]
