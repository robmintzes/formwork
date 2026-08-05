# -*- coding: utf-8 -*-
"""pyRevit Routes - Health endpoint handler for MCP."""

__author__ = "Template Author"

from pyrevit import HOST_APP
from pyrevit import script

from revit_mcp_bridge.response import make_ok, make_error
from revit_mcp_bridge import identity as _identity

logger = script.get_logger()


def get_health(doc, request):
    """Return Revit status, pyRevit version string, and active document info."""
    tool = "revit_health_ping"
    try:
        revit_version = str(HOST_APP.version)
        revit_build = str(HOST_APP.build)

        try:
            pyrevit_version = str(HOST_APP.pyrevit_version)
        except Exception:
            pyrevit_version = "unknown"

        if doc is None:
            return make_ok(
                tool,
                {
                    "revit_version": revit_version,
                    "revit_build": revit_build,
                    "pyrevit_version": pyrevit_version,
                    "document_open": False,
                    "extension_identity": _identity.identity(),
                },
                doc=None,
                messages=["No document is open in the active Revit session."],
                next_actions=[
                    "Open a Revit project, then retry.",
                    "Call revit_health_ping again to confirm document state.",
                ],
            )

        return make_ok(
            tool,
            {
                "revit_version": revit_version,
                "revit_build": revit_build,
                "pyrevit_version": pyrevit_version,
                "document_open": True,
                "extension_identity": _identity.identity(),
            },
            doc=doc,
            next_actions=["Call revit_project_info for full project metadata."],
        )

    except Exception as exc:
        logger.error("pyRevit MCP routes_health error: {}".format(exc))
        return make_error(
            tool,
            "revit_error",
            "An unexpected error occurred in the health route: " + str(exc),
            checks=["Check the pyRevit console log for details."],
        )
