# pyRevit Toolbar Template: a design technology foundation

**What this is now:** a foundation that generates a firm's own design
technology workspace (branded pyRevit toolbar, WPF UI kit, HTML guides,
agent-neutral governance, and a read-only MCP bridge) from a small
configuration. You do not rebrand this repository; you generate a separate
workspace from it and regenerate when your inputs change.

> **Alpha.** Generation, validators, and automated tests pass. **No live
> Revit/pyRevit verification has been completed**, and a C# add-in starter does
> not exist yet. Treat it as a development foundation, not a production
> deployment system.

- **Adopting it?** Read the [adoption guide](docs/onboarding/ADOPTING.md).
- **Want the contracts?** See the [foundation specification](docs/product/FOUNDATION_SPEC.md).
- **Fastest start:** `python -m toolkit_cli serve` opens the local onboarding
  wizard (loopback only; it prints a link with a per-launch token).
- **Contributing?** Follow the [branch policy](docs/onboarding/BRANCH_POLICY.md):
  a human-owned branch and a pull request for every change.

Profiles are the inputs to generation. `profiles/bimxbert` is the default (the
BIMxBert name and marks are **not** MIT-licensed; see its `NOTICE-brand.md`).
`profiles/quillmoor` is a fictional firm that proves identity is data. The
foundation code is MIT.

```powershell
python -m toolkit_cli config validate --firm profiles/quillmoor
python -m toolkit_cli init --profile profiles/quillmoor --workspace "D:\Work\quillmoor-dt"
python -m toolkit_cli render --workspace "D:\Work\quillmoor-dt" --dry-run
python -m toolkit_cli render --workspace "D:\Work\quillmoor-dt"
python -m toolkit_cli validate --workspace "D:\Work\quillmoor-dt"
```

Repeat renders are no-ops, edited generated files are reported as conflicts
instead of overwritten, and firm-owned tools are never touched.

The [September 2026 repository assessment](docs/reviews/repository-state-2026-09-30.md)
records the distinction between `main` and earlier unmerged stabilization work.

## Surfaces

A firm enables surfaces in `firm.json`. All are generated and tested; none is
live-verified in Revit yet.

| Surface | Produces |
| --- | --- |
| `pyrevit-sample` | pyRevit extension with a read-only Hello Button, icons, spec fragment, tool guide |
| `wpf-specimen` | Themed WPF resource dictionaries, specimen window, PowerShell runner, bundled fonts |
| `html-guide` | Self-contained offline guide with the firm's brand |
| `governance` | `AGENTS.md` and thin agent pointers, branch policy, hooks, CI, GitHub ruleset JSON |
| `mcp-bridge` | Read-only pyRevit Routes bridge and external FastMCP server |
| `ui-kit` | Themed WPF dialogs (chooser, selector, result), controls, icons, `UI Kit Demo` button |

Not built yet: a C# add-in starter, application starters, managed firm-wide
deployment, authenticated remote MCP, and the WebView2 tool host. See the
[backlog](docs/product/BACKLOG.md) and the [toolkit roadmap](docs/ROADMAP.md).

This checkout also still carries the original neutral sample extension
(`extensions/Placeholder.extension`), a local read-only MCP bridge, and
standard-library validators for bundle structure, metadata, icons, safety
patterns, and toolbar spec alignment. Generated workspaces vendor the
validators and bridge from here.

## Repository layout

```text
pyrevit-toolbar-template/
├── .agents/skills/pyrevit-tool/       # pyRevit authoring playbook
├── .github/workflows/                 # CI and development-policy pipelines
├── docs/
│   ├── decisions/                     # architecture decision records
│   ├── design/                        # neutral WPF and HTML design guidance
│   ├── handoffs/                      # durable work-in-progress state
│   ├── memory/                        # Revit-version API overlays
│   ├── onboarding/                    # adopter guide, developer and MCP guides
│   ├── product/                       # charter, foundation spec, backlog
│   ├── reviews/                       # repository assessments
│   ├── templates/                     # reusable documentation templates
│   ├── toolbar/                       # ribbon spec and per-tool guides
│   └── verification/                  # live-check runbooks and evidence matrix
├── extensions/Placeholder.extension/  # neutral sample pyRevit extension
├── profiles/                          # bimxbert (default) and quillmoor (fictional)
├── schemas/                           # firm.json JSON Schema
├── scripts/                           # install, verification, and package helpers
├── servers/revit-mcp/                 # local MCP-to-pyRevit Routes bridge
├── tests/                             # validator and generation regression tests
├── toolkit_cli/                       # command-line entry point (python -m toolkit_cli)
├── toolkit_engine/                    # generator, adapters, templates, planner
├── toolkit_wizard/                    # local onboarding wizard service and UI
└── validators/                        # static repository guardrails
```

