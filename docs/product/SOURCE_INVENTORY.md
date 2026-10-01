# Candidate source inventory

Status: discovery inventory, not an approved release manifest.
Updated September 30, 2026. No candidate source assets were copied by this task.

Source labels:

- **Foundation repo:** this repository, Formwork (formerly pyrevit-toolbar-template).
- **Rockwell repo:** Rob's local design-technology repository; paths below are
  relative to that repository, avoiding workstation-specific public links.
- **Brand export:** BIMxBert Design System (1).zip supplied by Rob.

Existing Rockwell code is governed by that repository's proprietary/internal-use
LICENSE. Rob's reported approval from Cassie should be reflected in a scoped
release record. The existing public foundation has an MIT license; that does
not establish the release terms of additional imported material.

## Candidate components

| ID | Source / path | Proposed disposition | Known work before incorporation |
| --- | --- | --- | --- |
| S01 | Foundation repo: AGENTS.md, agent shims, validators, docs/toolbar/, docs/onboarding/BRANCH_POLICY.md | Retain and generalize | Integrate policy PR #3; replace maintenance-owner defaults with adopter configuration where applicable. |
| S02 | Foundation repo: draft stabilization PR #2 | Review and integrate | Complete subsystem review, reconcile policy changes, and retain honest live-verification boundaries. |
| S03 | Brand export: tokens/CONTRACT.md, tokens/scale.css, themes/bimxbert.css | Starting token vocabulary and default profile | Convert maintained values into structured data; preserve meanings and resolve platform-specific conversions. |
| S04 | Brand export: components/ui-components.css and components/*/*.jsx | Candidate neutral component layer | Replace hard-coded Wordmark and accessibility labels with profile-backed brand assets; validate the runtime behavior. |
| S05 | Brand export: exports/illustrator/BIMxBert-*.svg | Default BIMxBert asset pack | Record release terms and provenance; define logo slots and generated platform variants for adopting firms. |
| S06 | Brand export: xaml/BIMxBert.Theme.Light.xaml | WPF adapter specimen | It remains provisional and uses RGDT-compatible keys/controls; reconcile with a neutral, generated contract and test on Windows. |
| S07 | Brand export: tokens/fonts.css | Font configuration example | Current file uses Google Fonts imports; choose licensed local font files for offline tools and retain notices. |
| S08 | Rockwell repo: automation/rgdt_token_workbench.py and automation/test_rgdt_token_workbench.py | Reference for the generator and later wizard | Generalize hard-coded paths; expand from color updates to the proposed profile; establish scoped release/provenance records. |
| S09 | Rockwell repo: DT Tools/DT Tools.extension/lib/rgdt-design-system/tokens/rgdt-color-tokens.json | Structured token reference | Map legacy names to the neutral contract; avoid maintaining two independent authorities. |
| S10 | Rockwell repo: DT Tools/DT Tools.extension/lib/rgdt-design-system/modules/rgdt-module-schemas.json and docs/design/rgdt/tool-ui-modules.md | Candidate module schemas and recipes | Separate firm identity from reusable structure; begin with the first demo's supported components. |
| S11 | Rockwell repo: DT Tools/DT Tools.extension/lib/rgdt_ui/RGDT.Controls.xaml and bootstrap.py | Candidate WPF controls/loading reference | Establish approved extraction scope, neutral resources, font handling, and explicit host/runtime compatibility. |
| S12 | Rockwell repo: docs/design/rgdt/component-recipes.md and docs/templates/technical-report/ | Candidate documentation/component recipes | Extract reusable layouts and guidance; parameterize branding and remove internal examples and destinations. |

These entries identify candidates rather than certify the complete source or
its licensing. Paths S08-S12 and the Brand export were checked locally; the
ZIP's listed component/theme/asset paths were inspected during the preceding
architecture discussion. PR #2's automated results are recorded in the
[repository assessment](../reviews/repository-state-2026-09-30.md).

## Release record required for each imported item

Record the exact source version/hash, selected files, origin and contributors,
approval scope, original and release license, third-party dependencies, changes
made during neutralization, and the verification performed. Keep the release
record separate from changing firm/tool author metadata.

## Material outside the initial extraction

Internal project data, deployment destinations, credentials, archives, compiled
third-party binaries, commercial font files, complete production toolbar
collections, and unrelated applications are outside the first demo. Expand the
inventory deliberately when another component has a defined product use.
