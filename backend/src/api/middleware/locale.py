"""Locale middleware — detects user language from cookie or Accept-Language header.

Resolution order:
  1. ``i18next`` cookie (set by the React i18next frontend)
  2. ``Accept-Language`` header (first 2 characters, e.g. "en" from "en-US,en;q=0.9")
  3. Default: "en"

The detected language is stored in ``request.state.lang`` for downstream use.
"""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

SUPPORTED_LANGS: frozenset[str] = frozenset({"en", "pl"})
DEFAULT_LANG: str = "en"


class LocaleMiddleware(BaseHTTPMiddleware):
    """Attach detected language to request.state.lang."""

    async def dispatch(self, request: Request, call_next: object) -> Response:
        # 1. Check i18next cookie
        lang_cookie = request.cookies.get("i18next", "")[:2]

        # 2. Fall back to Accept-Language header (first 2 chars)
        lang_header = request.headers.get("accept-language", "")[:2].lower()

        # 3. Resolve in order: cookie → header → default
        if lang_cookie in SUPPORTED_LANGS:
            lang = lang_cookie
        elif lang_header in SUPPORTED_LANGS:
            lang = lang_header
        else:
            lang = DEFAULT_LANG

        request.state.lang = lang

        response: Response = await call_next(request)  # type: ignore[arg-type]
        return response
