# -*- coding: utf-8 -*-
"""Shared response envelope builder for pyRevit MCP route handlers."""

__author__ = "Template Author"


def _doc_context(doc):
    """Build a minimal document context dict from an active Revit document."""
    if doc is None:
        return {"title": None, "path": None, "is_workshared": False}

    return {
        "title": _safe_doc_title(doc),
        "path": _safe_doc_path(doc),
        "is_workshared": _safe_is_workshared(doc),
    }


def _safe_doc_title(doc):
    try:
        return doc.Title
    except Exception:
        return None


def _safe_doc_path(doc):
    try:
        return doc.PathName if doc.PathName else None
    except Exception:
        return None


def _safe_is_workshared(doc):
    for attr_name in ("IsWorkshared", "IsWorkShared"):
        try:
            return bool(getattr(doc, attr_name))
        except Exception:
            pass
    return False


def make_ok(tool, data, doc=None, messages=None, next_actions=None):
    """Build a successful response envelope."""
    return {
        "status": "ok",
        "tool": tool,
        "risk_class": "read_only",
        "document": _doc_context(doc),
        "data": data if data is not None else {},
        "messages": messages if messages is not None else [],
        "next_actions": next_actions if next_actions is not None else [],
    }


def make_error(tool, code, message, checks=None, doc=None):
    """Build an error response envelope."""
    return {
        "status": "error",
        "tool": tool,
        "risk_class": "read_only",
        "document": _doc_context(doc),
        "data": {},
        "messages": [],
        "next_actions": [],
        "error": {
            "code": code,
            "message": message,
            "checks": checks if checks is not None else [],
        },
    }
