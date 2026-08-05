# -*- coding: utf-8 -*-
"""Allowlist registry for the pyRevit MCP generic dispatch route."""

__author__ = "Template Author"

_NO_SPEC = "none"
_OPTIONAL_SPEC = "optional"
_REQUIRED_SPEC = "required"

# op: (tool, module, function, spec_mode)
_REGISTRY = {
    "health": ("revit_health_ping", "revit_mcp_bridge.handlers_health", "get_health", _NO_SPEC),
    "project/info": ("revit_project_info", "revit_mcp_bridge.handlers_project", "get_project_info", _NO_SPEC),
    "project/levels": ("revit_project_levels", "revit_mcp_bridge.handlers_project", "get_project_levels", _NO_SPEC),
    "project/worksets": ("revit_project_worksets", "revit_mcp_bridge.handlers_project", "get_project_worksets", _NO_SPEC),
    "project/links": ("revit_project_links", "revit_mcp_bridge.handlers_project", "get_project_links", _NO_SPEC),
}


def resolve(op):
    clean = _normalize_op(op)
    if not clean:
        return None

    entry = _REGISTRY.get(clean)
    if entry is not None:
        if entry[3] == _REQUIRED_SPEC:
            return None
        return _resolved(entry, [])

    if "/" not in clean:
        return None

    prefix, spec = clean.rsplit("/", 1)
    entry = _REGISTRY.get(prefix)
    if entry is None:
        return None
    if entry[3] not in (_OPTIONAL_SPEC, _REQUIRED_SPEC):
        return None
    if spec == "":
        return None
    return _resolved(entry, [spec])


def registered_ops():
    return sorted(_REGISTRY.keys())


def _resolved(entry, extra_args):
    return (entry[0], entry[1], entry[2], extra_args)


def _normalize_op(op):
    if op is None:
        return None
    clean = str(op).strip("/")
    while "//" in clean:
        clean = clean.replace("//", "/")
    return clean
