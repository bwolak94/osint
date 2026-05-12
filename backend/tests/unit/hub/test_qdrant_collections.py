"""Tests for QdrantCollectionManager — collection lifecycle."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.adapters.qdrant.collections import (
    KNOWLEDGE_COLLECTION,
    QdrantCollectionManager,
)


def _mock_client(collection_names: list[str] | None = None) -> AsyncMock:
    """Build a mock AsyncQdrantClient."""
    client = AsyncMock()

    # Mock get_collections
    mock_collection = MagicMock()
    mock_collection.name = KNOWLEDGE_COLLECTION
    collections_response = MagicMock()
    collections_response.collections = (
        [mock_collection] if collection_names and KNOWLEDGE_COLLECTION in collection_names else []
    )
    client.get_collections.return_value = collections_response

    # Mock get_collection for collection_info
    info = MagicMock()
    info.vectors_count = 42
    info.status = "green"
    client.get_collection.return_value = info

    return client


class TestEnsureKnowledgeCollection:
    async def test_creates_collection_when_absent(self) -> None:
        client = _mock_client(collection_names=[])
        manager = QdrantCollectionManager(client)
        await manager.ensure_knowledge_collection()
        client.create_collection.assert_called_once()

    async def test_skips_creation_when_exists(self) -> None:
        client = _mock_client(collection_names=[KNOWLEDGE_COLLECTION])
        manager = QdrantCollectionManager(client)
        await manager.ensure_knowledge_collection()
        client.create_collection.assert_not_called()

    async def test_create_call_uses_correct_collection_name(self) -> None:
        client = _mock_client(collection_names=[])
        manager = QdrantCollectionManager(client)
        await manager.ensure_knowledge_collection()
        call_kwargs = client.create_collection.call_args[1]
        assert call_kwargs["collection_name"] == KNOWLEDGE_COLLECTION

    async def test_create_call_includes_dense_vector(self) -> None:
        client = _mock_client(collection_names=[])
        manager = QdrantCollectionManager(client)
        await manager.ensure_knowledge_collection()
        call_kwargs = client.create_collection.call_args[1]
        assert "dense" in call_kwargs["vectors_config"]

    async def test_create_call_includes_sparse_vector(self) -> None:
        client = _mock_client(collection_names=[])
        manager = QdrantCollectionManager(client)
        await manager.ensure_knowledge_collection()
        call_kwargs = client.create_collection.call_args[1]
        assert "sparse" in call_kwargs["sparse_vectors_config"]


class TestDeleteKnowledgeCollection:
    async def test_calls_delete(self) -> None:
        client = _mock_client()
        manager = QdrantCollectionManager(client)
        await manager.delete_knowledge_collection()
        client.delete_collection.assert_called_once_with(
            collection_name=KNOWLEDGE_COLLECTION
        )


class TestCollectionInfo:
    async def test_returns_name_count_status(self) -> None:
        client = _mock_client(collection_names=[KNOWLEDGE_COLLECTION])
        manager = QdrantCollectionManager(client)
        info = await manager.collection_info()
        assert info["name"] == KNOWLEDGE_COLLECTION
        assert info["vectors_count"] == 42
        assert "green" in str(info["status"])
