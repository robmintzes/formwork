# ADR 0005 - Source extraction, brand marks, and fonts

Status: marks and fonts **accepted** (Rob, 2026-09-30); clean-room **proposed**.

## Rockwell repository: clean-room reference

The Rockwell `design-technology` LICENSE is proprietary/internal-use. Rob
reports Cassie's support for open-sourcing, but no scoped release record exists
yet. The engine, templates, XAML, and CSS in this repository are written
independently. Rockwell material informed concepts only: module families
M0-M7, the semantic role idea, and lessons from its token workbench (atomic
writes; and its missing Origin/Host checks, which the wizard must not repeat).
No Rockwell file, value set, font, or identifier is copied. If a specific
Rockwell component is later imported, it gets a release-record entry first.

## BIMxBert export

Rob authored the BIMxBert system with Claude Design and owns the brand.

- Token values are transcribed into `profiles/bimxbert/tokens.tokens.json`
  as structured DTCG data.
- Outlined SVG marks (wordmark and symbol, light and inverse) are imported with
  their embedded C2PA/Content Credentials metadata removed. Original file
  hashes are recorded in the release record.
- **The BIMxBert name and marks are not licensed under MIT.** A profile notice
  says so and travels into generated BIMxBert workspaces.
- Not imported: exploratory boards, uploads (RGDT source copies), PDFs, the
  React/JSX components (hard-coded wordmark; CDN Babel), and the provisional
  XAML (RGDT-compatible keys).

## Fonts

BIMxBert's Barlow Condensed, Geist, and Geist Mono are SIL OFL 1.1. Static TTF
instances (WPF handles variable fonts poorly) are vendored from the official
upstream repositories with their OFL texts and recorded hashes. The fictional
profile deliberately uses only system fonts to exercise the fallback path.
Commercial or office-licensed fonts (for example Rockwell's) are never
vendored; a firm profile may reference them with a non-redistributable licence,
which produces a warning.
