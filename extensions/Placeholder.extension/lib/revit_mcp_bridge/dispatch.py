# -*- coding: utf-8 -*-
"""Hot-reload dispatcher for pyRevit MCP route shims."""

__author__ = "Template Author"

import os
import sys

from revit_mcp_bridge.response import make_error
from revit_mcp_bridge import identity

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


def call_registered(op, doc, request, registry_module_name=None):
    """Resolve an operation through the hot-reloadable allowlist registry.

    Request data never becomes a Python module or function name. Only literal
    mappings returned by ``handlers_registry.resolve`` can reach ``call``.
    """
    if registry_module_name is None:
        registry_module_name = "revit_mcp_bridge.handlers_registry"

    try:
        registry = _load_handler(registry_module_name)
        resolved = registry.resolve(op)
    except Exception as exc:
        return make_error(
            "revit_dispatch",
            "handler_reload_error",
            "Could not load the generic dispatch registry: {}".format(exc),
            doc=doc,
            checks=[
                "Check the pyRevit console log for the registry import traceback.",
                "Fix the registry module, then call this route again.",
                "Restart Revit if a stable route shim changed.",
            ],
        )

    if resolved is None:
        return make_error(
            "revit_dispatch",
            "operation_not_allowed",
            "Generic dispatch operation is not registered: {}".format(op),
            doc=doc,
            checks=[
                "Use an operation returned by handlers_registry.registered_ops().",
                "Register new read-only operations before calling them.",
                "Never pass module or function names in the route path.",
            ],
        )

    tool, module_name, function_name, extra_args = resolved
    args = [doc, request]
    args.extend(extra_args)
    return call(tool, module_name, function_name, *args)


def preload(module_name):
    """Import and record a handler so it is tracked from boot."""
    _load_handler(module_name)


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
    if current is not None and current != loaded:
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
