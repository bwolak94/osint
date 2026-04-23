# ruff_mcp_stdio_ban.py
#
# This file documents the ruff lint rule that bans STDIO-based MCP transports.
#
# STDIO BANNED: RCE vulnerability (April 2026)
# -----------------------------------------------
# Using mcp.client.stdio (or any subprocess/pipe-based MCP transport) exposes
# the application to Remote Code Execution because a compromised or malicious
# MCP server can inject arbitrary commands into the host process via stdin/stdout.
#
# The ban is enforced via ruff's `banned-module-level-imports` configuration in
# pyproject.toml under [tool.ruff.lint.flake8-bugbear] / [tool.ruff.lint] section.
#
# Specifically, the following patterns are banned at import level:
#   - mcp.client.stdio
#   - mcp.server.stdio
#
# All MCP integrations MUST use HTTP/SSE transport exclusively.
# See: backend/src/adapters/mcp/client.py for the approved MCPClient base class.
#
# If you believe you have a legitimate use case for STDIO transport,
# raise a security review with the platform team before proceeding.
