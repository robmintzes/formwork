# -*- coding: utf-8 -*-
"""Register the extension's local pyRevit Routes at session startup."""

__author__ = "Template Author"

import os
import sys

from pyrevit import script

log = script.get_logger()


def _initialize_extension():
    """Register route decorators without starting the pyRevit Routes server."""
    try:
        ext_dir = os.path.dirname(__file__)
        lib_dir = os.path.join(ext_dir, "lib")
        if lib_dir not in sys.path:
            sys.path.insert(0, lib_dir)

        from revit_mcp_bridge import startup as mcp_startup

        mcp_startup.init()
        log.info("Placeholder extension loaded and MCP routes registered.")
    except Exception as e:
        log.warning("Could not initialize MCP routes bridge: {}".format(e))


# pyRevit executes startup.py as a script; it does not call a module __init__
# function. Importing route modules registers their decorators. The Routes server
# itself remains controlled by the user's pyRevit settings.
_initialize_extension()
