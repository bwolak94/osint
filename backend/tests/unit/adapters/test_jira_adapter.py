"""Tests for Jira adapter."""

import asyncio
from unittest.mock import MagicMock, patch


class TestJiraAdapter:
    def test_test_connection_no_url(self) -> None:
        from src.adapters.integrations.jira_adapter import JiraAdapter

        with patch("src.adapters.integrations.jira_adapter.get_settings") as mock:
            mock.return_value = MagicMock(
                jira_url="", jira_email="", jira_api_token="", jira_project_key=""
            )
            adapter = JiraAdapter()
            result = asyncio.get_event_loop().run_until_complete(adapter.test_connection())
        assert result["connected"] is False

    def test_test_connection_with_url(self) -> None:
        from src.adapters.integrations.jira_adapter import JiraAdapter

        with patch("src.adapters.integrations.jira_adapter.get_settings") as mock:
            mock.return_value = MagicMock(
                jira_url="https://jira.example.com", jira_project_key="OSINT"
            )
            adapter = JiraAdapter()
            result = asyncio.get_event_loop().run_until_complete(adapter.test_connection())
        assert result["connected"] is True
        assert result["project"] == "OSINT"
