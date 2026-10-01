# Live host verification matrix

Add a row only after the redacted evidence report exists and every required
automated and manual check passes.

| Check | Revit | Revit build | pyRevit | Python engine | OS | Contexts | Git SHA | Evidence | Status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Generated workspace ([runbook](GENERATED_WORKSPACE.md)), BIMxBert profile | 2026 | 26.0.4.409 (20250227_1515) | 6.5.5.26237 | IronPython 2.7.12 | Windows 11 Pro 10.0.26200 | none, family, project | `b006930` | [2026-10-01](live/2026-10-01-revit-2026-bimxbert-workspace.md) | Pass, after three fixes |
| Foundation sample and Routes/MCP (`formwork verify revit`, [README](README.md)) | - | - | - | - | - | - | - | - | Not tested |

### 2026-10-01 generated-workspace run

Rob ran the checklist in Revit. He reported the results in conversation, and the
lead recorded them in the checklist file before running `formwork verify workspace`.
The Quillmoor side-by-side check (optional) was not run.

- **Failed first attempts, fixed before the recorded pass**, in
  [PR #8](https://github.com/robmintzes/formwork/pull/8):
  1. Web Tool Demo: `No module named Web`. The host never referenced the
     WebView2 assemblies Revit had already loaded.
  2. Web Tool Demo: an ambiguous `ContinueWith` overload in IronPython.
     The environment task is now polled on the UI thread.
  3. UI Kit selector: a system resize strip over the titlebar. It now uses the
     shared non-resizable frame.

  Every automated test and offline render passed with all three defects present.
- **Evidence caveats:**
  - The report's OS line says `Windows 10` because Python's `platform.release()`
    reports `10` on Windows 11; the table above gives the real build.
  - The report records the declared Revit year; the build and the Python engine
    come from `pyrevit env`.
  - The report's `formwork 0.1.0-alpha.1` is the CLI package's own version, which
    lags the engine (`0.3.0-alpha.1`).

## Recording rules

- Test `project`, `none`, and `family` contexts where the host combination
  supports them.
- Record the exact Revit build and pyRevit version reported by the live health
  check, not a remembered marketing version.
- Link only redacted evidence; never link model files, raw route bodies, Revit
  journals, usernames, or project paths.
- A warning, skipped required check, dirty/unknown build identity, or stale
  loaded module is not a pass.
- Retest after changing the Revit build, pyRevit build or engine, extension
  runtime, MCP SDK major version, or deployment method.
