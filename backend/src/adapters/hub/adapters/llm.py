"""LLM adapters for Hub news pipeline.

Implements LLMSummarizer and LLMCritic protocols by wrapping the existing
LLMAdapter (OpenAI / Anthropic). Both classes are constructed with an api_key
and provider string so they can be injected without importing global settings.
"""

from __future__ import annotations

import structlog

log = structlog.get_logger(__name__)

_SUMMARISE_SYSTEM = (
    "You are a concise news analyst. Summarise the article in 2-3 sentences, "
    "focusing on key facts, actors, and impact. Be factual and objective."
)

_CRITIQUE_SYSTEM = (
    "You are a summary quality evaluator. Given an article and its summary, "
    "score the summary from 0.0 to 1.0 on factual accuracy and completeness. "
    "Respond ONLY in JSON: {\"score\": <float>, \"feedback\": \"<str>\"}"
)


class LLMSummarizerImpl:
    """LLMSummarizer backed by the project's LLMAdapter.

    Implements: src.adapters.hub.agents.news.summary.LLMSummarizer
    """

    def __init__(self, api_key: str, provider: str = "openai", model: str = "gpt-4o-mini") -> None:
        self._api_key = api_key
        self._provider = provider
        self._model = model

    async def summarize(self, content: str, context: str = "") -> str:
        """Return a 2-3 sentence summary of *content*."""
        system = _SUMMARISE_SYSTEM
        if context:
            system += f"\n\nAdditional context for improvement:\n{context}"
        try:
            return await self._call(system, content)
        except Exception as exc:
            await log.awarning("llm_summarizer_error", error=str(exc))
            # Extractive fallback
            sentences = content.split(". ")
            return ". ".join(sentences[:2])[:300]

    async def _call(self, system: str, user_content: str) -> str:
        if self._provider == "anthropic":
            return await self._call_anthropic(system, user_content)
        return await self._call_openai(system, user_content)

    async def _call_openai(self, system: str, user_content: str) -> str:
        import openai  # noqa: PLC0415
        client = openai.AsyncOpenAI(api_key=self._api_key)
        response = await client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user_content},
            ],
            max_tokens=512,
            temperature=0.3,
        )
        return response.choices[0].message.content or ""

    async def _call_anthropic(self, system: str, user_content: str) -> str:
        import anthropic  # noqa: PLC0415
        client = anthropic.AsyncAnthropic(api_key=self._api_key)
        response = await client.messages.create(
            model=self._model,
            max_tokens=512,
            system=system,
            messages=[{"role": "user", "content": user_content}],
        )
        return response.content[0].text if response.content else ""


class LLMCriticImpl:
    """LLMCritic backed by the project's LLMAdapter.

    Implements: src.adapters.hub.agents.news.critic.LLMCritic
    """

    def __init__(self, api_key: str, provider: str = "openai", model: str = "gpt-4o-mini") -> None:
        self._api_key = api_key
        self._provider = provider
        self._model = model

    async def critique(self, content: str, summary: str) -> tuple[float, str]:
        """Score summary quality; return (score, feedback)."""
        user_content = f"Article:\n{content[:2000]}\n\nSummary:\n{summary}"
        try:
            raw = await self._call(_CRITIQUE_SYSTEM, user_content)
            return self._parse_response(raw)
        except Exception as exc:
            await log.awarning("llm_critic_error", error=str(exc))
            return 0.85, f"critique unavailable: {exc}"

    def _parse_response(self, raw: str) -> tuple[float, str]:
        import json  # noqa: PLC0415
        # Extract JSON from response (may have surrounding text)
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start >= 0 and end > start:
            try:
                data = json.loads(raw[start:end])
                score = float(data.get("score", 0.85))
                feedback = str(data.get("feedback", ""))
                return max(0.0, min(1.0, score)), feedback
            except (json.JSONDecodeError, ValueError):
                pass
        return 0.85, "could not parse critique response"

    async def _call(self, system: str, user_content: str) -> str:
        if self._provider == "anthropic":
            return await self._call_anthropic(system, user_content)
        return await self._call_openai(system, user_content)

    async def _call_openai(self, system: str, user_content: str) -> str:
        import openai  # noqa: PLC0415
        client = openai.AsyncOpenAI(api_key=self._api_key)
        response = await client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user_content},
            ],
            max_tokens=256,
            temperature=0.1,
            response_format={"type": "json_object"},
        )
        return response.choices[0].message.content or "{}"

    async def _call_anthropic(self, system: str, user_content: str) -> str:
        import anthropic  # noqa: PLC0415
        client = anthropic.AsyncAnthropic(api_key=self._api_key)
        response = await client.messages.create(
            model=self._model,
            max_tokens=256,
            system=system,
            messages=[{"role": "user", "content": user_content}],
        )
        return response.content[0].text if response.content else "{}"
