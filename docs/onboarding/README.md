# Developer Onboarding & Operating Model

Welcome to the alpha pyRevit toolbar development foundation. This document
outlines local setup, branch ownership, packaging, and safety expectations. It
does not imply that the template has completed live Revit verification or is
ready for managed firm-wide deployment.

---

## 1. Local Development Setup

To link this repository's extension folder directly to your Revit environment:

1. Open PowerShell and run:
   ```powershell
   .\scripts\install-extension.ps1
   ```
2. Open Revit and click **pyRevit -> Reload** to refresh the toolbar UI.
3. Changes under `extensions/` should appear after reload when the extension is
   registered correctly.

> **Routes safety rule:** if the MCP bridge is enabled, do not call a route
> after **pyRevit Reload**. Fully restart Revit, or toggle pyRevit Routes off and
> back on, before the first route request. See [MCP_GUIDE.md](MCP_GUIDE.md).

---

## 2. Git Branch Policy

Follow [BRANCH_POLICY.md](BRANCH_POLICY.md) for the canonical policy and setup.
All contributions use a human-owned development branch and a pull request into
`main` (or a future `stable` integration branch), including documentation edits.
This repository's maintenance prefix is `robmintzes`, for example
`robmintzes/add-purge-button`; another developer uses their own human prefix.

Install the local commit/push guards once per clone:

```powershell
.\scripts\install-git-hooks.ps1 -Owner robmintzes
```

Before editing, check the working tree and branch:

```powershell
git status --short --branch
py -3.11 validators/check_branch_policy.py
```

GitHub enforces the pull-request and CI gates independently of local hooks.
Passing static checks does not establish live Revit compatibility or production
readiness.

---

## 3. The Deploy Workflow

The current scripts support local packaging and registration only:

- `scripts/package-extension.ps1` creates ZIP files under `dist/`; it does not
  upload, sign, checksum, version, or deploy them.
- `scripts/install-extension.ps1` attempts to register the local `extensions/`
  directory with pyRevit; it does not install a release ZIP or remote repository.
- Firm-wide rollout, rollback, and update policy must be designed and tested by
  the adopting firm before production use.

---

## 4. Working safely with Revit

Always remember the golden rules of Revit scripting:
- Check document context (family vs project) before running UI.
- Never open a transaction when showing a dialog.
- Explicitly catch exceptions (especially user cancels) so the UI exits gracefully.
- Read data from links; do not write to them.

## 5. Verification boundary

Run all repository validators and automated tests before opening Revit. Then
perform a separate live test against each supported Revit/pyRevit combination,
including ribbon load, cancel paths, read/write behavior, and Routes lifecycle.
Use the evidence-producing [Windows and live Revit verification
procedure](../verification/README.md). That live matrix has not yet been
completed for this repository.
