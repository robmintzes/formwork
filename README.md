# pyRevit Agentic Toolkit Foundation

An early-stage, firm-neutral foundation for teams building a governed pyRevit
toolbar and a local, read-only Revit MCP bridge with AI coding agents.

Live Revit/pyRevit verification remains outstanding. See the [September 2026 repository assessment](docs/reviews/repository-state-2026-09-30.md) for the distinction between `main` and the unmerged stabilization work.

Before developing, install the local Git guards and follow the [branch policy](docs/onboarding/BRANCH_POLICY.md). All contributions use a human-owned branch and a pull request.

> **Alpha status:** the repository has static validation and automated Python
> tests, but it has not yet completed an end-to-end test inside a live Revit and
> pyRevit session. Treat it as a development foundation, not a production-ready
> deployment system.

## Current scope

The repository currently provides:

- vendor-neutral agent instructions and a pyRevit authoring playbook;
- a neutral sample pyRevit extension with toolbar, bundle, and tool-doc specs;
- a localhost-only, read-only MCP bridge foundation;
- standard-library validators for bundle structure, metadata, icons, safety
  patterns, toolbar coverage, and spec-to-bundle alignment;
- CI coverage for validator regressions, generated structure, and the MCP server;
- PowerShell packaging and verified local pyRevit registration helpers;
- cross-platform environment diagnostics and a redacted live Revit verification
  harness.

It does **not** yet provide an update-safe setup wizard, managed firm-wide
deployment, authenticated remote MCP access, or completed live Revit
verification. Those are roadmap work, not implied capabilities.
See the [toolkit roadmap](docs/ROADMAP.md) for the proposed configuration-first
onboarding architecture and delivery phases.

## Repository layout

```text
pyrevit-toolbar-template/
├── .agents/skills/pyrevit-tool/       # pyRevit authoring playbook
├── .github/workflows/ci.yml           # repository and MCP test pipeline
├── docs/
│   ├── design/                        # neutral WPF and HTML design guidance
│   ├── handoffs/                      # durable work-in-progress state
│   ├── memory/                        # Revit-version API overlays
│   ├── onboarding/                    # developer and MCP setup guides
│   ├── templates/                     # reusable documentation templates
│   └── toolbar/                       # ribbon spec and per-tool guides
├── extensions/Placeholder.extension/ # deployable pyRevit extension root
├── scripts/                           # bootstrap, install, and package helpers
├── servers/revit-mcp/                 # local MCP-to-pyRevit Routes bridge
├── tests/                             # validator and generation regression tests
└── validators/                        # static repository guardrails
```

Repository instructions, specs, tests, and documentation stay outside the
extension root so only `extensions/*.extension` needs to be registered with
pyRevit.

## Start locally

### 1. Run the repository checks

Use CPython 3.10 or newer. From the repository root:

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

### 2. Rebrand a working copy

The current bootstrap scripts mutate the checkout in place. Run one of them
once on a clean feature branch or disposable copy:

```bash
python scripts/bootstrap.py --firm "Example Firm" --extension "ExampleTools"
```

```powershell
.\scripts\bootstrap.ps1 -FirmName "Example Firm" -ExtensionName "ExampleTools"
```

The two implementations declare the same replacement surfaces. CI exercises
the Python generator plus both Windows PowerShell 5.1 and PowerShell 7 in paths
containing spaces. Neither script is an update-safe project generator, and live
workstation onboarding remains a separate verification gate. A bootstrap error
can leave its working copy partially changed; discard that copy or restore the
feature branch before retrying instead of running the script again in place.

### 3. Register the extension with pyRevit

On a Windows workstation with the pyRevit CLI available:

```powershell
.\scripts\install-extension.ps1
```

The script attempts to register this repository's `extensions/` directory. If
the CLI is unavailable, add that directory through pyRevit's custom extension
settings.

If you are also using the MCP bridge, read the mandatory Routes reload rule in
the [MCP guide](docs/onboarding/MCP_GUIDE.md) before making a request.

### 4. Produce live Windows/Revit evidence

The guarded Windows runner checks prerequisites and exercises every documented
read-only Routes endpoint and MCP tool while retaining no raw project data:

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

Automated tests exercise the Python validators, bootstrap structure, and MCP
server contract. The verification harness can record live results, but static
checks cannot prove Revit API behavior, pyRevit ribbon loading, Routes lifecycle
behavior, or transaction safety at runtime.

No live Revit/pyRevit verification has been completed for this stabilization
slice. The active checklist and blockers are recorded in
[docs/handoffs/mcp-bridge-onboarding-2026-06-19.md](docs/handoffs/mcp-bridge-onboarding-2026-06-19.md).

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE).
