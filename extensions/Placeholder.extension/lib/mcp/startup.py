# -*- coding: utf-8 -*-
"""Startup initializer for pyRevit MCP Routes."""

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

    try:
        # Import identity recorder
        _identity = _import_or_reload("mcp.identity")
        
        # Route shims
        _route_modules = [
            "mcp.routes_health",
            "mcp.routes_project",
            "mcp.routes_dispatch",
        ]
        for _name in _route_modules:
            _module = _import_or_reload(_name)
            _identity.record_loaded(_name, _module, kind="route")
        
        logger.info("pyRevit MCP Bridge: Route modules registered.")

        # Preload handlers
        from mcp import dispatch as _dispatch
        _handler_modules = [
            "mcp.handlers_registry",
            "mcp.handlers_health",
            "mcp.handlers_project",
        ]
        for _name in _handler_modules:
            _dispatch.preload(_name)
            
        logger.info("pyRevit MCP Bridge: Handler modules preloaded.")
    except Exception as exc:
        logger.error("pyRevit MCP Bridge: Failed to register routes. {}".format(exc))
