# ADR 0007 - pyRevit icon contract

Status: **proposed**.

## Context

The template validator required exactly 32x32 `icon.png`. Rockwell and BIMxBert
guidance use 96x96 PNG pairs (`icon.png`, `icon.dark.png`). pyRevit documents
`icon.dark.png` as the dark-theme variant and accepts images up to 96x96,
scaling them for display DPI (pyRevit Bundles documentation; pyRevit forum
"What for the icon size").

## Decision

- Generated bundles ship `icon.png` and `icon.dark.png`, both 96x96 RGBA,
  drawn deterministically by the engine from brand tokens.
- `check_bundle_structure.py` accepts square 32x32 or 96x96 icons and requires
  `icon.dark.png`, when present, to match `icon.png`'s size. Other sizes remain
  errors. This is a deliberate widening, not a removal of the check.
- Live verification records whether both variants display correctly on the
  declared Revit/pyRevit combination; until then the dark variant is unverified.
