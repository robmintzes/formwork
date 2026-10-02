# Array Along Path browser and static verification

Date: 2026-10-02. Browser: Microsoft Edge driven by Playwright.

This evidence covers the new tool's browser simulation and generated files.
It does **not** establish live Revit placement or Undo behavior.

- Initial port: 319 repository tests passed. The 9 Array Along Path tests were
  rerun after the markup revision, including 1/3/2000 new-copy counts.
- 11 extension tests passed; 18 MCP server tests passed in an isolated environment
  with the server's declared dependencies (MCP 2.2.0).
- Root bundle, toolbar spec, branch policy and safety validators passed.
  US English and `git diff --check` passed.
- Both firm profiles render the new tool; generated BIMxBert sandbox passes
  workspace validation and repeat rendering makes no changes.
- Browser interactions checked: spacing/count, valid/invalid inputs, offsets,
  seeded scatter/re-roll, plan simulation, keyboard pane sizing/persistence,
  path replay, responsive layout, system reduced motion and explicit opt-in.
  Narrow layout has no horizontal overflow at 390px. In spacing mode, the
  synthetic source's first-station duplicate is excluded from the new-copy count.
- No client/project data appears in these images; geometry is the synthetic
  demonstration path and chair outline.
- Markup revision: one compact header with the logo at upper right, Close next
  to Place copies, a stationary original outline/label, and Copies instead of
  stations in count mode. The count slider defaults to 50 and supports adjustable,
  persisted limits; entering a larger count expands its range. Verified at
  14/77/2000 copies, including lower-limit clamping and mode/reload behavior.
  Both animated Orientation checkboxes passed pointer, Space-key and reduced-motion
  checks. Original position/rotation remained fixed while those settings changed.
  Refreshed images below show this revision. Live placement/Undo remains unverified.

![Desktop preview](desktop.png)

![Tablet preview](tablet.png)

![Mobile preview](mobile.png)

![Scatter preview](scatter.png)

Live checklist and continuation notes:
[tool handoff](../../handoffs/array-along-path-motion-2026-10-02.md).
