# Adversarial security review - October 1, 2026

Reviewer: an independent Opus subagent, read-only, with proof-of-concept
scripts run against temporary copies. The lead fixed the findings in the same
session. Regression tests are in `tests/test_security_hardening.py`.

## Verdict

The wizard boundary held against outside attackers: every DNS-rebinding,
`text/plain`, form-POST, and foreign-origin probe received 421 or 403. One
medium finding (manifest tampering) and several low findings were fixed.
Nothing was found that would let a web page or an unauthenticated local
process write files.

## Findings and dispositions

| # | Severity | Finding | Disposition |
| --- | --- | --- | --- |
| 1 | Medium | Manifest `firm/` / `.toolkit/` guard was case-sensitive; a tampered manifest listing `FIRM/firm.json` deleted inputs (confirmed) | **Fixed.** `is_reserved_path` casefolds; manifest entries must name a known adapter |
| 2 | Low | Preview cookie value was the API token; cookies are not port-scoped | **Fixed.** Separate per-launch preview secret that cannot unlock `/api` |
| 3 | Low | Brand SVG checks missed `<style>@import`, `url(http...)`, `<set>`/`<animate>` href injection, UTF-16 DOCTYPE (confirmed) | **Fixed.** Expat-based DTD detection; static-artwork allow rules; scheme and `url()` checks on attributes and `<style>`; SVG outputs scanned too |
| 4 | Low | Generated web server served a dot-file via its 8.3 short name `ENV-SE~1` (confirmed with Node 24) | **Fixed.** Resolved long-name segments re-checked; Host allow-list added (DNS rebinding) |
| 5 | Low | External-resource regexes bypassable (`srcset`, `image-set`, `https:host`, `/\host`, `<base>`, XAML `ImageSource`/`UriSource`, UNC, WebSocket, `sendBeacon`) | **Fixed.** One remote-reference definition applied to all loading contexts; navigation `<a>` exempt |
| 6 | Low | Reserved-name gaps (`COM¹`, `CONIN$`, `CONOUT$`, `CLOCK$`, `CON .json`) | **Fixed.** `is_reserved_name` shared by output paths and config |
| 7 | Low | Single-threaded wizard could be stalled by one idle socket | **Fixed.** Handler socket timeout (15 s) |
| 8 | Info | Deeply nested JSON raised `RecursionError` | **Fixed.** Clean 400 `request.json`; unexpected errors return a stable 500 without a traceback |
| 9 | Info | Workspace paths in system folders accepted | **Fixed.** `SystemRoot`, `ProgramFiles`, `ProgramFiles(x86)`, `ProgramData` refused. UNC paths remain allowed (some firms use shares) |
| 10 | Info | Check-then-write window for junction swaps; `firm/` itself not link-checked | **Partly fixed.** `firm/` reparse points refused. The swap window needs local write access to the workspace and is **accepted** |
| 11 | Info | Preview iframe had no `sandbox` | **Fixed.** `sandbox="allow-same-origin"` (no scripts; cookie still works) |

## Accepted risks

- **Manifest as trusted engine state.** A tampered manifest can still mark a
  committed file as a retired `common` output with its current hash. The next
  render would delete it, and the dry run lists it. Treat
  `.toolkit/manifest.json` changes like code in review.
- **The MCP SDK's own DNS-rebinding protection** on the HTTP transport was not
  verified for `mcp>=2`. The local environment had 1.26. The bridge's own
  loopback validation was confirmed: `0.0.0.0`, `::`, `nip.io`, userinfo, and
  numeric-IP tricks are all refused.
- **Template trust.** Output scanning is a safety net for foundation
  templates, not a sandbox for hostile templates.
