"""Tests for the NL query API endpoints."""

import pytest
from unittest.mock import MagicMock


class TestNLQueryEndpoint:
    async def test_parse_query_endpoint(self) -> None:
        """parse_query should return structured results."""
        from src.api.v1.nl_query import parse_query, NLQueryRequest

        mock_user = MagicMock()
        request = NLQueryRequest(query="Check john@example.com for breaches")
        result = await parse_query(body=request, current_user=mock_user)

        assert result.raw_query == "Check john@example.com for breaches"
        assert len(result.seed_inputs) >= 1
        assert result.intent == "breach"

    async def test_extract_entities_endpoint(self) -> None:
        """extract_entities should return entity list."""
        from src.api.v1.nl_query import extract_entities, EntityExtractionRequest

        mock_user = MagicMock()
        request = EntityExtractionRequest(text="Email: test@example.com, IP: 8.8.8.8")
        result = await extract_entities(body=request, current_user=mock_user)

        assert result.count >= 2
        types = {e["input_type"] for e in result.entities}
        assert "email" in types
        assert "ip_address" in types
