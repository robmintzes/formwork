# Repo Operating Instructions for AI Agents

> Canonical, vendor-neutral instructions for any AI coding agent working in this repository (Claude Code, Google Antigravity, ChatGPT, local orchestrators).

---

## 1. How Guidance is Organized

This repository uses a structured memory layer to govern human and AI development:
- **Instructions (This File):** Root conventions, safety policies, and operating defaults.
- **Skills (Procedures):** Bounded playbooks located in `.agents/skills/`. For example, `.agents/skills/pyrevit-tool/SKILL.md` is the playbook for building ribbon buttons.
- **UX Design Standards:** Located in `docs/design/DESIGN.md` (visual style rules and UI tokens), `docs/design/xaml-recipes.md` (WPF forms), and `docs/design/html-recipes.md` (HTML reporting).
- **Toolbar Specification:** Located in `docs/toolbar/toolbar_spec.md`. This is the single source of truth for the ribbon tabs, panels, and button mappings.
- **API Memory Overlays:** Located in `docs/memory/`. Version-specific notes (e.g., `revit-2025.md`) keep models from hallucinating APIs or violating target .NET runtimes.

---

## 2. Core Conventions & Branch Policy

- **Author Attributions:** When authoring a tool or library, set `__author__` in Python files and the `author:` metadata field in `bundle.yaml` to the default Firm Name placeholder or the rebranded target. Avoid personal developer attributions on shared tools.
- **Branch Ownership:** Use `<human-owner>/<lowercase-task-slug>` (e.g., `robmintzes/feature-name`). The owner of this repository's maintenance work is `robmintzes`; other contributors use their accountable human prefix. Do not name branches after an AI agent. Local guards check the configured owner; CI checks the naming convention, which is not proof of identity.
- **Preflight Check:** Before any development edit, run `git status --short --branch` and `python validators/check_branch_policy.py`. Preserve existing work. Switch from `main`, `stable`, detached HEAD, or an incorrectly owned branch before editing. Create task branches from an up-to-date `origin/main` unless deliberately continuing an existing task. All contributions, including documentation, go through a pull request.
- **Install Local Guards:** Run `./scripts/install-git-hooks.ps1 -Owner robmintzes` once per clone (use the accountable human prefix for another developer). This installs tracked pre-commit and pre-push guards without replacing another hooks configuration. Do not bypass guards to perform development on an integration branch.
- **Merge Gate:** `main` and any future `stable` branch require a pull request, passing `branch-policy` and `repository-validation` checks against the current base, and resolved review conversations. GitHub enforcement includes admins and blocks force pushes and deletion. Automated checks do not authorize an agent to merge or release; the human decides when to merge. See [the canonical branch policy](docs/onboarding/BRANCH_POLICY.md), including its activation and single-owner review policy.
- **Spec Integrity:** Do not write code or create folder structures for a new ribbon button unless a matching entry has been registered in `docs/toolbar/toolbar_spec.md`.

---

## 3. Revit API Safety Guidelines

- **Context Validation First:** Verify the active document context (e.g., project, family, sheet) and user selection at the very start of the script, before prompting the user with dialogs or initiating database transactions.
- **Transaction Safety:** 
  - Keep transactions as short and narrow as possible.
  - Never hold a transaction open while waiting for user input or displaying a UI dialog.
  - Wrap database changes inside a try-except block with explicit transaction commit and rollback handling.
- **Linked Document Read-Only Constraint:** Models obtained via `RevitLinkInstance.GetLinkDocument()` are strictly read-only. Do not attempt to run transactions or edit elements inside linked documents; collect links as input sources, and write results into the active host document.

---

## 4. Persistent Memory & Handoff Protocol

To support long-running, multi-session tasks, this repository implements a working-state handoff system:
- **Handoff Files:** Located in `docs/handoffs/`.
- **Handoff Index:** `docs/handoffs/INDEX.md` maps active handoff files.
- **Handoff Rules:** If a task spans multiple sessions or is handed off between different AI agents/humans, write or update a handoff file (e.g., `docs/handoffs/feature-slug-YYYY-MM-DD.md`) containing:
  - `## State`: What has been completed.
  - `## Open`: Next actionable steps, blockers, and rejected paths.
  - `## Incremental Edit Log`: Short, dated bullet points outlining incremental code changes and key architectural decisions.
