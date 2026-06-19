# -*- coding: utf-8 -*-
"""Hot-reload dispatcher for pyRevit MCP route shims."""

import os
import sys

from mcp.response import make_error
from mcp import identity

try:
    reload
except NameError:
    from importlib import reload

try:
    import importlib
except Exception:
    importlib = None

_LOADED_MTIMES = {}


def call(tool, module_name, function_name, *args):
    """Load/reload a handler module and call the requested function."""
    doc = args[0] if args else None
    try:
        module = _load_handler(module_name)
        func = getattr(module, function_name)
        return func(*args)
    except Exception as exc:
        return make_error(
            tool,
            "handler_reload_error",
            "Could not load or execute handler {}.{}: {}".format(module_name, function_name, str(exc)),
            doc=doc,
            checks=[
                "Check the pyRevit console log for the handler import traceback.",
                "Fix the handler module, then call this route again to retry hot reload.",
                "If the stable route shim changed, restart Revit fully.",
            ],
        )


def preload(module_name):
    """Import and record a handler so it is tracked from boot."""
    try:
        _load_handler(module_name)
    except Exception:
        pass


def _load_handler(module_name):
    if importlib is not None:
        try:
            importlib.invalidate_caches()
        except Exception:
            pass

    module = sys.modules.get(module_name)
    if module is None:
        __import__(module_name)
        module = sys.modules[module_name]
        _record(module_name, module)
        return module

    current = _module_mtime(module)
    loaded = _LOADED_MTIMES.get(module_name)
    if current is not None and (loaded is None or current > loaded):
        module = reload(module)
        _record(module_name, module)
    return module


def _record(module_name, module):
    mtime = _module_mtime(module)
    if mtime is not None:
        _LOADED_MTIMES[module_name] = mtime
    identity.record_loaded(module_name, module, kind="handler")


def _module_mtime(module):
    path = getattr(module, "__file__", None)
    if not path:
        return None
    if path.endswith(".pyc") and os.path.exists(path[:-1]):
        path = path[:-1]
    try:
        return os.path.getmtime(path)
    except Exception:
        return None
