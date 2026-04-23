"""Notion MCP client.

Uses HTTP/SSE transport only.
STDIO BANNED: RCE vulnerability (April 2026).

Read operations (read_page, list_pages) are freely callable.
Write operations (create_page, update_page) require Human-in-the-Loop
approval: pass approved=True after obtaining explicit user confirmation.
"""

from __future__ import annotations

from typing import Any

import structlog

from src.adapters.mcp.client import MCPClient, MCPWriteRequiresApprovalError

logger = structlog.get_logger(__name__)

# STDIO BANNED: RCE vulnerability (April 2026)
NOTION_MCP_URL = "https://mcp.notion.so/sse"


class NotionMCPClient(MCPClient):
    """MCP client for Notion.

    All write operations (create_page, update_page) require explicit HiL
    approval. Pass approved=True only after the user confirms the action.

    Args:
        server_url: MCP server base URL (defaults to Notion's SSE endpoint).
        token: Notion integration token.
    """

    def __init__(
        self,
        server_url: str = NOTION_MCP_URL,
        token: str | None = None,
    ) -> None:
        super().__init__(server_url=server_url, token=token)

    # ------------------------------------------------------------------
    # Read operations — no HiL required
    # ------------------------------------------------------------------

    async def read_page(self, page_id: str) -> dict[str, Any]:
        """Retrieve a Notion page by ID (read-only).

        Args:
            page_id: Notion page UUID.

        Returns:
            Page properties and content dict from the MCP server.
        """
        result = await self.call_tool("notion.readPage", {"page_id": page_id})
        logger.info("notion_page_read", page_id=page_id)
        return result

    async def list_pages(self, database_id: str) -> list[dict[str, Any]]:
        """List pages in a Notion database (read-only).

        Args:
            database_id: Notion database UUID.

        Returns:
            List of page dicts from the MCP server.
        """
        result = await self.call_tool("notion.listPages", {"database_id": database_id})
        pages: list[dict[str, Any]] = result.get("pages", [])
        logger.info("notion_pages_listed", database_id=database_id, count=len(pages))
        return pages

    # ------------------------------------------------------------------
    # Write operations — HiL approval required
    # ------------------------------------------------------------------

    async def create_page(
        self,
        database_id: str,
        properties: dict[str, Any],
        content: str,
        *,
        approved: bool = False,
    ) -> dict[str, Any]:
        """Create a new page in a Notion database.

        WRITE OPERATION — requires Human-in-the-Loop approval.
        Pass approved=True only after the user has explicitly confirmed.

        Args:
            database_id: Parent database UUID.
            properties: Notion property values for the new page.
            content: Markdown or plain-text body content for the page.
            approved: Must be True; set only after user confirms.

        Returns:
            Created page dict from the MCP server.

        Raises:
            MCPWriteRequiresApprovalError: If approved is False.
        """
        if not approved:
            raise MCPWriteRequiresApprovalError("create_page")

        result = await self.call_tool(
            "notion.createPage",
            {"database_id": database_id, "properties": properties, "content": content},
        )
        logger.info("notion_page_created", database_id=database_id)
        return result

    async def update_page(
        self,
        page_id: str,
        changes: dict[str, Any],
        *,
        approved: bool = False,
    ) -> dict[str, Any]:
        """Update properties or content on an existing Notion page.

        WRITE OPERATION — requires Human-in-the-Loop approval.
        Pass approved=True only after the user has explicitly confirmed.

        Args:
            page_id: Notion page UUID to update.
            changes: Dict of property names → new values to apply.
            approved: Must be True; set only after user confirms.

        Returns:
            Updated page dict from the MCP server.

        Raises:
            MCPWriteRequiresApprovalError: If approved is False.
        """
        if not approved:
            raise MCPWriteRequiresApprovalError("update_page")

        result = await self.call_tool(
            "notion.updatePage",
            {"page_id": page_id, "changes": changes},
        )
        logger.info("notion_page_updated", page_id=page_id, changed_keys=list(changes.keys()))
        return result
