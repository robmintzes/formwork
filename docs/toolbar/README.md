# Toolbar Specification Guidelines

The file `toolbar_spec.md` is the single source of truth for our pyRevit extension layout. It defines how tools are grouped into tabs and panels on the Revit ribbon.

---

## 1. Hierarchy Rules

We enforce a strict **three-tier hierarchy**:
1. **Tab:** Represents the main Ribbon Tab (e.g. `AcmeTools`).
2. **Panel:** Represents a group within a Tab (e.g. `Sheet Tools`).
3. **Tool:** Represents the actual clickable button (e.g. `Create Sheets`).

*Note on Stacks:* Stacks (vertical alignments of 2 or 3 small buttons) are layout-hints, not a hierarchy tier. A tool in a stack sits flat under its parent panel and indicates its placement using `display_hint: stack:<stack_name>`.

---

## 2. Formatting a Tool Entry

Every tool must be registered in the spec sheet under its parent panel's heading using the following YAML schema:

```yaml
  - id: tool-unique-id            # Must be globally unique in this spec
    display_name: Button Title    # What users see on the button
    type: PushButton              # PushButton | SplitButton | Dropdown
    category: utility             # utility | audit | annotate | modeling
    risk: Low                     # Low | Medium | High
    lifecycle_stage: sandbox      # sandbox | beta | production
    description: Detail summary   # Details of what the tool accomplishes
    source_path: path/to/folder   # Relative path from repository root
    requires_confirmation: false  # Must be true if risk is High
```

---

## 3. Coverage Validation

The validator script `validators/validate_toolbar_spec.py` automatically checks this file on every commit to ensure:
- Every folder on disk ending in `.pushbutton` has a registered entry in `toolbar_spec.md`.
- No orphan entries exist in the spec that do not correspond to actual folders.
- All required fields are present.
- All IDs are unique.
