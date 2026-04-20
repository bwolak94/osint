"""Tests for the LLM adapter."""

import sys
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestLLMAdapter:
    async def test_chat_openai(self):
        """Chat should delegate to OpenAI when configured."""
        # Create a mock openai module
        mock_openai_module = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Test response"

        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
        mock_openai_module.AsyncOpenAI.return_value = mock_client

        with patch.dict(sys.modules, {"openai": mock_openai_module}):
            from src.adapters.ai.llm_adapter import LLMAdapter

            adapter = LLMAdapter()
            with patch("src.adapters.ai.llm_adapter.get_settings") as mock_settings:
                mock_settings.return_value = MagicMock(
                    llm_provider="openai",
                    openai_api_key="test-key",
                    openai_model="gpt-4o-mini",
                    llm_max_tokens=2048,
                    llm_temperature=0.7,
                )
                adapter._settings = mock_settings.return_value
                result = await adapter._chat_openai(
                    [{"role": "user", "content": "Hello"}],
                    "You are helpful."
                )

        assert result == "Test response"

    async def test_chat_delegates_to_provider(self):
        """Chat should call the correct provider based on settings."""
        from src.adapters.ai.llm_adapter import LLMAdapter

        adapter = LLMAdapter()

        with patch.object(adapter, "_chat_openai", new_callable=AsyncMock, return_value="openai response") as mock_openai:
            with patch("src.adapters.ai.llm_adapter.get_settings") as mock_settings:
                mock_settings.return_value = MagicMock(llm_provider="openai")
                adapter._settings = mock_settings.return_value
                result = await adapter.chat([{"role": "user", "content": "hi"}])

        assert result == "openai response"
        mock_openai.assert_awaited_once()

    async def test_chat_delegates_to_anthropic(self):
        """Chat should call Anthropic when provider is anthropic."""
        from src.adapters.ai.llm_adapter import LLMAdapter

        adapter = LLMAdapter()

        with patch.object(adapter, "_chat_anthropic", new_callable=AsyncMock, return_value="anthropic response") as mock_anthropic:
            with patch("src.adapters.ai.llm_adapter.get_settings") as mock_settings:
                mock_settings.return_value = MagicMock(llm_provider="anthropic")
                adapter._settings = mock_settings.return_value
                result = await adapter.chat([{"role": "user", "content": "hi"}])

        assert result == "anthropic response"
        mock_anthropic.assert_awaited_once()
