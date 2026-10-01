# ADR 0006 - Wizard stack

Status: **proposed**; implementation follows the proven generator.

## Decision

A local browser wizard served by `toolkit serve`:

- Python stdlib `http.server`, bound to `127.0.0.1` on a random free port.
- Per-launch random token in the opened URL fragment; every API call must send
  it in a header. `Host` must be the loopback address and port; `Origin`, when
  present, must match. JSON bodies only, size-capped.
- The API calls engine functions (`validate`, `plan`, `apply`); it never
  exposes arbitrary file reads or writes. Writes are limited to the selected
  workspace's `firm/` inputs and the engine's own apply.
- UI: static HTML/CSS/vanilla JS shipped in the foundation, styled by the
  foundation's own generated tokens. No build step, no npm, no CDN.
- Previews reuse the HTML adapter output; the WPF preview is labelled as a
  browser approximation until the native snapshot runner has been executed.

## Why not React/Electron/a desktop toolkit now

The BIMxBert export's React components depend on CDN Babel and a missing bundle;
a build chain would be the largest maintenance burden in the repository for a
handful of forms. Desktop packaging can wrap the same local service later
(for example a WebView2 host) once the flow is proven.
