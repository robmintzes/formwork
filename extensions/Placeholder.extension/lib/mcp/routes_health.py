# -*- coding: utf-8 -*-
"""pyRevit Routes - Stable route shims for MCP health check."""

from pyrevit import routes
from mcp import dispatch

_API = routes.API("placeholder")


@_API.route("/health/", methods=["GET"])
def get_health(doc, request):
    return dispatch.call("revit_health_ping", "mcp.handlers_health", "get_health", doc, request)
