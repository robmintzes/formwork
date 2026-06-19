# Handoff - pyRevit MCP Bridge and Onboarding Documentation

This handoff details the status of adding the Model Context Protocol (MCP) server bridge and developer documentation.

---

## State
* **Developer Guides**:
  * [DOCUMENTATION_GUIDE.md](file:///Users/bert/dev/pyrevit-toolbar-template/docs/onboarding/DOCUMENTATION_GUIDE.md): Explains documentation standards and validation rules.
  * [MCP_GUIDE.md](file:///Users/bert/dev/pyrevit-toolbar-template/docs/onboarding/MCP_GUIDE.md): Explains the localhost MCP server architecture and config steps.
  * [tool-guide-template.md](file:///Users/bert/dev/pyrevit-toolbar-template/docs/templates/tool-guide-template.md): Reusable skeleton for individual tool documentation.
* **pyRevit routes**:
  * Programmed route listener and hot-reload dispatcher inside the `mcp` subpackage of the `Placeholder.extension`.
  * Exposed `/placeholder/health/` and `/placeholder/project/info|levels|worksets|links/` endpoints.
* **FastMCP Server**:
  * Configured local FastMCP server in `servers/revit-mcp/mcp-server`.
  * Created setup and launch script utilities.
* **Bootstrapper**:
  * Updated `bootstrap.ps1` to automatically rebrand route paths and URLs.

---

## Open
* **Staged Write Prototypes**: Future phases could introduce safe write operations (e.g. view template renames) with Revit-side user approval dialogs.
* **Extended Standards Audits**: Adding custom rules matching firm standards (e.g., naming conventions check) to the MCP server audits.

---

## Incremental Edit Log
* **2026-06-19**: Created onboarding developer docs and reusable templates. Created `mcp` routing structure inside `Placeholder.extension/lib/mcp/` using Rockwell's hot-reloading architecture. Programmed and verified the local Python FastMCP server and its launch scripts. Expanded the rebranding bootstrapper. Checked syntax and validated the template.
