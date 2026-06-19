# tools/project.py
# MCP tools for project metadata.

from __future__ import annotations

from typing import Any

from app import mcp
from revit_client import RevitClient, RevitClientError, build_error_result


@mcp.tool()
async def revit_project_info() -> dict[str, Any]:
    """
    Get metadata about the currently open Revit project.

    Use this first when you need to orient to the active model before answering
    project-specific Revit questions. Returns title, file path, worksharing status,
    project number, project name, client name, status, and issue date.
    """
    client = RevitClient()
    try:
        response = await client.get("/project/info/")
        return response.model_dump()
    except RevitClientError as exc:
        return build_error_result("revit_project_info", exc)


@mcp.tool()
async def revit_project_levels() -> dict[str, Any]:
    """
    Get all levels defined in the currently open Revit project, sorted by elevation.

    Returns level name, elevation in feet, and element ID for each level. Useful for
    confirming floor-to-floor heights and checking for duplicate levels.
    """
    client = RevitClient()
    try:
        response = await client.get("/project/levels/")
        return response.model_dump()
    except RevitClientError as exc:
        return build_error_result("revit_project_levels", exc)


@mcp.tool()
async def revit_project_worksets() -> dict[str, Any]:
    """
    Get all user worksets in the currently open workshared Revit project.

    Returns workset name, ID, open/closed state, and current owner (if checked out).
    Returns an empty worksets list if the project is not workshared.
    """
    client = RevitClient()
    try:
        response = await client.get("/project/worksets/")
        return response.model_dump()
    except RevitClientError as exc:
        return build_error_result("revit_project_worksets", exc)


@mcp.tool()
async def revit_project_links() -> dict[str, Any]:
    """
    Get all linked Revit models and CAD files in the currently open Revit project.

    Returns link name, element ID, link type (revit/cad), loaded state, file path,
    and attachment type (overlay vs attachment) for Revit links.
    """
    client = RevitClient()
    try:
        response = await client.get("/project/links/")
        return response.model_dump()
    except RevitClientError as exc:
        return build_error_result("revit_project_links", exc)
