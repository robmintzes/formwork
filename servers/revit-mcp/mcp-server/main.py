# main.py
# Revit MCP - FastMCP server entry point.
#
# Transport modes:
#   stdio (default)            - for Claude Desktop, Cursor, and similar local clients
#   streamable-http            - for MCP Inspector, Codex CLI, and multi-client local use
#
# Usage:
#   stdio:           python main.py
#   streamable-http: python main.py --transport streamable-http

from __future__ import annotations

import argparse
import logging
import sys

import settings
from app import mcp, registered_tool_names

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("revit_mcp")

# Warn if write tools were enabled
if settings.ENABLE_WRITE_TOOLS:
    logger.warning(
        "ENABLE_WRITE_TOOLS is true. No write tools are implemented yet - "
        "this flag has no effect but should be false in all read-only deployments."
    )
else:
    logger.info("Write tools: disabled (ENABLE_WRITE_TOOLS=false).")

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Revit MCP server - AI-to-Revit bridge (read-only)"
    )
    parser.add_argument(
        "--transport",
        choices=["stdio", "streamable-http"],
        default="stdio",
        help="MCP transport mode. Use 'streamable-http' for MCP Inspector.",
    )
    args = parser.parse_args()

    if args.transport == "streamable-http":
        logger.info(
            "Starting Revit MCP server (streamable-http) on %s:%s%s",
            settings.MCP_HOST,
            settings.MCP_PORT,
            settings.MCP_STREAMABLE_HTTP_PATH,
        )
        mcp.run(transport="streamable-http")
    else:
        logger.info("Starting Revit MCP server (stdio).")
        mcp.run(transport="stdio")


if __name__ == "__main__":
    tool_names = registered_tool_names()
    if not tool_names:
        raise RuntimeError("No MCP tools are registered; refusing to start an empty server.")
    logger.info("Registered MCP tools: %s", ", ".join(sorted(tool_names)))
    main()
