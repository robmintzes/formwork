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
| B11 | Live gate: Revit 2026 + pyRevit 6.5.5 + IronPython 2.7.12 via `formwork verify revit`, generated BIMxBert workspace installed | B7, PR #2 review | C/H (combination) | partial: the generated-workspace check passed on 2026-10-01 ([MATRIX](../verification/MATRIX.md); three defects found and fixed first). Not run: `formwork verify revit` (Routes and MCP) |
| B12 | Governance adapter: AGENTS.md, agent shims, branch policy/hooks, ruleset JSON from `maintainers` | B7 | C | done |
| B13 | Template overrides (done: `firm/overrides/`); `config migrate` and three-way upgrade merge (todo, wait for a schema v2) | B8 | P | partial |
| B14 | Wizard (`formwork serve`) per ADR 0006 | B8, B10 | C (wizard), P (stack) | done (spec section 7; clicked through in a browser, not yet used by an adopter) |
| B15 | Retire `scripts/bootstrap.*` once `init`/`render` cover the sample; update CI windows-smoke | B8 | P | done |
| B16 | Engine distribution to adopters: pinned checkout now, PyPI `formwork-dt` after B11; vendoring rejected (ADR 0009) | B8 | H | done (decision); publishing is B22 |
| B17 | Permanent product/repository name: Formwork, repo robmintzes/formwork (ADR 0008) | - | H | done |
| B21 | Rename the `toolkit` CLI, `toolkit_*` packages, and `.toolkit/` state folder to `formwork` (ADR 0010); `python -m toolkit_cli` alias; pre-0.3 workspaces migrate on render | B17 | C | done (0.3.0-alpha.1) |
| B22 | Publish `formwork-dt` to PyPI: `pyproject.toml`, `formwork` console script, release tags, release checklist (ADR 0009) | B11, B21 | C (plan), H (go-ahead to publish) | todo - after B11 |
| B23 | Remove the `toolkit_cli` alias (0.4.0) | B21 | P | todo |
| B18 | Later surfaces: ~~MCP bridge in workspaces~~ (done: `mcp-bridge` surface, spec 8.1; live run pending), ~~C# add-in starter~~ (done: `revit-addin` surface, spec 8.3; builds offline for 2025-2027, never loaded in Revit), ~~Python app~~ (done: `python-app` surface, spec 8.4; stdlib CLI that renders a table as a branded HTML report, its tests run in the engine suite), ~~TypeScript app~~ (done: `web-app` surface, spec 8.4; Node 22.18+ type-stripped server and app shell, `node --test` run in the engine suite, types not checked) | B12 | C (scope), P (order) | done (live Revit run still pending for the Revit-facing parts) |
| B19 | `ui-kit` surface: themed WPF dialog kit (M0 chooser, M1 result, M2-lite selector), controls, icons, `UI Kit Demo` button; ported under ADR 0005 (R05); native renders recorded | B6, B12 | C | done (live in Revit 2026 on 2026-10-01; other versions not run) |
| B20 | Port the WebView2 HTML tool host (M2-M7 families): NuGet-sourced DLLs, bridge verbs, session and result shape, offline assets | B19 | P | partial: `web-host` surface done (spec 8.5, R06): host, bridge verbs, session and result shape, offline assets and a read-only M5 `Web Tool Demo`. The "NuGet-sourced DLLs" part is superseded: the host references the WebView2 assemblies Revit ships, so nothing is vendored or downloaded. Not done: M2, M3, M4, M6 and M7 scaffolds, picking (`pick_*`, hide-while-picking), the ExternalEvent helper, the write-tool pattern (`validate`/`execute` demo); Revit 2022/2023 need a firm-supplied assembly set; live in Revit 2026 on 2026-10-01, other versions not run |

Pending human actions: B11's remaining `formwork verify revit` run (Routes and MCP; requires Rob in Revit), then the
go-ahead to publish (B22). PRs #3, #2, #4, #5, and #6 merged 2026-10-01.
