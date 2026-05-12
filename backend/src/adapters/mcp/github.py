"""GitHub MCP client.

Uses HTTP/SSE transport only.
STDIO BANNED: RCE vulnerability (April 2026).

Read operations (list_issues, list_prs) are freely callable.
Write operations (create_comment, update_issue_status) require
Human-in-the-Loop approval: pass approved=True after obtaining explicit
user confirmation.
"""

from __future__ import annotations

from typing import Any

import structlog

from src.adapters.mcp.client import MCPClient, MCPWriteRequiresApprovalError

logger = structlog.get_logger(__name__)

# STDIO BANNED: RCE vulnerability (April 2026)
GITHUB_MCP_URL = "https://api.github.com/mcp/sse"


class GitHubMCPClient(MCPClient):
    """MCP client for GitHub.

    All write operations (create_comment, update_issue_status) require
    explicit HiL approval. Pass approved=True only after user confirms.

    Args:
        server_url: MCP server base URL (defaults to GitHub's SSE endpoint).
        token: GitHub Personal Access Token or OAuth token.
    """

    def __init__(
        self,
        server_url: str = GITHUB_MCP_URL,
        token: str | None = None,
    ) -> None:
        super().__init__(server_url=server_url, token=token)

    # ------------------------------------------------------------------
    # Read operations — no HiL required
    # ------------------------------------------------------------------

    async def list_issues(self, repo: str, state: str = "open") -> list[dict[str, Any]]:
        """List issues in the given repository (read-only).

        Args:
            repo: Repository in "owner/name" format.
            state: Issue state filter — "open", "closed", or "all".

        Returns:
            List of issue dicts from the MCP server.
        """
        result = await self.call_tool("github.listIssues", {"repo": repo, "state": state})
        issues: list[dict[str, Any]] = result.get("issues", [])
        logger.info("github_issues_listed", repo=repo, state=state, count=len(issues))
        return issues

    async def list_prs(self, repo: str, state: str = "open") -> list[dict[str, Any]]:
        """List pull requests in the given repository (read-only).

        Args:
            repo: Repository in "owner/name" format.
            state: PR state filter — "open", "closed", or "all".

        Returns:
            List of PR dicts from the MCP server.
        """
        result = await self.call_tool("github.listPRs", {"repo": repo, "state": state})
        prs: list[dict[str, Any]] = result.get("pull_requests", [])
        logger.info("github_prs_listed", repo=repo, state=state, count=len(prs))
        return prs

    # ------------------------------------------------------------------
    # Write operations — HiL approval required
    # ------------------------------------------------------------------

    async def create_comment(
        self,
        issue_id: int,
        body: str,
        *,
        approved: bool = False,
    ) -> dict[str, Any]:
        """Post a comment on a GitHub issue or pull request.

        WRITE OPERATION — requires Human-in-the-Loop approval.
        Pass approved=True only after the user has explicitly confirmed.

        Args:
            issue_id: Numeric issue or PR identifier.
            body: Markdown content of the comment.
            approved: Must be True; set only after user confirms.

        Returns:
            Created comment dict from the MCP server.

        Raises:
            MCPWriteRequiresApprovalError: If approved is False.
        """
        if not approved:
            raise MCPWriteRequiresApprovalError("create_comment")

        result = await self.call_tool("github.createComment", {"issue_id": issue_id, "body": body})
        logger.info("github_comment_created", issue_id=issue_id)
        return result

    async def update_issue_status(
        self,
        issue_id: int,
        status: str,
        *,
        approved: bool = False,
    ) -> dict[str, Any]:
        """Update the state/status of a GitHub issue.

        WRITE OPERATION — requires Human-in-the-Loop approval.
        Pass approved=True only after the user has explicitly confirmed.

        Args:
            issue_id: Numeric issue identifier.
            status: New status value (e.g. "open", "closed").
            approved: Must be True; set only after user confirms.

        Returns:
            Updated issue dict from the MCP server.

        Raises:
            MCPWriteRequiresApprovalError: If approved is False.
        """
        if not approved:
            raise MCPWriteRequiresApprovalError("update_issue_status")

        result = await self.call_tool(
            "github.updateIssueStatus", {"issue_id": issue_id, "status": status}
        )
        logger.info("github_issue_status_updated", issue_id=issue_id, status=status)
        return result
