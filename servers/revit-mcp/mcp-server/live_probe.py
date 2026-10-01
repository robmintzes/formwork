"""Dedicated subprocess helper for redacted live MCP verification.

The helper launches ``main.py`` through the MCP SDK's stdio transport, verifies
the exact tool catalog, and invokes every expected read-only tool. Only safe
contract metadata crosses back to the outer verifier process.
"""

from __future__ import annotations

import argparse
import asyncio
import ipaddress
import json
import math
import os
from pathlib import Path
import platform
import sys
from typing import Any
from urllib.parse import urlsplit


_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from formwork_cli.revit_contract import assess_envelope  # noqa: E402


PROTOCOL = "formwork-live-probe-v1"
PREFIX = "FORMWORK_LIVE_PROBE_V1:"
TOOLS = (
    "revit_health_ping",
    "revit_project_info",
    "revit_project_levels",
    "revit_project_worksets",
    "revit_project_links",
)


def _is_loopback_url(value: str) -> bool:
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except (TypeError, ValueError):
        return False
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return False
    if port is None:
        return False
    if parsed.username is not None or parsed.password is not None:
        return False
    if parsed.query or parsed.fragment:
        return False
    if parsed.hostname.lower() == "localhost":
        return True
    try:
        return ipaddress.ip_address(parsed.hostname).is_loopback
    except ValueError:
        return False


def _assess_result(
    payload: Any, requested_tool: str, invocation_ok: bool = True
) -> dict[str, Any]:
    assessment = assess_envelope(payload, requested_tool)
    issues = list(assessment.issues)
    if not invocation_ok:
        issues.append("sdk_tool_error")

    result: dict[str, Any] = {
        "requested_tool": requested_tool,
        "observed_tool": (
            requested_tool
            if isinstance(payload, dict) and payload.get("tool") == requested_tool
            else None
        ),
        "risk_class": (
            "read_only"
            if isinstance(payload, dict) and payload.get("risk_class") == "read_only"
            else None
        ),
        "status": assessment.status,
        "error_code": assessment.error_code,
        "invocation_ok": invocation_ok,
        "envelope_valid": not issues,
        "issues": sorted(set(issues)),
    }
    if requested_tool == "revit_health_ping":
        result.update(
            extension_sha=assessment.extension_sha,
            extension_any_stale=assessment.extension_any_stale,
            server_sha=assessment.server_sha,
        )
    return result


def _failed_result(tool: str, issue: str) -> dict[str, Any]:
    return {
        "requested_tool": tool,
        "observed_tool": None,
        "risk_class": None,
        "status": None,
        "error_code": None,
        "invocation_ok": False,
        "envelope_valid": False,
        "issues": [issue],
    }


async def _probe_tools(
    base_url: str, timeout: float
) -> tuple[list[dict[str, Any]], bool, int]:
    """Launch the real server entry point over stdio and exercise its catalog."""
    from mcp import Client, StdioServerParameters, stdio_client

    server_dir = Path(__file__).resolve().parent
    parameters = StdioServerParameters(
        command=sys.executable,
        args=[str(server_dir / "main.py")],
        cwd=server_dir,
        env={
            "ENABLE_WRITE_TOOLS": "false",
            "MCP_HOST": "127.0.0.1",
            "PYTHONIOENCODING": "utf-8",
            "REVIT_ROUTES_BASE_URL": base_url.rstrip("/"),
            "REVIT_ROUTES_TIMEOUT": str(timeout),
        },
    )
    results: list[dict[str, Any]] = []
    catalog_valid = False
    catalog_count = 0
    try:
        # Server logs can contain route failures; discard them rather than
        # retaining domain text or allowing a temporary log to grow.
        with open(os.devnull, mode="w", encoding="utf-8") as server_log:
            transport = stdio_client(parameters, errlog=server_log)
            async with Client(
                transport,
                cache=None,
                read_timeout_seconds=timeout,
            ) as client:
                catalog = await client.list_tools()
                names = [tool.name for tool in catalog.tools]
                catalog_count = len(names)
                catalog_valid = (
                    catalog_count == len(TOOLS) and set(names) == set(TOOLS)
                )

                # Invoke all expected tools even when discovery is wrong so one
                # run captures the complete set of actionable failures.
                for tool in TOOLS:
                    try:
                        call_result = await client.call_tool(tool, {})
                        payload = call_result.structured_content
                        summary = _assess_result(
                            payload, tool, invocation_ok=not call_result.is_error
                        )
                        if not catalog_valid:
                            summary["envelope_valid"] = False
                            summary["issues"] = sorted(
                                set(summary["issues"] + ["tool_catalog_mismatch"])
                            )
                        results.append(summary)
                        del payload, call_result
                    except Exception:
                        results.append(_failed_result(tool, "tool_call_failed"))
    except Exception:
        return (
            [_failed_result(tool, "mcp_client_failed") for tool in TOOLS],
            False,
            catalog_count,
        )
    return results, catalog_valid, catalog_count


def _emit(
    results: list[dict[str, Any]],
    *,
    catalog_valid: bool,
    catalog_count: int,
    fatal_code: str | None = None,
) -> None:
    record: dict[str, Any] = {
        "protocol": PROTOCOL,
        "python_version": platform.python_version(),
        "catalog_valid": catalog_valid,
        "catalog_count": catalog_count,
        "results": results,
    }
    if fatal_code is not None:
        record["fatal_code"] = fatal_code
    print(PREFIX + json.dumps(record, sort_keys=True, separators=(",", ":")))


def _timeout_from_environment() -> float | None:
    try:
        timeout = float(os.environ.get("REVIT_ROUTES_TIMEOUT", "10"))
    except ValueError:
        return None
    if not math.isfinite(timeout) or timeout <= 0 or timeout > 120:
        return None
    return timeout


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the redacted live MCP probe.")
    parser.add_argument("--base-url", required=True)
    args = parser.parse_args(argv)
    if not _is_loopback_url(args.base_url):
        _emit(
            [_failed_result(tool, "non_loopback_url") for tool in TOOLS],
            catalog_valid=False,
            catalog_count=0,
            fatal_code="non_loopback_url",
        )
        return 0

    timeout = _timeout_from_environment()
    if timeout is None:
        _emit(
            [_failed_result(tool, "invalid_timeout") for tool in TOOLS],
            catalog_valid=False,
            catalog_count=0,
            fatal_code="invalid_timeout",
        )
        return 0

    try:
        results, catalog_valid, catalog_count = asyncio.run(
            _probe_tools(args.base_url, timeout)
        )
    except Exception:
        _emit(
            [_failed_result(tool, "probe_runtime_failed") for tool in TOOLS],
            catalog_valid=False,
            catalog_count=0,
            fatal_code="probe_runtime_failed",
        )
        return 0
    _emit(
        results,
        catalog_valid=catalog_valid,
        catalog_count=catalog_count,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
