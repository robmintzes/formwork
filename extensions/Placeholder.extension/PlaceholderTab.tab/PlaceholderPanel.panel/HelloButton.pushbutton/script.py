# -*- coding: utf-8 -*-
"""Show a read-only greeting and summary of the active Revit project."""

from pyrevit import DB, forms, revit, script

__author__ = "Template Author"


def _safe_name(value, fallback):
    try:
        name = str(value).strip()
        return name if name else fallback
    except Exception:
        return fallback


def main():
    # Validate context before collecting data or displaying a dialog.
    doc = revit.doc
    if doc is None:
        print("Hello Button requires an open Revit project document.")
        script.exit()

    if doc.IsFamilyDocument:
        forms.alert(
            "Hello Button can only run in a Revit project document.",
            title="Hello Button",
            exitscript=True,
        )

    # Read-only query: no transaction is created and no element is modified.
    views = DB.FilteredElementCollector(doc).OfClass(DB.View)
    view_count = sum(1 for view in views if not view.IsTemplate)
    active_view = getattr(doc, "ActiveView", None)

    message = (
        "Hello from your pyRevit toolkit.\n\n"
        "Project: {0}\n"
        "Active view: {1}\n"
        "Non-template views: {2}"
    ).format(
        _safe_name(getattr(doc, "Title", None), "Untitled project"),
        _safe_name(getattr(active_view, "Name", None), "No active view"),
        view_count,
    )
    forms.alert(message, title="Hello Button")


if __name__ == "__main__":
    main()
