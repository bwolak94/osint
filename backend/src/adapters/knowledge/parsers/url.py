"""URL parser — fetches and extracts plain text from a URL.

Primary path: injected URLFetcher (e.g. Tavily extract endpoint).
Fallback:     httpx GET + basic HTML tag stripping.
"""

from __future__ import annotations

import re
from typing import Protocol


class URLFetcher(Protocol):
    """Interface for URL content extraction (injected for testability)."""

    async def extract(self, url: str) -> str: ...


def _strip_html(html: str) -> str:
    """Remove HTML tags and decode common entities from a raw HTML string."""
    # Remove script and style blocks entirely
    text = re.sub(r"<(script|style)[^>]*>[\s\S]*?</\1>", "", html, flags=re.IGNORECASE)
    # Remove all remaining tags
    text = re.sub(r"<[^>]+>", " ", text)
    # Decode common HTML entities
    entities: dict[str, str] = {
        "&amp;": "&", "&lt;": "<", "&gt;": ">",
        "&quot;": '"', "&#39;": "'", "&nbsp;": " ",
    }
    for entity, char in entities.items():
        text = text.replace(entity, char)
    # Collapse whitespace
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


async def parse_url(url: str, fetcher: URLFetcher | None = None) -> str:
    """Fetch and extract plain text from a URL.

    Args:
        url:     The URL to fetch.
        fetcher: Injected URLFetcher (None → httpx GET + HTML stripping).

    Returns:
        Extracted plain text suitable for chunking.

    Raises:
        RuntimeError: If the HTTP request fails.
    """
    if fetcher is not None:
        return await fetcher.extract(url)

    # Fallback: httpx GET
    try:
        import httpx  # noqa: PLC0415
    except ImportError as exc:
        raise ImportError("httpx is required for URL parsing: pip install httpx") from exc

    async with httpx.AsyncClient(follow_redirects=True, timeout=15.0) as client:
        response = await client.get(url, headers={"User-Agent": "OSINTHub/2.0"})
        response.raise_for_status()
        content_type = response.headers.get("content-type", "")
        if "html" in content_type:
            return _strip_html(response.text)
        return response.text
