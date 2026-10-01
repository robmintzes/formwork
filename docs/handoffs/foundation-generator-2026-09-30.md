# Handoff - foundation workspace generator (first slice)

Branch: `robmintzes/foundation-generator`, pushed; draft PR [#4](https://github.com/robmintzes/pyrevit-toolbar-template/pull/4).
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
4. **Next engineering:** governance adapter (B12: AGENTS.md, agent shims,
   hooks/branch policy from `maintainers`, ruleset JSON); `toolkit validate
   --workspace`; retire `scripts/bootstrap.*` and update CI windows-smoke
   (B15); wizard per ADR 0006 (B14).
5. **Pending human decisions:** permanent product name (B17); engine
   distribution to adopters (B16).

### Rejected paths

- In-place fork rebranding (ADR 0002); region markers in shared files and
  partial apply on conflict (ADR 0004); copying Rockwell files or fonts
  (ADR 0005); React/CDN wizard stack (ADR 0006); `rem` tokens and silent
  WPF size offsets (ADR 0003).

## Incremental Edit Log

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
