# ADR 0005 - Source extraction, brand marks, and fonts

Status: marks and fonts **accepted** (Rob, 2026-09-30). Rockwell reuse
**accepted** (Rob, 2026-09-30), superseding the earlier clean-room proposal.

## Rockwell repository: reuse with a scoped record

The Rockwell `design-technology` LICENSE is proprietary/internal-use. On
2026-09-30 Rob, who authored nearly all of that repository with AI
assistance, explicitly permitted using its tools and apps here and said not to
treat its licensing as a blocker. He had earlier reported Cassie Nozil's
support for open-sourcing.

The permission covers Rob-authored Rockwell code, XAML, CSS, documentation,
and design patterns. It does **not** cover what was never Rockwell's or Rob's
to grant. Those items stay out:

- Adobe/office-licensed fonts (IvyPresto, Proxima Nova, Auger Mono);
- bundled third-party binaries (qpdf, the WebView2 SDK);
- client and project data;
- internal deployment destinations (`G:\` lanes, internal URLs);
- Rockwell's name, logos, and marks.

Imported items are neutralized: firm identity becomes configuration, `RGDT` /
`rg-` identifiers become the firm namespace, and internal references are
removed. Each item is recorded in the release record (source commit, files,
changes, verification) before it merges.

Code written before this permission (the engine, the CLI, the wizard
boundary, and the initial XAML/CSS) was written independently, using Rockwell
material only as a reference for concepts. It stays as it is; nothing
requires it to be replaced.

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