Repository instructions, specs, tests, and documentation stay outside the
extension root so only `extensions/*.extension` needs to be registered with
pyRevit.

## Start locally

### 1. Install the Git guards and run the repository checks

Use CPython 3.10 or newer. Install the guards once per clone (use your own
human branch prefix; see the [branch policy](docs/onboarding/BRANCH_POLICY.md)),
then run the checks from the repository root:

```powershell
.\scripts\install-git-hooks.ps1 -Owner <your-branch-prefix>
```

```bash
python -m unittest discover -s tests -v
python -m unittest discover -s extensions/Placeholder.extension/tests -v
python validators/check_bundle_structure.py
python validators/check_safety_rules.py
python validators/validate_toolbar_spec.py
```

To run the MCP tests as CI does:

```bash
python -m pip install -r servers/revit-mcp/mcp-server/requirements.txt
python -m pytest servers/revit-mcp/mcp-server/tests -q
```

Run the portable authoring diagnostic on macOS, Linux, or Windows:

```bash
python -m toolkit_cli doctor --profile authoring
```

### 2. Create your firm's workspace

Use the wizard (`python -m toolkit_cli serve`) or the CLI commands above. Copy
`profiles/quillmoor` as the starting point for your own profile. Full steps,
ownership rules, and upgrade guidance are in the
[adoption guide](docs/onboarding/ADOPTING.md). The in-place `bootstrap` scripts
that previously rebranded this checkout were retired on 2026-09-30. CI
generates both shipped profiles on Windows in paths containing spaces and
validates them.

### 3. Register an extension with pyRevit

For a generated workspace:

```powershell
pyrevit extensions paths add "D:\Work\quillmoor-dt\extensions"
```

For this checkout's neutral sample, on a Windows workstation with the pyRevit
CLI available:

```powershell
.\scripts\install-extension.ps1
```

The script attempts to register this repository's `extensions/` directory. If
the CLI is unavailable, add that directory through pyRevit's custom extension
settings.

If you are also using the MCP bridge, read the mandatory Routes reload rule in
the [MCP guide](docs/onboarding/MCP_GUIDE.md) before making a request.

### 4. Produce live Windows/Revit evidence

For a generated workspace, follow the [generated workspace live
check](docs/verification/GENERATED_WORKSPACE.md). For this checkout's own
sample and read-only Routes/MCP bridge, the guarded Windows runner checks
prerequisites and exercises every documented read-only Routes endpoint and MCP
tool while retaining no raw project data:

```powershell
.\scripts\verify-windows.ps1 -Mode Preflight
.\scripts\verify-windows.ps1 -Mode Live -ExpectedContext project -RoutesResetConfirmed
```

Read the [Windows and live Revit verification guide](docs/verification/README.md)
before using live mode. The required Routes-reset confirmation exists to
prevent the known unsafe call sequence after pyRevit Reload.

## Development model

- Read [AGENTS.md](AGENTS.md) before changing code.
- Register every new ribbon tool in
  [docs/toolbar/toolbar_spec.md](docs/toolbar/toolbar_spec.md) before creating its
  bundle directory.
- Follow the [tool documentation guide](docs/onboarding/DOCUMENTATION_GUIDE.md)
  and add `docs/toolbar/tools/<tool-id>.md`.
- Keep firm identity, paths, standards, and branding out of the public
  foundation. Apply them in a generated firm-owned workspace.
- Work on a human-owned feature branch; do not make nontrivial code changes
  directly on `main`.

## Verification status

Automated tests exercise the Python validators, workspace generation, the
wizard service, and the MCP server contract. The verification harness can
record live results, but static checks cannot prove Revit API behavior, pyRevit
ribbon loading, Routes lifecycle behavior, or transaction safety at runtime.
Native WPF and browser renders of the generated specimens were captured
separately (see `docs/verification/foundation-generator/`).

No live Revit/pyRevit verification has been completed for the foundation or for
any generated workspace; the [verification matrix](docs/verification/MATRIX.md)
has no passing combination. The active checklist and blockers for the MCP
bridge are recorded in
[docs/handoffs/mcp-bridge-onboarding-2026-06-19.md](docs/handoffs/mcp-bridge-onboarding-2026-06-19.md).

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE). The
BIMxBert name and marks in `profiles/bimxbert` are not covered by that license.
