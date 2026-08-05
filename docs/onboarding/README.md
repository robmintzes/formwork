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

We protect our production branch and require structured contribution workflows:

- **No commits directly to `main`:** All edits (except minor typos in markdown documentation) must occur on feature/bugfix branches.
- **Branch Naming Standard:** Prefixes must carry the human owner's username or prefix. For example:
  - `rmintzes/add-purge-button`
  - `jdoe/fix-selection-bug`
- **Owner Resolution:** When collaborating with AI agents, ensure the active branch prefix corresponds to your human handler name. AI agents are instructed to check this and refuse commits on detached HEADs or wrong prefixes.

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
That live matrix has not yet been completed for this repository.
