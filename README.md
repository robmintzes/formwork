# pyRevit Agentic Toolbar Template

A comprehensive, production-grade, AI-agent-agnostic template framework for architecture and BIM teams to scaffold, validate, and deploy custom pyRevit toolbars and extensions.

---

## Architecture Overview

This template implements a **dual-root architecture**: separating human/agent guidelines, specs, and validation code from the actual pyRevit runtime extension bundle. This ensures that repository metadata and memory structures do not clutter the deployed extension.

```text
pyrevit-toolbar-template/
├─ .github/
│  └─ workflows/
│     └─ ci.yml                          # GitHub Actions validation pipeline
├─ .agents/
│  └─ skills/
│     └─ pyrevit-tool/
│        └─ SKILL.md                     # Agentic playbook for pyRevit script authoring
├─ docs/
│  ├─ onboarding/
│  │  ├─ README.md                       # Human onboarding & branch policy
│  │  ├─ DOCUMENTATION_GUIDE.md           # Tool documentation lifecycle standard
│  │  └─ MCP_GUIDE.md                     # Local Model Context Protocol bridge guide
│  ├─ templates/
│  │  └─ tool-guide-template.md           # Reusable markdown template for new tools
│  ├─ design/
│  │  ├─ DESIGN.md                       # Editorial tokens (color, type, margins)
│  │  ├─ xaml-recipes.md                 # WPF/XAML copy-pasteable component recipes
│  │  └─ html-recipes.md                 # HTML/CSS UI and report recipes
│  ├─ toolbar/
│  │  ├─ README.md                       # Spec sheet documentation rules
│  │  └─ toolbar_spec.md                 # Machine-parseable toolbar hierarchy
│  └─ memory/
│     ├─ README.md
│     ├─ revit-2024.md                   # Revit 2024 context rules
│     ├─ revit-2025.md                   # Revit 2025 (.NET 8 runtime) rules
│     └─ revit-2027.md                   # Revit 2027 (.NET 10 runtime) rules
├─ validators/
│  ├─ check_bundle_structure.py          # Script-and-manifest static validator
│  ├─ check_safety_rules.py              # Revit API transaction & risk validator
│  └─ validate_toolbar_spec.py           # Ribbon coverage & spec validator
├─ servers/
│  └─ revit-mcp/                         # FastMCP-to-Revit bridge service
├─ scripts/
│  ├─ bootstrap.ps1                      # Rebrands this template to your firm
│  ├─ install-extension.ps1              # Hooks extension path into local pyRevit
│  └─ package-extension.ps1              # Packages extension to a distributable zip
├─ extensions/
│  └─ Placeholder.extension/             # Actual pyRevit extension folder
│     ├─ extension.json                  # Manifest
│     ├─ startup.py                      # Extension start-up code
│     ├─ lib/                            # Shared Python utility modules
│     ├─ hooks/                          # pyRevit event hooks
│     ├─ checks/                         # Pre-execution runtime checks
│     └─ PlaceholderTab.tab/             # Configured tabs, panels, and pushbuttons
├─ AGENTS.md                             # Repository operating guidelines for AI
├─ CLAUDE.md                             # AI adapter shim
└─ GEMINI.md                             # AI adapter shim
```

---

## Onboarding: Getting Started

### 1. Rebrand the Template
Run the bootstrapping script to customize the repository name, folders, and manifests for your firm:
```powershell
# Open PowerShell in the repository root and run:
.\scripts\bootstrap.ps1
```
The script will prompt you for:
- **Firm Name** (e.g., `AcmeCorp`)
- **Extension Name** (e.g., `AcmeTools`)
- **Git Remote Repository URL**

It will then automatically rename folder structures, update naming references across files, and regenerate the `extension.json` manifest.

### 2. Local Installation
Once rebranded, register your extension locally with pyRevit so it loads into Revit:
```powershell
.\scripts\install-extension.ps1
```
Open Autodesk Revit and click **pyRevit -> Reload** to view your new toolbar.

### 3. Run Static Validators
Verify file structure, toolbar coverage, and code safety:
```bash
python validators/check_bundle_structure.py
python validators/check_safety_rules.py
python validators/validate_toolbar_spec.py
```

---

## Working with AI Coding Agents

This repository is optimized for **Agentic Development** (using Claude Code, ChatGPT, Antigravity, GitHub Copilot, etc.). 

1. **Instructions (AGENTS.md):** AI agents will automatically discover and read `AGENTS.md` (and `CLAUDE.md`/`GEMINI.md` shims) to understand codebase rules, naming standards, and transaction policies.
2. **Playbooks (.agents/skills/):** The `pyrevit-tool` skill playbook instructs models on how to write safe Revit API transaction scripts, filter selection contexts, interact with linked models, and conform to the UI recipes.
3. **API Memory (docs/memory/):** Revit version overlays prevent models from hallucinating old APIs or using incompatible .NET paradigms (such as using .NET Framework libraries on Revit 2025 which requires .NET 8).
4. **Validation Guardrails:** Any code written by an agent must pass the local and CI python validators before it can merge into the production branch.

---

## License

This project is licensed under the MIT License - see the `LICENSE` file for details.
