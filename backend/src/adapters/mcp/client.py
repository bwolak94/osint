"""Base MCP client using HTTP/SSE transport only.

STDIO BANNED: RCE vulnerability (April 2026).
All MCP communication must use HTTP/SSE transport. Never use mcp.client.stdio
or any subprocess-based transport — this is a hard security requirement.

Write operations (create/update/delete) require Human-in-the-Loop (HiL)
approval before being called. Callers must pass approved=True explicitly.
"""

from __future__ import annotations

from typing import Any

import httpx
import structlog

logger = structlog.get_logger(__name__)

# STDIO BANNED: RCE vulnerability (April 2026)
# Do NOT import or use mcp.client.stdio, subprocess, or any stdio-based transport.


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class MCPError(Exception):
    """Raised when an MCP server returns a non-2xx response."""

    def __init__(self, status_code: int, message: str) -> None:
        self.status_code = status_code
        self.message = message
        super().__init__(f"MCPError {status_code}: {message}")


class MCPWriteRequiresApprovalError(Exception):
    """Raised when a write operation is called without Human-in-the-Loop approval.

    All create/update/delete operations on MCP resources require an explicit
    approved=True argument as a guard against accidental or automated writes.
    """

    def __init__(self, operation: str) -> None:
        self.operation = operation
        super().__init__(
            f"MCP write operation '{operation}' requires Human-in-the-Loop approval. "
            f"Pass approved=True after obtaining explicit user confirmation."
        )


# ---------------------------------------------------------------------------
# Base client
# ---------------------------------------------------------------------------


class MCPClient:
    """HTTP/SSE MCP client — STDIO transport is banned (RCE vulnerability, April 2026).

    All write operations (create/update/delete) require HiL approval before calling.
    Concrete subclasses should enforce this via MCPWriteRequiresApprovalError.

    Args:
        server_url: Base URL of the MCP server (HTTP or HTTPS endpoint).
        token: Optional Bearer token for Authorization header.
    """

    def __init__(self, server_url: str, token: str | None = None) -> None:
        self._server_url = server_url.rstrip("/")
        self._token = token
        self._log = logger.bind(mcp_client=self.__class__.__name__, server_url=self._server_url)

    def _build_headers(self) -> dict[str, str]:
        headers: dict[str, str] = {"Content-Type": "application/json", "Accept": "application/json"}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        return headers

    async def call_tool(self, tool: str, params: dict[str, Any]) -> dict[str, Any]:
        """Call an MCP tool via HTTP/SSE transport.

        Posts the params as a JSON body to {server_url}/tools/{tool}.

        Args:
            tool: Name of the MCP tool to invoke.
            params: Tool-specific parameters as a dict.

        Returns:
            Parsed JSON response body as a dict.

        Raises:
            MCPError: If the server returns a non-2xx status code.
        """
        url = f"{self._server_url}/tools/{tool}"
        self._log.debug("mcp_tool_call", tool=tool, url=url)

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=params, headers=self._build_headers())

        if not response.is_success:
            self._log.error(
                "mcp_tool_call_failed",
                tool=tool,
                status_code=response.status_code,
                body=response.text[:500],
            )
            raise MCPError(status_code=response.status_code, message=response.text)

        self._log.info("mcp_tool_call_success", tool=tool, status_code=response.status_code)
        return response.json()  # type: ignore[no-any-return]

    async def list_tools(self) -> list[str]:
        """List available tool names from the MCP server.

        Sends GET {server_url}/tools and returns the list of tool names.

        Returns:
            Sorted list of available tool name strings.

        Raises:
            MCPError: If the server returns a non-2xx status code.
        """
        url = f"{self._server_url}/tools"
        self._log.debug("mcp_list_tools", url=url)

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, headers=self._build_headers())

        if not response.is_success:
            raise MCPError(status_code=response.status_code, message=response.text)

        data: dict[str, Any] = response.json()
        tools: list[str] = data.get("tools", [])
        self._log.info("mcp_list_tools_success", count=len(tools))
        return tools
