# Handoff - foundation workspace generator (first slice)

Branch: `robmintzes/foundation-generator`, merged to main through PR
[#4](https://github.com/robmintzes/formwork/pull/4) on 2026-10-01.
Stacked on `robmintzes/foundation-charter` (policy PR #3 lineage) plus a merge
of `origin/robmintzes/runtime-stabilization` (PR #2 at `573c382`). Neither PR
is merged; this branch's eventual PR is stacked on both.

## State

- **Specification:** [FOUNDATION_SPEC.md](../product/FOUNDATION_SPEC.md),
  [decision records 0001-0007](../decisions/README.md),
  [backlog](../product/BACKLOG.md), [release record](../product/RELEASE_RECORD.md).
- **Decisions Rob answered (2026-09-30):** stack on PR #2; generated workspace
  rather than in-place fork; BIMxBert code MIT but name/marks reserved;
  vendor static OFL fonts.
- **Engine:** `toolkit_engine/` - config v1 validation, DTCG 2025.10 subset
  with alias/cycle resolution and required roles, contrast warnings, profile
  loading with SVG/PNG/font checks, adapters (`common`, `pyrevit-sample`,
  `wpf-specimen`, `html-guide`), in-memory output checks (offline, XML, PNG,
  IronPython syntax guard), manifest planner, convergent apply, path safety.
- **CLI:** `python -m toolkit_cli config validate --firm DIR`,
  `init --profile DIR --workspace DIR`, `render --workspace DIR [--dry-run]`,
  `--format json`, `--output`. Exit 0/1/2 per spec section 5.
- **Profiles:** `profiles/bimxbert` (default) and `profiles/quillmoor`
  (fictional; system fonts; pill buttons, tonal secondary, solid badges).
- **Validators:** icons may be 32x32 or 96x96, `icon.dark.png` must match;
  toolbar spec reads `docs/toolbar/spec.d/*.md` fragments.

### Verification performed (Windows 11, CPython 3.11.9)

- `py -3.11 -m unittest discover -s tests`: **120 passed** (83 pre-existing
  root tests including PR #2 and policy suites, plus 37 new engine tests).
  New engine tests also pass on CPython 3.13 and 3.14.
- Extension tests: 11 passed. Validators: all three passed. `git diff --check`
  clean.
- Both shipped profiles generate workspaces (paths with spaces and
  parentheses) that pass `validate_bundle_structure` and
  `validate_toolbar_spec` with zero errors; second render is a no-op.
- **Native WPF:** `show-specimen.ps1 -Snapshot` under Windows PowerShell 5.1
  STA rendered both specimens; packaged fonts resolved by relative URI;
  keyboard focus, disabled, and selected states visible.
  Evidence: [docs/verification/foundation-generator/](../verification/foundation-generator/).
- **Browser:** headless Microsoft Edge with a dead proxy (network unavailable)
  rendered both HTML guides with local fonts and logos.
- **Not run:** the isolated MCP pytest suite (unchanged by this work); any
  live Revit/pyRevit session. **No host support is claimed.**

## Open

1. **Rob:** review and merge PR #3, then PR #2, then draft PR #4
   (its diff includes theirs until they merge).
2. **Live gate (B11)** - runbook: [GENERATED_WORKSPACE.md](../verification/GENERATED_WORKSPACE.md);
   recorder: `toolkit verify workspace`. install a generated BIMxBert workspace's extension on
   Revit 2026 + pyRevit 6.5.5 (IronPython 2.7.12) and record ribbon load,
   light/dark icons, `help_url`, no-document/family/project contexts. The
   foundation sample and Routes verification use `toolkit verify revit`
   with the human `--routes-reset-confirmed` assertion.
3. **Unverified host claims to check live:** pyRevit honours `help_url` in
   `bundle.yaml`; `icon.dark.png` at 96x96 displays in dark theme.
4. **Next engineering:** see the overnight build log below and the backlog.
   Candidates:
   - a C# Revit add-in starter (net8 for 2025/2026, net10 for 2027; the
     targeting packs and Revit API DLLs are local, so it builds offline;
     Revit 2024 / net48 needs reference assemblies that are not installed);
   - a WebView2 HTML tool host port (its DLLs must come from NuGet);
   - `config migrate` / template overrides (B13).
5. **Pending human decisions:**
   - permanent product name (B17);
   - engine distribution to adopters (B16);
   - whether NuGet/PyPI downloads are acceptable for local verification of
     the vendored MCP server suite and WebView2 (CI covers the MCP suite).
6. **Workstation constraint:** Cylance Script Control blocks some PowerShell
   scripts here (`verify-generated-workspace.ps1`; probably
   `verify-windows.ps1`). The Python CLI paths are the supported route.

### Rejected paths

- In-place fork rebranding (ADR 0002).
- Region markers in shared files, and partial apply on conflict (ADR 0004).
- Copying licensed fonts, third-party binaries, or Rockwell marks (ADR 0005).
  Rob-authored Rockwell code is now permitted.
- React/CDN wizard stack (ADR 0006).
- `rem` tokens and silent WPF size offsets (ADR 0003).

## Overnight build log (2026-09-30 to 10-01)

Rob granted free rein at about 11:30 PM to keep building. Lead: Opus.
Well-specified chunks went to Sonnet subagents, and the lead reviewed every
change before committing.

| Commit | Item |
| --- | --- |
| `8798b52` | `toolkit validate --workspace`; bootstrap scripts retired; Windows CI generates and validates both profiles |
| `25b1a20` | Wizard backend (`toolkit serve`): loopback-only, token, Host/Origin checks, cookie-scoped preview, plan-before-apply |
| `776bb63` | `mcp-bridge` surface (Sonnet), and CI running the vendored MCP server tests in a generated workspace |
| `2537d84` | Wizard UI (Sonnet): 8 steps, strict CSP, no innerHTML; the lead clicked through it in the browser pane |
| `159ae5c` | `ui-kit` surface ported from Rockwell rgdt_ui (Sonnet): M0/M1/M2 dialogs, UI Kit Demo button, native snapshots |
| `91bae77` | Live checklist gains UI Kit Demo checks (WPF inside Revit) |
| `63692cb` | Adopter guide `docs/onboarding/ADOPTING.md` and README refresh (Sonnet) |
| `c7eaef2` | Firm overrides (`firm/overrides/`): deliberate customization without conflicts |
| `b60e9fc` | `revit-addin` C# starter (Sonnet): offline `dotnet build` for Revit 2026/2027 verified; stable uuid5 AddInId |
| `4bf8a37` | Spec 4.7 overrides; Revit 2025.5/2026.5 now on .NET 10 (memory overlay corrected after checking Autodesk and the local RevitAPI references) |
| `b003ac2` | CI fix: add-in build-error tests gated to Windows (NETSDK1100 on Ubuntu runners) |
| `6f3f66e` | `python-app` (branded CSV/JSON to HTML report CLI) and `web-app` (dependency-free TypeScript on Node 22.18+) starters (Sonnet) |
| `da5d12e` | `web-host` WebView2 tool host ported from rgdt_web (Sonnet), and fixes for the Opus adversarial security review (1 medium, 6 low, 4 info; [review](../reviews/security-review-2026-10-01.md)) |

### End-of-night state (2026-10-01, about 06:00)

- **Surfaces (11):**
  - pyrevit-sample, wpf-specimen, html-guide;
  - governance, mcp-bridge;
  - ui-kit, web-host;
  - revit-addin, python-app, web-app;
  - plus the always-on common files.
- **Commands:** `config validate`, `init`, `render [--dry-run]`, `validate`, `serve` (wizard), `verify workspace`, plus PR #2's `doctor` and `verify revit`.
- **Tests:** 299 root tests, plus 11 extension tests, all passing on Windows with CPython 3.11. CI was green at every completed head, with one Linux-only failure fixed in `b003ac2`.
- **Evidence beyond unit tests:**
  - native WPF snapshots: specimen, UI kit dialogs, the add-in summary window;
  - offline headless Edge renders of the guides;
  - real offline `dotnet build` for Revit 2026 and 2027;
  - generated Python and Node app suites executed;
  - vendored MCP server tests run in CI.
- **Still unverified:** anything inside Revit or pyRevit. The checklist now covers:
  - the ribbon and light/dark icons;
  - `help_url`;
  - no-document, family and project contexts;
  - the UI Kit Demo;
  - the Web Tool Demo;
  - clean exit.

  The C# add-in has never been loaded.
- **Recommended next step (Rob, about 30-45 min):** run
  [GENERATED_WORKSPACE.md](../verification/GENERATED_WORKSPACE.md) on Revit
  2026 with a generated BIMxBert workspace. Every host surface has
  accumulated unverified code; the live gate now outranks new features.

Findings worth Rob's attention:

- **Revit 2025 and 2026 moved to .NET 10** in their .5 updates. The repo's
  memory overlay said .NET 8, and the installed RevitAPI.dll references
  confirm .NET 10. Any Rockwell C# add-ins still targeting net8 should be
  checked against .NET 10 breaking changes.
- **Cylance Script Control** blocked `verify-generated-workspace.ps1` but
  allowed `show-specimen.ps1` and the UI-kit snapshot script, so the policy is
  selective. The Python CLI paths avoid it.
- **Rockwell reuse:** ADR 0005 and release record R05 record the scope.
  Licensed fonts, Rockwell marks, WebView2 DLLs, internal paths, and project
  data stay out.

## Incremental Edit Log

- **2026-10-01:** Merged PR #3 (`6aa7e84`), then PR #2 after bringing it up to
  date with main (`7b1e5fb`, merged `7ad4ad7`), then PR #4 (`3ccf8b4`), all with
  merge commits and green required checks. Rob chose the name **Formwork**
  (ADR 0008). The GitHub repo was renamed to `robmintzes/formwork` (old URLs
  redirect; ruleset 24278014 carried over). CLI and package rename is B21.

- **2026-09-30:** Added the `governance` surface (B12): canonical AGENTS.md, thin
  client pointers, firm skill, branch policy doc, CI workflow, ruleset JSON,
  and vendored validators/hooks/installer with asserted substitutions;
  optional `governance.required_approvals`. The IronPython guard is now scoped to
  `extensions/`. Real-hook test: generated workspace blocks main, agent, and
  non-maintainer branches.

- **2026-09-30:** Added `toolkit verify workspace` (redacted evidence; checklist
  coverage enforcement), the manual checklist template, the runbook, and
  `scripts/verify-generated-workspace.ps1`. Python path verified end to end;
  the PowerShell wrapper is blocked by Cylance Script Control on the reference
  workstation, so the runbook uses plain commands. Fixed windows-smoke CI by
  sizing the bootstrap test's nested-suite timeout (`79c60d8`).

- **2026-09-30:** Created branch; merged PR #2 into the planning branch,
  resolving AGENTS/README/INDEX/onboarding conflicts in favour of the policy
  text with stabilization's neutral author wording (`5699926`).
- **2026-09-30:** Wrote spec, ADRs, backlog (`79a5a60`).
- **2026-09-30:** Implemented engine, CLI, schema, validator changes, and
  acceptance tests (`67dd534`).
- **2026-09-30:** Added BIMxBert and Quillmoor profiles, release record, and
  render evidence (`702476a`).
