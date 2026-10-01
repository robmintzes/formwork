# -*- coding: utf-8 -*-
"""pyRevit Routes - Stable route shims for MCP project metadata."""

__author__ = "Template Author"

from pyrevit import routes
from revit_mcp_bridge import dispatch

_API = routes.API("placeholder")


@_API.route("/project/info/", methods=["GET"])
def get_project_info(doc, request):
    return dispatch.call("revit_project_info", "revit_mcp_bridge.handlers_project", "get_project_info", doc, request)


@_API.route("/project/levels/", methods=["GET"])
def get_project_levels(doc, request):
    return dispatch.call("revit_project_levels", "revit_mcp_bridge.handlers_project", "get_project_levels", doc, request)


@_API.route("/project/worksets/", methods=["GET"])
def get_project_worksets(doc, request):
    return dispatch.call("revit_project_worksets", "revit_mcp_bridge.handlers_project", "get_project_worksets", doc, request)


@_API.route("/project/links/", methods=["GET"])
def get_project_links(doc, request):
    return dispatch.call("revit_project_links", "revit_mcp_bridge.handlers_project", "get_project_links", doc, request)
