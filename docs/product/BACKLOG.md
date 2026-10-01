# First-milestone backlog

Dependency-ordered. Status: **done**, **in progress**, **todo**, **blocked**.
Requirement labels: C = confirmed, P = proposed choice, H = pending human
decision. Specification: [FOUNDATION_SPEC.md](FOUNDATION_SPEC.md).

| ID | Item | Depends on | Label | Status |
| --- | --- | --- | --- | --- |
| B0 | Stack branch on PR #2 + PR #3; resolve doc conflicts; full suite green | - | C | done |
| B1 | Spec, ADRs, backlog, release record | B0 | C | done |
| B2 | Engine core: diagnostics, strict JSON loading, firm config validation | B1 | P | done |
| B3 | DTCG subset parser, alias resolution, cycle detection, required roles, contrast | B2 | P | done |
| B4 | Path safety, manifest, planner, convergent apply, dry-run | B2 | P | done |
| B5 | Profiles: BIMxBert (vendored OFL fonts, cleaned marks) and fictional firm | B3 | C | done |
| B6 | Adapters: pyrevit-sample, wpf-specimen, html-guide, common notices | B3, B4 | C | done |
| B7 | CLI: `config validate`, `init`, `render`; JSON reports and exit codes | B4, B6 | P | done |
| B8 | Acceptance tests: repeat no-op, propagation, custom-tool preservation, conflict, offline, path boundaries, diagnostics | B7 | C | done |
| B9 | Validator updates: 32/96 icons + dark variant, toolbar spec fragments | B6 | P | done |
| B10 | Native WPF snapshot on Windows; browser screenshot; record in handoff | B6 | C | done |
| B11 | Live gate: Revit 2026 + pyRevit 6.5.5 + IronPython 2.7.12 via `toolkit verify revit`, generated BIMxBert workspace installed | B7, PR #2 review | C/H (combination) | todo - needs Rob at Revit |
| B12 | Governance adapter: AGENTS.md, agent shims, branch policy/hooks, ruleset JSON from `maintainers` | B7 | C | todo |
| B13 | `config migrate`, template overrides, three-way upgrade merge | B8 | P | todo |
| B14 | Wizard (`toolkit serve`) per ADR 0006 | B8, B10 | C (wizard), P (stack) | todo |
| B15 | Retire `scripts/bootstrap.*` once `init`/`render` cover the sample; update CI windows-smoke | B8 | P | todo |
| B16 | Engine distribution to adopters (pip, pinned checkout, vendored) | B8 | H | todo |
| B17 | Permanent product/repository name | - | H | todo |
| B18 | Later surfaces: MCP bridge in workspaces, C# add-in starter, Python app, TypeScript app | B12 | C (scope), P (order) | todo |

Pending human decisions: B11's live run (requires Rob in Revit), B16, B17,
and merge order of PR #3 -> PR #2 -> this branch.
