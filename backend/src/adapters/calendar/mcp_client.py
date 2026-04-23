"""MCP Calendar client — HTTP/SSE transport ONLY.

CRITICAL SECURITY NOTE:
  STDIO transport is permanently disabled. An RCE vulnerability in MCP STDIO
  was disclosed in April 2026. All MCP communication must use HTTP/SSE transport.

Falls back to mock data when mcp_endpoint is not configured (dev/test mode).

Design: all write operations (create_event) MUST only be called after
Human-in-the-Loop approval from the caller (enforced at calendar_agent level).
"""

from __future__ import annotations

from typing import TypedDict

import structlog

log = structlog.get_logger(__name__)


class MCPCalendarEvent(TypedDict, total=False):
    """A single calendar event from the MCP server."""

    id: str
    title: str
    start: str    # ISO 8601 datetime
    end: str      # ISO 8601 datetime
    description: str | None
    status: str   # "draft" | "confirmed" | "cancelled"


_MOCK_EVENTS: list[MCPCalendarEvent] = [
    MCPCalendarEvent(
        id="mock-1",
        title="Team standup",
        start="2026-04-22T09:00:00Z",
        end="2026-04-22T09:30:00Z",
        description="Daily team sync",
        status="confirmed",
    ),
    MCPCalendarEvent(
        id="mock-2",
        title="Sprint planning",
        start="2026-04-22T10:00:00Z",
        end="2026-04-22T12:00:00Z",
        description="Bi-weekly sprint planning",
        status="confirmed",
    ),
]


class CalendarMCPClient:
    """MCP HTTP/SSE client for calendar read/write operations.

    Args:
        endpoint: MCP server HTTP endpoint (None → mock mode).
    """

    def __init__(self, endpoint: str | None = None) -> None:
        if endpoint and endpoint.startswith("stdio:"):
            raise ValueError(
                "STDIO transport is disabled (RCE CVE April 2026). Use HTTP/SSE endpoint."
            )
        self._endpoint = endpoint

    async def list_events(self, date_range_days: int = 7) -> list[MCPCalendarEvent]:
        """List calendar events for the next N days.

        Returns mock data if no MCP endpoint is configured.
        """
        if self._endpoint is None:
            await log.ainfo("mcp_calendar_mock", operation="list_events")
            return list(_MOCK_EVENTS)

        try:
            import httpx  # noqa: PLC0415

            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{self._endpoint}/calendar/events",
                    json={"date_range_days": date_range_days},
                )
                response.raise_for_status()
                data = response.json()
                return [MCPCalendarEvent(**event) for event in data.get("events", [])]
        except Exception as exc:
            await log.aerror("mcp_calendar_error", operation="list_events", error=str(exc))
            return list(_MOCK_EVENTS)  # graceful fallback

    async def get_free_slots(self, duration_minutes: int) -> list[dict[str, str]]:
        """Return free time slots of the requested duration.

        Returns mock slots if no MCP endpoint is configured.
        """
        if self._endpoint is None:
            await log.ainfo("mcp_calendar_mock", operation="get_free_slots")
            return [
                {"start": "2026-04-23T09:00:00Z", "end": "2026-04-23T10:00:00Z"},
                {"start": "2026-04-23T14:00:00Z", "end": "2026-04-23T15:00:00Z"},
                {"start": "2026-04-24T10:00:00Z", "end": "2026-04-24T11:00:00Z"},
            ]

        try:
            import httpx  # noqa: PLC0415

            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{self._endpoint}/calendar/free-slots",
                    json={"duration_minutes": duration_minutes},
                )
                response.raise_for_status()
                return response.json().get("slots", [])
        except Exception as exc:
            await log.aerror("mcp_calendar_error", operation="get_free_slots", error=str(exc))
            return []

    async def create_event(self, event: MCPCalendarEvent) -> MCPCalendarEvent:
        """Create a calendar event via the MCP server.

        IMPORTANT: Caller MUST obtain HiL approval before calling this method.
        """
        if self._endpoint is None:
            await log.ainfo("mcp_calendar_mock", operation="create_event")
            return MCPCalendarEvent(
                id="mock-created",
                status="draft",
                **{k: v for k, v in event.items() if k not in ("id", "status")},
            )

        try:
            import httpx  # noqa: PLC0415

            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{self._endpoint}/calendar/events/create",
                    json=dict(event),
                )
                response.raise_for_status()
                return MCPCalendarEvent(**response.json())
        except Exception as exc:
            await log.aerror("mcp_calendar_error", operation="create_event", error=str(exc))
            raise
