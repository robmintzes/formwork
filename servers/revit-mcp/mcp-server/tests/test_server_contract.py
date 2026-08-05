from __future__ import annotations

from typing import Any

import pytest
from mcp import Client
from mcp.server import MCPServer

import main
from app import mcp, registered_tool_names


EXPECTED_TOOLS = {
    "revit_health_ping",
    "revit_project_info",
    "revit_project_levels",
    "revit_project_links",
    "revit_project_worksets",
}


@pytest.mark.asyncio
async def test_tools_are_discoverable_through_public_v2_client() -> None:
    assert isinstance(mcp, MCPServer)
    assert await registered_tool_names() == EXPECTED_TOOLS

    async with Client(mcp, cache=None) as client:
        result = await client.list_tools()

    assert {tool.name for tool in result.tools} == EXPECTED_TOOLS
    assert all(tool.input_schema["type"] == "object" for tool in result.tools)


def test_stdio_entry_mode_uses_v2_run_api(monkeypatch: pytest.MonkeyPatch) -> None:
    call: dict[str, Any] = {}

    def fake_run(*, transport: str, **kwargs: Any) -> None:
        call.update(transport=transport, **kwargs)

    monkeypatch.setattr(mcp, "run", fake_run)

    main.run_server("stdio")

    assert call == {"transport": "stdio"}


def test_http_entry_mode_passes_binding_at_run_time(monkeypatch: pytest.MonkeyPatch) -> None:
    call: dict[str, Any] = {}

    def fake_run(*, transport: str, **kwargs: Any) -> None:
        call.update(transport=transport, **kwargs)

    monkeypatch.setattr(mcp, "run", fake_run)
    monkeypatch.setattr(main.settings, "MCP_HOST", "127.0.0.1")
    monkeypatch.setattr(main.settings, "MCP_PORT", 3001)
    monkeypatch.setattr(main.settings, "MCP_STREAMABLE_HTTP_PATH", "/mcp")
    monkeypatch.setattr(main.settings, "MCP_JSON_RESPONSE", False)
    monkeypatch.setattr(main.settings, "MCP_STATELESS_HTTP", False)

    main.run_server("streamable-http")

    assert call == {
        "transport": "streamable-http",
        "host": "127.0.0.1",
        "port": 3001,
        "streamable_http_path": "/mcp",
        "json_response": False,
        "stateless_http": False,
    }
