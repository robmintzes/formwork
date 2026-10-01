# Hello Button

Hello Button is a deliberately small, read-only reference tool. It confirms
that the extension loaded correctly and demonstrates project-context validation
before showing pyRevit UI.

## User workflow

1. Open a Revit project document.
2. On **Placeholder Tools**, in **Placeholder Panel**, click **Hello Button**.
3. Review the project title, active view, and non-template view count in the
   message dialog.

The tool exits without a dialog when no document is open. In a family document,
it explains that a project document is required.

## Technical design

- **Minimum pyRevit version:** 4.8.10
- **Document context:** Active Revit project document
- **Revit API query:** `FilteredElementCollector(doc).OfClass(DB.View)`
- **User interface:** `pyrevit.forms.alert`
- **External dependencies:** None beyond pyRevit and the Revit API
- **Linked models:** Not accessed

## Risk and transactions

- **Risk classification:** Low / read-only
- **Modifies the Revit database:** No
- **Transaction:** None

The script only reads the active document and view collection. It never opens a
transaction, changes a property, or writes to a linked document.

## Troubleshooting

- **No document is open:** Open a project and run the tool again.
- **A family document is active:** Switch to or open a project document.
- **The button is missing:** Reload the extension or restart Revit after
  confirming that the extension is installed and enabled.

## Changelog

- **1.0.0 (2026-08-04):** Replaced the mutating sample with a read-only project
  summary and added explicit no-document and family-document checks.
