# -*- coding: utf-8 -*-
"""pyRevit Routes - Stable route shims for MCP project metadata."""

from pyrevit import routes
from mcp import dispatch

_API = routes.API("placeholder")


@_API.route("/project/info/", methods=["GET"])
def get_project_info(doc, request):
    return dispatch.call("revit_project_info", "mcp.handlers_project", "get_project_info", doc, request)


@_API.route("/project/levels/", methods=["GET"])
def get_project_levels(doc, request):
    return dispatch.call("revit_project_levels", "mcp.handlers_project", "get_project_levels", doc, request)


@_API.route("/project/worksets/", methods=["GET"])
def get_project_worksets(doc, request):
    return dispatch.call("revit_project_worksets", "mcp.handlers_project", "get_project_worksets", doc, request)


@_API.route("/project/links/", methods=["GET"])
def get_project_links(doc, request):
    return dispatch.call("revit_project_links", "mcp.handlers_project", "get_project_links", doc, request)
