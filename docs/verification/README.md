# Windows and live Revit verification

This procedure turns a Windows/Revit test session into reviewable evidence. The
verifier calls only the five documented read-only Routes endpoints and their
matching MCP tools. It does not open a Revit transaction, change a model, start
or kill Revit, or mutate pyRevit configuration.

The JSON and Markdown reports retain contract outcomes, versions, and Git
identity. They deliberately discard project titles and paths, client and
address fields, link paths, workset names and owners, usernames, hostnames, and
raw response bodies.

## On macOS before the host test

Run the authoring profile from the repository root:

```bash
python -m formwork_cli doctor --profile authoring
python -m unittest discover -s tests -v
python -m unittest discover -s extensions/Placeholder.extension/tests -v
```

Windows-only checks appear as `SKIP`; missing optional local services appear as
`WARN`. Neither is presented as live Revit success.

## Windows preflight

Open Windows PowerShell 5.1 in the repository root and run:

```powershell
git pull --ff-only

powershell.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\scripts\verify-windows.ps1 `
  -Mode Preflight
```

The first preflight is expected to report `INCOMPLETE` when the extension or MCP
environment is not installed yet. Remediate it explicitly:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\scripts\install-extension.ps1

powershell.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\servers\revit-mcp\scripts\setup-mcp-server.ps1

pyrevit configs routes enable
pyrevit configs routes port 48884
```

Run the preflight again. The installer is idempotent and verifies that
`pyrevit extensions paths` contains this repository's `extensions` directory.

## Mandatory reload safety gate

After clicking **pyRevit Reload**, do not call Routes immediately. Fully restart
Revit or toggle Routes off and back on first. The Windows verifier refuses all
live HTTP and MCP calls unless `-RoutesResetConfirmed` is supplied; the switch
is a human assertion that this reset actually happened, not a magic safety
incantation.

Use a disposable model for the first project-context run. Confirm the neutral
ribbon tab is visible and run the Hello Button once. Copy the manual checklist
and change only its `status` fields:

```powershell
Copy-Item `
  .\docs\verification\manual-checks.template.json `
  .\.logs\manual-checks.json
```

Allowed statuses are `pass`, `fail`, `warn`, `skip`, `pending`, and `not_run`.
Required `pending`, `warn`, or `skip` checks keep the result incomplete. Freeform
notes and titles are ignored so they cannot accidentally leak project data.

## Live project verification

With a project open and Revit freshly started or Routes reset:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\scripts\verify-windows.ps1 `
  -Mode Live `
  -ExpectedContext project `
  -RoutesResetConfirmed `
  -ManualChecks .\.logs\manual-checks.json
```

The run checks:

- pyRevit's built-in `/routes/status` contract;
- `/placeholder/health/`;
- project info, levels, worksets, and links Routes envelopes;
- all five matching MCP tool calls through the MCP SDK;
- exact tool identifiers and `risk_class: read_only` on every response;
- the selected project/family/no-document context;
- the supplied manual ribbon and reload checks.

## Context matrix

Repeat live verification after the same reload safety procedure for each
applicable state:

| Context | Setup | Expected project-route result |
| --- | --- | --- |
| `project` | Disposable `.rvt` project open | `status: ok` |
| `none` | Revit open with every document closed | `error.code: no_document` |
| `family` | Disposable family document open | `error.code: family_document_not_supported` |

Set `-ExpectedContext none` or `-ExpectedContext family` for those runs. The
health endpoint remains successful because it describes the host even when no
project document is available.

## Evidence and exit codes

The wrapper writes ignored local evidence beneath:

```text
.logs/windows-verification/<UTC timestamp>/
├── doctor.json
├── manual-checks.json
└── revit-live/
    ├── live-verification.json
    └── live-verification.md
```

- Exit `0`: every required check passed.
- Exit `1`: at least one check failed.
- Exit `2`: evidence is incomplete or command input is invalid.

Do not commit raw HTTP responses, Revit journals, model files, environment
files, or anything else containing project/user data. The generated evidence is
designed to be shareable, but inspect it before attaching it to an issue.

After a complete pass, add the tested combination to the [live host verification
matrix](MATRIX.md). Do not infer support for adjacent Revit or pyRevit versions.
