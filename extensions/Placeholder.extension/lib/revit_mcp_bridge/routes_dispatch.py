# -*- coding: utf-8 -*-
"""pyRevit Routes - Single generic dispatch route for MCP."""

__author__ = "Template Author"

from pyrevit import routes
from revit_mcp_bridge import dispatch

_API = routes.API("placeholder")


@_API.route("/x/<op>/", methods=["GET"])
def get_generic_dispatch(doc, request, op):
    return dispatch.call_registered(op, doc, request)
