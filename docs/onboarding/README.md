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
