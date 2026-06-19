# app.py
# Owns the single FastMCP app instance.

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

import settings

mcp = FastMCP(
    name="revit-mcp",
    instructions=(
        "Revit MCP gives you structured, read-only access to a live Revit session "
        "through pyRevit Routes. "
        "Always call revit_health_ping first to confirm Revit is reachable. "
        "All tools are read-only. Write tools are disabled."
    ),
    host=settings.MCP_HOST,
    port=settings.MCP_PORT,
    streamable_http_path=settings.MCP_STREAMABLE_HTTP_PATH,
    json_response=settings.MCP_JSON_RESPONSE,
    stateless_http=settings.MCP_STATELESS_HTTP,
)

from starlette.requests import Request  # noqa: E402
from starlette.responses import JSONResponse  # noqa: E402

import build_identity  # noqa: E402
import tools  # noqa: E402, F401


# Plain HTTP health endpoint
@mcp.custom_route("/healthz", methods=["GET"])
async def healthz(request: Request) -> JSONResponse:
    return JSONResponse(build_identity.identity())


def registered_tool_names() -> set[str]:
    """Return registered MCP tool names for startup checks."""
    try:
        return {tool.name for tool in mcp._tool_manager.list_tools()}
    except AttributeError:
        return set(getattr(mcp, "_tools", {}).keys())
