# app.py
# Owns the single MCPServer app instance.

from __future__ import annotations

from mcp.server import MCPServer

mcp = MCPServer(
    name="revit-mcp",
    instructions=(
        "Revit MCP gives you structured, read-only access to a live Revit session "
        "through pyRevit Routes. "
        "Always call revit_health_ping first to confirm Revit is reachable. "
        "All tools are read-only. Write tools are disabled."
    ),
)

import tools  # noqa: E402, F401


async def registered_tool_names() -> set[str]:
    """Return registered MCP tool names through the SDK's public API."""
    return {tool.name for tool in await mcp.list_tools()}
