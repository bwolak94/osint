"""LLM adapter for chat and analysis features."""

from typing import Any, AsyncGenerator

import structlog

from src.config import get_settings

log = structlog.get_logger()


class LLMAdapter:
    """Unified adapter for LLM providers (OpenAI, Anthropic)."""

    SYSTEM_PROMPT = (
        "You are an expert OSINT analyst assistant embedded in an investigation platform. "
        "Help users analyze findings, suggest investigation strategies, identify patterns, "
        "and explain technical OSINT concepts. Be precise and actionable. "
        "When discussing findings, reference specific data points."
    )

    def __init__(self) -> None:
        self._settings = get_settings()

    async def chat(self, messages: list[dict[str, str]], context: str = "") -> str:
        """Send a chat request and return the full response."""
        provider = self._settings.llm_provider

        system = self.SYSTEM_PROMPT
        if context:
            system += f"\n\nInvestigation context:\n{context}"

        if provider == "anthropic":
            return await self._chat_anthropic(messages, system)
        return await self._chat_openai(messages, system)

    async def stream_chat(
        self, messages: list[dict[str, str]], context: str = ""
    ) -> AsyncGenerator[str, None]:
        """Stream chat response token by token."""
        provider = self._settings.llm_provider

        system = self.SYSTEM_PROMPT
        if context:
            system += f"\n\nInvestigation context:\n{context}"

        if provider == "anthropic":
            async for chunk in self._stream_anthropic(messages, system):
                yield chunk
        else:
            async for chunk in self._stream_openai(messages, system):
                yield chunk

    async def _chat_openai(self, messages: list[dict[str, str]], system: str) -> str:
        try:
            import openai

            client = openai.AsyncOpenAI(api_key=self._settings.openai_api_key)
            full_messages = [{"role": "system", "content": system}] + messages
            response = await client.chat.completions.create(
                model=self._settings.openai_model,
                messages=full_messages,
                max_tokens=self._settings.llm_max_tokens,
                temperature=self._settings.llm_temperature,
            )
            return response.choices[0].message.content or ""
        except ImportError:
            log.warning("openai package not installed")
            return "OpenAI package not installed. Configure LLM provider."
        except Exception as e:
            log.error("OpenAI chat error", error=str(e))
            return f"Error: {e}"

    async def _stream_openai(
        self, messages: list[dict[str, str]], system: str
    ) -> AsyncGenerator[str, None]:
        try:
            import openai

            client = openai.AsyncOpenAI(api_key=self._settings.openai_api_key)
            full_messages = [{"role": "system", "content": system}] + messages
            stream = await client.chat.completions.create(
                model=self._settings.openai_model,
                messages=full_messages,
                max_tokens=self._settings.llm_max_tokens,
                temperature=self._settings.llm_temperature,
                stream=True,
            )
            async for chunk in stream:
                delta = chunk.choices[0].delta
                if delta.content:
                    yield delta.content
        except ImportError:
            yield "OpenAI package not installed."
        except Exception as e:
            log.error("OpenAI stream error", error=str(e))
            yield f"Error: {e}"

    async def _chat_anthropic(self, messages: list[dict[str, str]], system: str) -> str:
        try:
            import anthropic

            client = anthropic.AsyncAnthropic(api_key=self._settings.anthropic_api_key)
            response = await client.messages.create(
                model=self._settings.anthropic_model,
                system=system,
                messages=messages,
                max_tokens=self._settings.llm_max_tokens,
                temperature=self._settings.llm_temperature,
            )
            return response.content[0].text if response.content else ""
        except ImportError:
            log.warning("anthropic package not installed")
            return "Anthropic package not installed. Configure LLM provider."
        except Exception as e:
            log.error("Anthropic chat error", error=str(e))
            return f"Error: {e}"

    async def _stream_anthropic(
        self, messages: list[dict[str, str]], system: str
    ) -> AsyncGenerator[str, None]:
        try:
            import anthropic

            client = anthropic.AsyncAnthropic(api_key=self._settings.anthropic_api_key)
            async with client.messages.stream(
                model=self._settings.anthropic_model,
                system=system,
                messages=messages,
                max_tokens=self._settings.llm_max_tokens,
                temperature=self._settings.llm_temperature,
            ) as stream:
                async for text in stream.text_stream:
                    yield text
        except ImportError:
            yield "Anthropic package not installed."
        except Exception as e:
            log.error("Anthropic stream error", error=str(e))
            yield f"Error: {e}"
