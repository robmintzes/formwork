---
name: pyrevit-tool
description: Use when building or modifying a pyRevit tool (pushbutton, splitbutton, helper library, or event hooks). Covers layout conventions, transaction safety, context checks, WPF vs HTML UI rules, and delivery checklists.
---

# pyRevit Tool Playbook

*Procedural playbook for creating or editing pyRevit toolbar buttons and tools.*

---

## 1. Directory Structure Conventions

A standard pushbutton folder must reside under `extensions/<ExtensionName>.extension/...` and have the suffix `.pushbutton`. It should contain:
- `script.py`: The executable Python code.
- `bundle.yaml`: Button manifest containing metadata.
- `icon.png`: A `32x32` pixel icon.

Example:
```text
extensions/AcmeTools.extension/AcmeTab.tab/SheetTools.panel/CreateSheets.pushbutton/
├─ script.py
├─ bundle.yaml
└─ icon.png
```

---

## 2. API Safety and Transaction Rules

Revit expects clean transaction handling. Follow these rules unconditionally:

### Context Check Up Front
Verify you are in a valid document before showing any UI.
```python
from pyrevit import revit, DB

doc = revit.doc
uidoc = revit.uidoc

# Exit immediately if document is null or in family context when project is required
if doc.IsFamilyDocument:
    from pyrevit import forms
    forms.alert("This tool can only be run in a project document.", exitscript=True)
```

### Transaction Contexts
- Perform all read operations *before* opening a transaction.
- Wrap all write operations in a transaction try-except block.
- Keep the transaction scope as small as possible. Never ask the user for input or display a UI dialog inside an open transaction.

```python
# Clean transaction template
tx = DB.Transaction(doc, "Add Parameters to View")
try:
    tx.Start()
    # Perform database modifications here
    tx.Commit()
except Exception as e:
    tx.Rollback()
    print("Failed to edit database: {}".format(e))
```

### Selection and Cancellation
When picking elements, catch cancellations cleanly rather than throwing raw .NET tracebacks.
```python
from Autodesk.Revit.Exceptions import OperationCanceledException

try:
    selected_ref = uidoc.Selection.PickObject(Autodesk.Revit.UI.Selection.ObjectType.Element)
except OperationCanceledException:
    # Clean exit on user escape/cancel
    script.exit()
```

---

## 3. Linked Document Constraints

- Linked models retrieved via `RevitLinkInstance.GetLinkDocument()` are **read-only**.
- You cannot start a transaction on a linked document.
- To modify a linked element, collect the properties from the link, and replicate the parameters or geometry in the host document.

---

## 4. UI Guideline Rules

- **Use pyRevit Primitives first:** Prefer built-in dialogs like `forms.SelectFromList`, `forms.ask_for_string`, and `forms.alert` over custom windows whenever possible.
- **Custom WPF (XAML):** If a custom GUI is necessary, use WPF with a separated XAML design. All XAML files must reference styles and colors defined in `docs/design/DESIGN.md` (and use copy-pasteable patterns from `docs/design/xaml-recipes.md`).
- **Reports and Audits (HTML/CSS):** For large output summaries, use pyRevit's HTML output window. Inject CSS that matches the tokens defined in `docs/design/html-recipes.md`.

---

## 5. Delivery Checklist

Before marking a task as complete:
1. Verify the code runs without warnings in both Python 2 and Python 3 modes if pyRevit is running in a mixed environment.
2. Confirm `bundle.yaml` contains correct `title`, `tooltip`, and `author`.
3. Check that the tool is registered under the correct panel in `docs/toolbar/toolbar_spec.md`.
4. Ensure no raw `shutil.rmtree` or dangerous shell deletions are used without manual authorization.
5. Update `docs/toolbar/tools/<id>.md` or leaving a handoff in `docs/handoffs/` if the task is a partial build.
