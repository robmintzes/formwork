# tools/health.py
# MCP tool: revit_health_ping

from __future__ import annotations

from typing import Any

import build_identity
from app import mcp
from revit_client import RevitClient, RevitClientError, build_error_result

_EXT_SUMMARY_KEYS = ("component", "root", "branch", "short_sha", "any_stale")


def _extension_summary(data: dict[str, Any]) -> dict[str, Any]:
    ext = data.get("extension_identity")
    if not isinstance(ext, dict):
        return {"unreachable": True}
    return {k: ext.get(k) for k in _EXT_SUMMARY_KEYS if k in ext}


@mcp.tool()
async def revit_health_ping() -> dict[str, Any]:
    """
    Check whether Revit is open, pyRevit Routes is responding, and a project
    document is loaded.

    Use this tool first when you need to confirm the Revit bridge is reachable
    before making any other revit_ calls. Returns Revit version, pyRevit version,
    and document open/closed state. Also returns a 'build_identity' block with
    the repo root + short SHA of the running MCP server and loaded Revit
    extension.
    """
    client = RevitClient()
    try:
        response = await client.get("/health/")
        result = response.model_dump()
        result["build_identity"] = {
            "server": build_identity.summary(),
            "extension": _extension_summary(result.get("data", {})),
        }
        return result
    except RevitClientError as exc:
        result = build_error_result("revit_health_ping", exc)
        result["build_identity"] = {
            "server": build_identity.summary(),
            "extension": {"unreachable": True},
        }
        return result
