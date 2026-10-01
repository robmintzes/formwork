# Custom Tools Documentation Guide

This document establishes the documentation standards and lifecycle requirements for all custom tools built within this pyRevit toolbar extension.

---

## 1. Documentation Goals

Clear documentation serves two primary audiences:
1. **Human Designers & BIM Managers**: Need to understand how to locate a tool, when to use it, what inputs are expected, and how to resolve common workflow failures.
2. **AI Coding Agents**: Need to understand the API contexts, selection filters, transaction boundaries, and safety policies of a tool so they can maintain or extend the codebase without introducing regressions.

---

## 2. Where Files Belong

Every tool added to this toolbar must have a corresponding guide. Maintain the following directory conventions:

```text
docs/
├─ templates/
│  └─ tool-guide-template.md        # The base template for all tool guides
└─ toolbar/
   ├─ toolbar_spec.md               # The single source of truth for the ribbon layout
   └─ tools/
      ├─ hello-button.md            # The user & technical guide for HelloButton
      └─ [your-new-tool-id].md      # Every new tool gets its own guide here
```

---

## 3. Step-by-Step Process for New Tools

When authoring a new pyRevit tool (e.g. a PushButton), follow this checklist:

### Step 1: Register in the Ribbon Spec
Before writing code, register the tool in
[toolbar_spec.md](../toolbar/toolbar_spec.md) under the appropriate panel. Define
its display name, type, category, risk, lifecycle stage, description, and source
path. The `display_name` must exactly match the `title` in the tool's
`bundle.yaml`.

### Step 2: Copy the Template
Copy [tool-guide-template.md](../templates/tool-guide-template.md) to
`docs/toolbar/tools/<tool-id>.md`. The filename must match the lowercase
kebab-case `id` in the toolbar spec.

### Step 3: Complete the Guide
Fill in all sections of the guide:
* **Workflow**: Walk through the UI and buttons.
* **API Details**: Specify whether it operates on active selection or filters, and if it requires a project document.
* **Risk & Transaction**: Define if it is `Low`, `Medium`, or `High` risk. List the transaction name.
* **Troubleshooting**: Document expected exceptions (like user cancellation).

### Step 4: Run Validators
Run the static validators from the repository root:
```bash
python validators/check_bundle_structure.py
python validators/check_safety_rules.py
python validators/validate_toolbar_spec.py
```

These checks require each pushbutton to have `script.py`, `bundle.yaml`, and a
valid `icon.png` (32x32 or 96x96); require non-empty title, tooltip, and author metadata;
and cross-check risk/lifecycle values, source paths, bundle titles, ribbon
coverage, tab-to-extension paths, and non-empty guides. They are static
guardrails, not a substitute for testing the tool in each supported
Revit/pyRevit runtime.
