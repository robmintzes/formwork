from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app import mcp
from revit_client import RevitClientError
from schemas import DocumentContext, RevitResponse
from tools import project


@pytest.mark.asyncio
async def test_project_info_returns_success_envelope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response = RevitResponse(
        status="ok",
        tool="revit_project_info",
        document=DocumentContext(
            title="Example Project",
            path="C:/Models/example.rvt",
            is_workshared=True,
        ),
        data={"project_number": "A-100", "project_name": "Example"},
        messages=["Project metadata loaded."],
    )
    client = AsyncMock()
    client.get.return_value = response
    monkeypatch.setattr(project, "RevitClient", lambda: client)

    call_result = await mcp.call_tool("revit_project_info", {})

    client.get.assert_awaited_once_with("/project/info/")
    assert call_result.is_error is False
    assert call_result.structured_content is not None
    result = call_result.structured_content
    assert result == response.model_dump()
    assert result["status"] == "ok"
    assert result["risk_class"] == "read_only"
    assert result["error"] is None


@pytest.mark.asyncio
async def test_project_levels_normalises_revit_client_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = AsyncMock()
    client.get.side_effect = RevitClientError(
        "revit_timeout",
        "Revit did not answer in time.",
        ["Confirm the Routes server is listening."],
    )
    monkeypatch.setattr(project, "RevitClient", lambda: client)

    call_result = await mcp.call_tool("revit_project_levels", {})

    client.get.assert_awaited_once_with("/project/levels/")
    assert call_result.is_error is False
    assert call_result.structured_content is not None
    result = call_result.structured_content
    assert result == {
        "status": "error",
        "tool": "revit_project_levels",
        "risk_class": "read_only",
        "document": {"title": None, "path": None, "is_workshared": False},
        "data": {},
        "messages": [],
        "next_actions": [],
        "error": {
            "code": "revit_timeout",
            "message": "Revit did not answer in time.",
            "checks": ["Confirm the Routes server is listening."],
        },
    }
