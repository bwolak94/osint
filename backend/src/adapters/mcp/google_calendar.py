"""Google Calendar MCP client.

Uses HTTP/SSE transport only.
STDIO BANNED: RCE vulnerability (April 2026).

Read operations (list_events, get_free_slots) are freely callable.
Write operations (create_event, update_event, delete_event) require
Human-in-the-Loop approval: pass approved=True after obtaining explicit
user confirmation.
"""

from __future__ import annotations

from typing import Any

import structlog

from src.adapters.mcp.client import MCPClient, MCPWriteRequiresApprovalError

logger = structlog.get_logger(__name__)

# STDIO BANNED: RCE vulnerability (April 2026)
GOOGLE_CALENDAR_MCP_URL = "https://mcp.googleapis.com/calendar/sse"


class GoogleCalendarMCPClient(MCPClient):
    """MCP client for Google Calendar.

    All write operations (create/update/delete) require explicit HiL approval.
    Pass approved=True after confirming with the user.

    Args:
        server_url: MCP server base URL (defaults to Google's SSE endpoint).
        token: OAuth 2.0 Bearer token for the Google Calendar API.
    """

    def __init__(
        self,
        server_url: str = GOOGLE_CALENDAR_MCP_URL,
        token: str | None = None,
    ) -> None:
        super().__init__(server_url=server_url, token=token)

    # ------------------------------------------------------------------
    # Read operations — no HiL required
    # ------------------------------------------------------------------

    async def list_events(self, date_range_days: int = 7) -> list[dict[str, Any]]:
        """List calendar events within the next N days (read-only).

        Args:
            date_range_days: Number of days ahead to include in the query.

        Returns:
            List of event dicts from the MCP server.
        """
        result = await self.call_tool("calendar.listEvents", {"date_range_days": date_range_days})
        events: list[dict[str, Any]] = result.get("events", [])
        logger.info("calendar_events_listed", count=len(events), date_range_days=date_range_days)
        return events

    async def get_free_slots(self, duration_minutes: int) -> list[dict[str, Any]]:
        """Return available free time slots of the requested duration (read-only).

        Args:
            duration_minutes: Required slot length in minutes.

        Returns:
            List of free-slot dicts (start, end, etc.) from the MCP server.
        """
        result = await self.call_tool("calendar.getFreeSlots", {"duration_minutes": duration_minutes})
        slots: list[dict[str, Any]] = result.get("slots", [])
        logger.info("calendar_free_slots_fetched", count=len(slots), duration_minutes=duration_minutes)
        return slots

    # ------------------------------------------------------------------
    # Write operations — HiL approval required
    # ------------------------------------------------------------------

    async def create_event(
        self,
        title: str,
        start: str,
        end: str,
        description: str = "",
        *,
        approved: bool = False,
    ) -> dict[str, Any]:
        """Create a calendar event.

        WRITE OPERATION — requires Human-in-the-Loop approval.
        Pass approved=True only after the user has explicitly confirmed the action.

        Args:
            title: Event title/summary.
            start: ISO-8601 datetime string for event start.
            end: ISO-8601 datetime string for event end.
            description: Optional event description body.
            approved: Must be True; set only after user confirms.

        Returns:
            Created event dict from the MCP server.

        Raises:
            MCPWriteRequiresApprovalError: If approved is False.
        """
        if not approved:
            raise MCPWriteRequiresApprovalError("create_event")

        result = await self.call_tool(
            "calendar.createEvent",
            {"title": title, "start": start, "end": end, "description": description},
        )
        logger.info("calendar_event_created", title=title, start=start, end=end)
        return result

    async def update_event(
        self,
        event_id: str,
        *,
        approved: bool = False,
        **changes: Any,
    ) -> dict[str, Any]:
        """Update an existing calendar event.

        WRITE OPERATION — requires Human-in-the-Loop approval.
        Pass approved=True only after the user has explicitly confirmed.

        Args:
            event_id: Identifier of the event to update.
            approved: Must be True; set only after user confirms.
            **changes: Arbitrary fields to update (title, start, end, etc.).

        Returns:
            Updated event dict from the MCP server.

        Raises:
            MCPWriteRequiresApprovalError: If approved is False.
        """
        if not approved:
            raise MCPWriteRequiresApprovalError("update_event")

        result = await self.call_tool(
            "calendar.updateEvent",
            {"event_id": event_id, **changes},
        )
        logger.info("calendar_event_updated", event_id=event_id, changes=list(changes.keys()))
        return result

    async def delete_event(
        self,
        event_id: str,
        *,
        approved: bool = False,
    ) -> None:
        """Delete a calendar event.

        WRITE OPERATION — requires Human-in-the-Loop approval.
        Pass approved=True only after the user has explicitly confirmed.

        Args:
            event_id: Identifier of the event to delete.
            approved: Must be True; set only after user confirms.

        Raises:
            MCPWriteRequiresApprovalError: If approved is False.
        """
        if not approved:
            raise MCPWriteRequiresApprovalError("delete_event")

        await self.call_tool("calendar.deleteEvent", {"event_id": event_id})
        logger.info("calendar_event_deleted", event_id=event_id)
