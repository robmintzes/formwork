# Developer Onboarding & Operating Model

Welcome to the custom pyRevit toolbar development workspace. This document outlines how to organize branches, deploy toolbars, and write code consistent with our team policies.

---

## 1. Local Development Setup

To link this repository's extension folder directly to your Revit environment:
1. Open PowerShell and run:
   ```powershell
   .\scripts\install-extension.ps1
   ```
2. Open Revit, click **pyRevit -> Reload**.
3. Any changes you make under the `extensions/` directory will be visible immediately (or after clicking pyRevit Reload).

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

For multi-machine/firm-wide distribution, we package and deploy toolbars via configuration:
- Local scripts under `scripts/` package the extension into a standard ZIP folder.
- In larger deployments, we use `scripts/package-extension.ps1` to upload packaged bundles to shared network drives or release tags.
- Non-developers can install the toolbar by running the `scripts/install-extension.ps1` script pointing to the release zip or repository remote.

---

## 4. Working safely with Revit

Always remember the golden rules of Revit scripting:
- Check document context (family vs project) before running UI.
- Never open a transaction when showing a dialog.
- Explicitly catch exceptions (especially user cancels) so the UI exits gracefully.
- Read data from links; do not write to them.
