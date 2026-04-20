"""Tests for the chat API endpoints."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestChatEndpoint:
    async def test_chat_non_streaming(self):
        """Non-streaming chat should return ChatResponse."""
        from src.api.v1.chat import chat, ChatRequest, ChatMessage, ChatResponse

        mock_llm = AsyncMock()
        mock_llm.chat = AsyncMock(return_value="AI response text")

        mock_user = MagicMock()
        mock_user.id = "test-user"

        request = ChatRequest(
            messages=[ChatMessage(role="user", content="Hello")],
            stream=False,
        )

        with patch("src.config.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(llm_provider="openai", openai_model="gpt-4o-mini")
            result = await chat(body=request, current_user=mock_user, llm=mock_llm)

        assert isinstance(result, ChatResponse)
        assert result.content == "AI response text"

    async def test_chat_analyze_findings(self):
        """Analyze endpoint should format findings and return analysis."""
        from src.api.v1.chat import analyze_findings

        mock_llm = AsyncMock()
        mock_llm.chat = AsyncMock(return_value="Analysis result")

        mock_user = MagicMock()

        result = await analyze_findings(
            body={"findings": {"emails": ["test@example.com"]}, "question": "What do you see?"},
            current_user=mock_user,
            llm=mock_llm,
        )

        assert result["analysis"] == "Analysis result"
        mock_llm.chat.assert_awaited_once()
