"""Tests for the full-text search API endpoint."""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.api.v1.search_fulltext import fulltext_search, SearchResponse
from src.adapters.search.elasticsearch_store import ElasticsearchStore


class TestFulltextSearchEndpoint:
    async def test_fulltext_search_returns_results(self) -> None:
        """fulltext_search should return results from ES store."""
        mock_es = AsyncMock(spec=ElasticsearchStore)
        mock_es.search.return_value = {
            "total": 1,
            "results": [
                {
                    "id": "abc-123",
                    "index": "osint_investigations",
                    "score": 1.5,
                    "source": {"title": "Test"},
                    "highlights": {},
                }
            ],
            "page": 1,
            "page_size": 20,
        }

        mock_user = MagicMock()
        mock_user.id = uuid4()

        result = await fulltext_search(
            q="test query",
            entity_types=None,
            page=1,
            page_size=20,
            current_user=mock_user,
            es=mock_es,
        )

        assert isinstance(result, SearchResponse)
        assert result.total == 1
        assert len(result.results) == 1
        assert result.page == 1
        mock_es.search.assert_awaited_once()

    async def test_fulltext_search_with_entity_type_filter(self) -> None:
        """fulltext_search should split entity_types CSV."""
        mock_es = AsyncMock(spec=ElasticsearchStore)
        mock_es.search.return_value = {"total": 0, "results": [], "page": 1, "page_size": 20}

        mock_user = MagicMock()
        mock_user.id = uuid4()

        await fulltext_search(
            q="test",
            entity_types="investigations,scan_results",
            page=1,
            page_size=20,
            current_user=mock_user,
            es=mock_es,
        )

        call_kwargs = mock_es.search.call_args.kwargs
        assert call_kwargs["entity_types"] == ["investigations", "scan_results"]

    async def test_fulltext_search_passes_owner_id(self) -> None:
        """fulltext_search should scope results to current user."""
        mock_es = AsyncMock(spec=ElasticsearchStore)
        mock_es.search.return_value = {"total": 0, "results": [], "page": 1, "page_size": 20}

        mock_user = MagicMock()
        user_id = uuid4()
        mock_user.id = user_id

        await fulltext_search(
            q="test",
            entity_types=None,
            page=1,
            page_size=20,
            current_user=mock_user,
            es=mock_es,
        )

        call_kwargs = mock_es.search.call_args.kwargs
        assert call_kwargs["owner_id"] == user_id
