"""Real Tavily Search API adapter (wraps tavily-python SDK).

Uses HTTP transport — never STDIO.
Falls back gracefully when tavily-python is not installed.
"""

from __future__ import annotations

from typing import Any

import structlog

log = structlog.get_logger(__name__)


class TavilySearcherImpl:
    """Production Tavily searcher using tavily-python SDK.

    Args:
        api_key: Tavily API key from settings.
    """

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key
        self._client: Any = None
        try:
            from tavily import TavilyClient  # noqa: PLC0415
            self._client = TavilyClient(api_key=api_key)
        except ImportError:
            log.warning("tavily_not_installed", detail="pip install tavily-python")

    async def search(
        self,
        query: str,
        search_depth: str = "advanced",
        max_results: int = 10,
        include_images: bool = True,
    ) -> list[dict[str, Any]]:
        """Search Tavily and return raw result dicts.

        Note: Tavily SDK is sync — run in thread executor for async compatibility.
        p50 latency ~998ms — always show a spinner in the UI.
        """
        import asyncio

        if self._client is None:
            return []

        def _sync_search() -> list[dict[str, Any]]:
            response = self._client.search(
                query=query,
                search_depth=search_depth,
                max_results=max_results,
                include_images=include_images,
            )
            return response.get("results", [])

        try:
            loop = asyncio.get_event_loop()
            results = await loop.run_in_executor(None, _sync_search)
            await log.ainfo("tavily_search_done", query=query[:80], results=len(results))
            return results
        except Exception as exc:
            await log.aerror("tavily_search_error", query=query[:80], error=str(exc))
            return []
