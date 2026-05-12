"""News searcher agent — fetches raw articles via Tavily or returns mock data.

Design: TavilySearcher is injected (DIP). When None, returns deterministic
mock articles so the pipeline can be tested end-to-end without network calls.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Protocol
from urllib.parse import urlparse

import structlog

from src.adapters.hub.agents.news.state import NewsArticle, NewsState

log = structlog.get_logger(__name__)

# Dynamic dates — always relative to now so they don't become stale
_now = datetime.now(timezone.utc)


def _mock_articles() -> list[dict[str, Any]]:
    """Build mock articles with dates relative to the current time."""
    now = datetime.now(timezone.utc)
    return [
        {
            "url": "https://example.com/news/ai-breakthrough",
            "title": "AI Breakthrough Changes Industry",
            "content": "Scientists have developed a new AI model that outperforms previous benchmarks.",
            "published_date": (now - timedelta(hours=3)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "score": 0.9,
            "image": "https://example.com/news/ai-breakthrough/thumbnail.jpg",
        },
        {
            "url": "https://techcrunch.com/news/startup-funding",
            "title": "Startup Funding Hits Record High",
            "content": "Venture capital investment in AI startups reached an all-time high this quarter.",
            "published_date": (now - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "score": 0.8,
            "image": None,
        },
        {
            "url": "https://reuters.com/tech/regulation",
            "title": "New Tech Regulations Announced",
            "content": "Governments worldwide are introducing new regulations targeting AI companies.",
            "published_date": (now - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "score": 0.75,
            "image": "https://reuters.com/tech/regulation/cover.jpg",
        },
    ]


class TavilySearcher(Protocol):
    """Interface for Tavily web search (Phase 2: HTTP/SSE; Phase 3: streaming)."""

    async def search(
        self,
        query: str,
        search_depth: str,
        max_results: int,
        include_images: bool = True,
    ) -> list[dict[str, Any]]: ...


def _extract_domain(url: str) -> str:
    """Extract the registered domain name from a URL string."""
    try:
        parsed = urlparse(url)
        return parsed.netloc or url
    except Exception:
        return url


def _normalise_article(raw: dict[str, Any]) -> NewsArticle:
    """Convert a raw Tavily/mock result dict to a NewsArticle TypedDict."""
    url = str(raw.get("url", ""))
    # Tavily returns images under the "image" key (include_images=True, March 2026)
    image_url = raw.get("image") or raw.get("image_url") or ""
    return NewsArticle(
        id=str(uuid.uuid4()),
        url=url,
        title=str(raw.get("title", "")),
        content=str(raw.get("content", raw.get("snippet", ""))),
        published_at=str(raw.get("published_date", raw.get("published_at", ""))),
        source_domain=_extract_domain(url),
        image_url=str(image_url) if image_url else "",
        credibility_score=0.0,  # filled by validator
        is_duplicate=False,
        tags=[],
        relevance_score=0.0,
        summary="",
        critique_score=0.0,
        critique_feedback="",
        action_relevance_score=0.0,
    )


async def news_searcher_agent(
    state: NewsState,
    tavily_searcher: TavilySearcher | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Fetch raw news articles for the given query.

    Args:
        state:           Current NewsState.
        tavily_searcher: Injected TavilySearcher (None → mock articles).
        **kwargs:        Ignored — uniform agent signature.

    Returns:
        Partial NewsState update dict.
    """
    query = state.get("search_query", "")
    thoughts: list[str] = list(state.get("thoughts") or [])

    await log.ainfo("news_searcher_start", query=query[:80])
    thoughts.append(f"NewsSearcher: searching for '{query}'…")

    raw_results: list[dict[str, Any]]

    if tavily_searcher is None:
        thoughts.append("NewsSearcher: no searcher configured — returning mock articles.")
        raw_results = _mock_articles()
    else:
        try:
            raw_results = await tavily_searcher.search(
                query=query,
                search_depth="advanced",
                max_results=10,
                include_images=True,  # March 2026 Tavily feature — article thumbnails
            )
        except Exception as exc:
            await log.aerror("news_searcher_error", error=str(exc))
            thoughts.append(f"NewsSearcher: search failed — {exc}")
            return {
                "raw_results": [],
                "articles": [],
                "thoughts": thoughts,
                "current_step": "searcher",
                "error": str(exc),
            }

    articles = [_normalise_article(r) for r in raw_results]
    thoughts.append(f"NewsSearcher: fetched {len(articles)} article(s).")

    await log.ainfo("news_searcher_done", article_count=len(articles))

    return {
        "raw_results": raw_results,
        "articles": articles,
        "thoughts": thoughts,
        "current_step": "searcher",
        "error": None,
    }
