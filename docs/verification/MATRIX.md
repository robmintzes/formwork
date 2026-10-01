# Live host verification matrix

No Windows/Revit/pyRevit combination has passed live verification yet. Add a
row only after the redacted evidence report exists and every required automated
and manual check passes.

| Revit | Revit build | pyRevit | Python engine | OS | Contexts | Git SHA | Evidence | Status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| _No verified combinations_ |  |  |  |  |  |  |  | Not tested |

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
