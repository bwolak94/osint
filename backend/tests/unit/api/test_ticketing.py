"""Tests for ticketing endpoints."""

from unittest.mock import AsyncMock, MagicMock

import pytest


class TestTicketingEndpoints:
    @pytest.mark.asyncio
    async def test_thehive_test_connection(self) -> None:
        from src.api.v1.ticketing import test_thehive

        mock_thehive = AsyncMock()
        mock_thehive.test_connection = AsyncMock(return_value={"connected": False})
        mock_user = MagicMock()
        result = await test_thehive(current_user=mock_user, thehive=mock_thehive)
        assert result["connected"] is False

    @pytest.mark.asyncio
    async def test_jira_test_connection(self) -> None:
        from src.api.v1.ticketing import test_jira

        mock_jira = AsyncMock()
        mock_jira.test_connection = AsyncMock(return_value={"connected": False})
        mock_user = MagicMock()
        result = await test_jira(current_user=mock_user, jira=mock_jira)
        assert result["connected"] is False

    @pytest.mark.asyncio
    async def test_create_thehive_case(self) -> None:
        from src.api.v1.ticketing import TheHiveCaseRequest, create_thehive_case

        mock_thehive = AsyncMock()
        mock_thehive.create_case = AsyncMock(return_value={"status": "skipped"})
        mock_user = MagicMock()
        body = TheHiveCaseRequest(title="Test Case")
        result = await create_thehive_case(body=body, current_user=mock_user, thehive=mock_thehive)
        assert result["status"] == "skipped"

    @pytest.mark.asyncio
    async def test_create_jira_ticket(self) -> None:
        from src.api.v1.ticketing import JiraTicketRequest, create_jira_ticket

        mock_jira = AsyncMock()
        mock_jira.create_ticket = AsyncMock(return_value={"status": "skipped"})
        mock_user = MagicMock()
        body = JiraTicketRequest(summary="Test Ticket")
        result = await create_jira_ticket(body=body, current_user=mock_user, jira=mock_jira)
        assert result["status"] == "skipped"
