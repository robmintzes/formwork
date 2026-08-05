# -*- coding: utf-8 -*-
"""Startup initializer for pyRevit MCP Routes."""

__author__ = "Template Author"

import os
import sys

from pyrevit import script

logger = script.get_logger()

# IronPython 2 reload function fallback
try:
    reload
except NameError:
    from importlib import reload


def _import_or_reload(module_name):
    if module_name in sys.modules:
        return reload(sys.modules[module_name])
    __import__(module_name)
    return sys.modules[module_name]


def init():
    """Import and register MCP route shims and handlers."""
    # Ensure this directory is in sys.path for relative/absolute imports
    lib_dir = os.path.dirname(os.path.dirname(__file__))
    if lib_dir not in sys.path:
        sys.path.insert(0, lib_dir)

    # Import identity recorder.
    _identity = _import_or_reload("revit_mcp_bridge.identity")

    # Route shims are stable registration surfaces. Exceptions propagate to the
    # extension startup script so a broken bridge is never logged as healthy.
    _route_modules = [
        "revit_mcp_bridge.routes_health",
        "revit_mcp_bridge.routes_project",
        "revit_mcp_bridge.routes_dispatch",
    ]
    for _name in _route_modules:
        _module = _import_or_reload(_name)
        _identity.record_loaded(_name, _module, kind="route")

    logger.info("pyRevit MCP Bridge: Route modules registered.")

    # Preload handlers and fail startup honestly if any import is broken.
    from revit_mcp_bridge import dispatch as _dispatch
    _handler_modules = [
        "revit_mcp_bridge.handlers_registry",
        "revit_mcp_bridge.handlers_health",
        "revit_mcp_bridge.handlers_project",
    ]
    for _name in _handler_modules:
        _dispatch.preload(_name)

    logger.info("pyRevit MCP Bridge: Handler modules preloaded.")
