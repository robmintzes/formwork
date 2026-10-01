# Live check: generated workspace in Revit

Proves that a workspace produced by `toolkit render` loads and behaves in a
real Revit/pyRevit session. Static tests, WPF snapshots, and browser renders
are separate evidence; none of them substitutes for this check.

Declared combination for the first run: **Revit 2026, pyRevit 6.5.5
(IronPython 2.7.12 default engine), Windows 11**. The sample tool is
read-only, but use a disposable copy of a project and family document anyway.

Time: about 30 minutes. Run commands from the foundation checkout.

## 1. Prepare (outside Revit)

```powershell
py -3.11 -m toolkit_cli init --profile profiles/bimxbert --workspace 'D:\Live Check\BIMxBert'
py -3.11 -m toolkit_cli render --workspace 'D:\Live Check\BIMxBert'
pyrevit extensions paths add 'D:\Live Check\BIMxBert\extensions'
New-Item -ItemType Directory -Force .logs\workspace-verification | Out-Null
Copy-Item docs\verification\workspace-manual-checks.template.json .logs\workspace-verification\manual-checks.json
```

The workspace path is your choice. It must be outside this checkout. The
`pyrevit extensions paths add` line is the only step that changes pyRevit
configuration; step 5 undoes it. `.logs/` is git-ignored.

`scripts\verify-generated-workspace.ps1 -Mode Prepare|Record|Unregister`
wraps the same steps where script policy allows. On the reference workstation,
Cylance Script Control blocks it, so the plain commands above are the
supported path.

## 2. Exercise it in Revit

Open `.logs\workspace-verification\manual-checks.json` and work through each
check's `step`, in order. Set `status` to `pass`, `fail`, `warn`, `skip`, or
`not_run`. Keep every check, and leave `required` unchanged: the verifier fails
a checklist that drops checks or makes them optional.

Notes you add to the file are not copied into evidence. Only `id`,
`required`, and `status` are recorded. Keep project names and paths out of
the file anyway.

The checks cover:

- pyRevit Reload;
- the tab, panel, and button appear;
- light and dark theme icons;
- tooltip and F1 help URL;
- no-document, family, and project contexts;
- the read-only proof (nothing in Undo);
- a clean shutdown;
- optionally, a second (Quillmoor) workspace loaded side by side.

## 3. Record evidence

```powershell
py -3.11 -m toolkit_cli verify workspace --workspace 'D:\Live Check\BIMxBert' --manual-checks .logs\workspace-verification\manual-checks.json --revit-version 2026
```

Exit `0` is a pass; `1` is a failure; `2` is incomplete (pending checks or no
declared Revit version). The automated checks confirm:

- the workspace still matches its inputs (a dry-run render reports no changes);
- the validators pass;
- pyRevit's version is readable;
- the workspace extensions folder is registered.

Evidence is written to `.logs/workspace-verification/<UTC>/` as JSON and
Markdown. It holds outcomes and versions only.

## 4. Publish the result

Add a row to [MATRIX.md](MATRIX.md) with the Revit build, pyRevit version,
engine, OS, contexts covered, git SHA, and outcome. Commit the Markdown
evidence on a task branch. Copy it out of `.logs/` first, and do not commit
anything that names a project. A failure is still evidence: record it and open
an issue rather than re-running until it passes.

## 5. Clean up

```powershell
pyrevit extensions paths forget 'D:\Live Check\BIMxBert\extensions'
```

Then reload pyRevit. Delete the workspace folder yourself if you no longer
need it; no script here deletes files.

## Relationship to the foundation live gate

This check covers *generated* workspaces. The foundation's own sample and
read-only Routes/MCP bridge are verified separately with
`python -m toolkit_cli verify revit ... --routes-reset-confirmed` (see
[README.md](README.md)). That procedure's mandatory reset rule still applies:
after a pyRevit Reload, restart Revit or toggle Routes before the first route
request. Workspaces that list the `mcp-bridge` surface carry a copy of the
bridge (see `docs/onboarding/MCP_GUIDE.md` in the workspace); its Routes
checks are not part of the checklist above and need their own live run.
Workspaces without that surface have no Routes step.
