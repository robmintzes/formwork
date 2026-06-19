# -*- coding: utf-8 -*-
"""Hello Button - Template pushbutton script demonstrating pyRevit standards."""
from __future__ import annotations

import sys
from Autodesk.Revit.Exceptions import OperationCanceledException
from pyrevit import DB, forms, revit

doc = revit.doc
uidoc = revit.uidoc


def main() -> None:
    # 1. Context validation up front
    if doc.IsFamilyDocument:
        forms.alert(
            "This script must be run inside a project (.rvt) document.",
            exitscript=True,
        )

    # 2. Gather information (Read-only phase)
    # Collect all views in the current project
    collector = DB.FilteredElementCollector(doc).OfClass(DB.View)
    views = [v for v in collector if not v.IsTemplate]

    if not views:
        forms.alert("No views found in the current project.", exitscript=True)

    # Create printable display name helper
    view_list = sorted(
        [forms.TemplateListItem(v, name=v.Name) for v in views],
        key=lambda x: x.name,
    )

    # 3. Present UI selection (outside of transaction)
    selected_view = forms.select_from_list(
        view_list,
        title="Select View to Audit",
        multiselect=False,
    )

    if not selected_view:
        # Exit cleanly if user closed the dialog or hit cancel
        print("Selection canceled by user.")
        sys.exit(0)

    # 4. Modify Database (Write phase inside explicit transaction)
    # We will append a comment suffix to the selected view's name as a test.
    tx = DB.Transaction(doc, "Template: Update View Name")
    try:
        tx.Start()

        # Update view name securely
        original_name = selected_view.Name
        # Note: If name contains [Audited], we skip it to prevent infinity appends
        if "[Audited]" not in original_name:
            selected_view.Name = "{} [Audited]".format(original_name)
            print(
                "Successfully renamed view from '{}' to '{}'.".format(
                    original_name, selected_view.Name
                )
            )
        else:
            print("View '{}' has already been audited.".format(original_name))

        tx.Commit()

    except Exception as e:
        tx.Rollback()
        forms.alert(
            "Failed to rename view. Transaction rolled back.\nError: {}".format(
                e
            ),
            exitscript=True,
        )


if __name__ == "__main__":
    try:
        main()
    except OperationCanceledException:
        print("Operation canceled by user.")
        sys.exit(0)
    except Exception as err:
        forms.alert(
            "An unexpected error occurred:\n{}".format(err),
            exitscript=True,
        )
