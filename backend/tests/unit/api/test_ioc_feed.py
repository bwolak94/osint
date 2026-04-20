"""Tests for IOC feed endpoints."""
import pytest
from unittest.mock import MagicMock


class TestIOCFeedEndpoints:
    @pytest.mark.asyncio
    async def test_get_ioc_feed(self):
        from src.api.v1.ioc_feed import get_ioc_feed
        mock_user = MagicMock()
        result = await get_ioc_feed(format="json", tlp=None, ioc_type=None, min_confidence=0.0, current_user=mock_user)
        assert result.total >= 1
        assert result.format == "json"

    @pytest.mark.asyncio
    async def test_ioc_feed_filter_by_tlp(self):
        from src.api.v1.ioc_feed import get_ioc_feed
        mock_user = MagicMock()
        result = await get_ioc_feed(format="json", tlp="red", ioc_type=None, min_confidence=0.0, current_user=mock_user)
        assert all(i.tlp == "red" for i in result.iocs)

    @pytest.mark.asyncio
    async def test_ioc_feed_filter_by_confidence(self):
        from src.api.v1.ioc_feed import get_ioc_feed
        mock_user = MagicMock()
        result = await get_ioc_feed(format="json", tlp=None, ioc_type=None, min_confidence=0.9, current_user=mock_user)
        assert all(i.confidence >= 0.9 for i in result.iocs)

    @pytest.mark.asyncio
    async def test_stix_bundle(self):
        from src.api.v1.ioc_feed import get_ioc_stix_bundle
        mock_user = MagicMock()
        result = await get_ioc_stix_bundle(current_user=mock_user)
        assert result["type"] == "bundle"
        assert result["spec_version"] == "2.1"
        assert len(result["objects"]) >= 1
