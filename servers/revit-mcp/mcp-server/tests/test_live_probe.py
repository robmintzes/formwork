from __future__ import annotations

from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading
from typing import Any, Iterator

import pytest

import live_probe


TEST_SHA = "a" * 40


def _payload(tool: str) -> dict[str, Any]:
    data: dict[str, dict[str, Any]] = {
        "revit_health_ping": {
            "revit_version": "2026",
            "revit_build": "20260701",
            "pyrevit_version": "5.2",
            "document_open": True,
            "extension_identity": {
                "component": "pyrevit-extension",
                "sha": TEST_SHA,
                "short_sha": TEST_SHA[:8],
                "any_stale": False,
            },
        },
        "revit_project_info": {
            "title": "Example",
            "path": None,
            "is_workshared": False,
            "project_number": None,
            "project_name": None,
            "client_name": None,
            "project_address": None,
            "project_status": None,
            "issue_date": None,
        },
        "revit_project_levels": {"count": 0, "levels": []},
        "revit_project_worksets": {"workshared": False, "worksets": []},
        "revit_project_links": {"count": 0, "links": []},
    }
    return {
        "status": "ok",
        "tool": tool,
        "risk_class": "read_only",
        "document": {"title": "Example", "path": None, "is_workshared": False},
        "data": data[tool],
        "messages": [],
        "next_actions": [],
        "error": None,
    }


@contextmanager
def _routes_server() -> Iterator[str]:
    payloads = {
        "/example/health/": _payload("revit_health_ping"),
        "/example/project/info/": _payload("revit_project_info"),
        "/example/project/levels/": _payload("revit_project_levels"),
        "/example/project/worksets/": _payload("revit_project_worksets"),
        "/example/project/links/": _payload("revit_project_links"),
    }

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            body = json.dumps(payloads[self.path]).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: Any) -> None:
            return None

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield "http://127.0.0.1:{}/example".format(server.server_port)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


@pytest.mark.asyncio
async def test_probe_launches_main_over_stdio_lists_and_invokes_every_tool() -> None:
    with _routes_server() as base_url:
        results, catalog_valid, catalog_count = await live_probe._probe_tools(
            base_url, 2.0
        )

    assert catalog_valid is True
    assert catalog_count == len(live_probe.TOOLS)
    assert [result["requested_tool"] for result in results] == list(live_probe.TOOLS)
    assert all(result["invocation_ok"] for result in results)
    assert all(result["envelope_valid"] for result in results)
    health = results[0]
    assert health["extension_sha"] == TEST_SHA
    assert health["extension_any_stale"] is False
    assert health["server_sha"] is not None


def test_probe_contract_summary_rejects_nonfinite_data_without_retaining_it() -> None:
    payload = _payload("revit_project_levels")
    payload["data"] = {
        "count": 1,
        "levels": [
            {
                "name": "sensitive-level-name",
                "elevation_feet": float("inf"),
                "id": 1,
            }
        ],
    }

    summary = live_probe._assess_result(payload, "revit_project_levels")

    assert summary["envelope_valid"] is False
    assert "invalid_level_elevation" in summary["issues"]
    assert "sensitive-level-name" not in json.dumps(summary)


def test_probe_rejects_non_loopback_urls_and_invalid_timeout() -> None:
    assert live_probe._is_loopback_url("http://127.0.0.1:48884/example")
    assert not live_probe._is_loopback_url("http://192.0.2.1:48884/example")

    original = live_probe.os.environ.get("REVIT_ROUTES_TIMEOUT")
    try:
        for value in ("0", "nan", "inf", "120.1", "not-a-number"):
            live_probe.os.environ["REVIT_ROUTES_TIMEOUT"] = value
            assert live_probe._timeout_from_environment() is None
    finally:
        if original is None:
            live_probe.os.environ.pop("REVIT_ROUTES_TIMEOUT", None)
        else:
            live_probe.os.environ["REVIT_ROUTES_TIMEOUT"] = original
