"""Tests for the Elasticsearch adapter."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from src.adapters.search.elasticsearch_store import ElasticsearchStore


@pytest.fixture
def es_store() -> ElasticsearchStore:
    with patch("src.adapters.search.elasticsearch_store.get_settings") as mock_settings:
        settings = MagicMock()
        settings.elasticsearch_url = "http://localhost:9200"
        settings.elasticsearch_index_prefix = "osint"
        settings.elasticsearch_username = ""
        settings.elasticsearch_password = ""
        mock_settings.return_value = settings
        store = ElasticsearchStore()
    return store


@pytest.fixture
def mock_client() -> AsyncMock:
    client = AsyncMock()
    client.indices = AsyncMock()
    return client


class TestElasticsearchStoreSearch:
    @pytest.mark.asyncio
    async def test_search_returns_results(self, es_store: ElasticsearchStore, mock_client: AsyncMock) -> None:
        es_store._client = mock_client
        mock_client.search.return_value = {
            "hits": {
                "total": {"value": 1},
                "hits": [
                    {
                        "_id": "abc-123",
                        "_index": "osint_investigations",
                        "_score": 1.5,
                        "_source": {"title": "Test investigation"},
                        "highlight": {"title": ["<em>Test</em> investigation"]},
                    }
                ],
            }
        }

        result = await es_store.search(query="Test")

        assert result["total"] == 1
        assert len(result["results"]) == 1
        assert result["results"][0]["id"] == "abc-123"
        assert result["results"][0]["score"] == 1.5
        assert result["results"][0]["highlights"]["title"] == ["<em>Test</em> investigation"]
        assert result["page"] == 1
        assert result["page_size"] == 20

    @pytest.mark.asyncio
    async def test_search_without_client_returns_empty(self, es_store: ElasticsearchStore) -> None:
        # _client stays None and import will fail in test env
        es_store._client = None

        with patch("src.adapters.search.elasticsearch_store.ElasticsearchStore._get_client", return_value=None):
            result = await es_store.search(query="anything")

        assert result["total"] == 0
        assert result["results"] == []

    @pytest.mark.asyncio
    async def test_search_with_owner_filter(self, es_store: ElasticsearchStore, mock_client: AsyncMock) -> None:
        es_store._client = mock_client
        owner_id = uuid4()
        mock_client.search.return_value = {"hits": {"total": {"value": 0}, "hits": []}}

        await es_store.search(query="test", owner_id=owner_id)

        call_args = mock_client.search.call_args
        body = call_args.kwargs["body"]
        must_clauses = body["query"]["bool"]["must"]
        assert len(must_clauses) == 2
        assert must_clauses[1] == {"term": {"owner_id": str(owner_id)}}


class TestElasticsearchStoreIndex:
    @pytest.mark.asyncio
    async def test_index_investigation_success(self, es_store: ElasticsearchStore, mock_client: AsyncMock) -> None:
        es_store._client = mock_client
        mock_client.index.return_value = {"result": "created"}

        inv_id = uuid4()
        result = await es_store.index_investigation(inv_id, {"title": "My investigation"})

        assert result is True
        mock_client.index.assert_awaited_once_with(
            index="osint_investigations",
            id=str(inv_id),
            document={"title": "My investigation"},
        )

    @pytest.mark.asyncio
    async def test_delete_investigation_success(self, es_store: ElasticsearchStore, mock_client: AsyncMock) -> None:
        es_store._client = mock_client
        mock_client.delete.return_value = {"result": "deleted"}

        inv_id = uuid4()
        result = await es_store.delete_investigation(inv_id)

        assert result is True
        mock_client.delete.assert_awaited_once_with(
            index="osint_investigations",
            id=str(inv_id),
            ignore=[404],
        )
