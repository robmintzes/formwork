# -*- coding: utf-8 -*-
"""pyRevit Routes - Stable route shims for MCP health check."""

__author__ = "Template Author"

from pyrevit import routes
from revit_mcp_bridge import dispatch

_API = routes.API("placeholder")


@_API.route("/health/", methods=["GET"])
def get_health(doc, request):
    return dispatch.call(
        "revit_health_ping",
        "revit_mcp_bridge.handlers_health",
        "get_health",
        doc,
        request,
    )
