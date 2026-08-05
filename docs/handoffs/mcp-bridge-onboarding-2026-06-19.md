# Handoff - pyRevit MCP Bridge and Onboarding Documentation

This handoff details the status of adding the Model Context Protocol (MCP) server bridge and developer documentation.

---

## State
* **Developer Guides**:
  * [DOCUMENTATION_GUIDE.md](../onboarding/DOCUMENTATION_GUIDE.md): Explains documentation standards and validation rules.
  * [MCP_GUIDE.md](../onboarding/MCP_GUIDE.md): Explains the localhost MCP server architecture, reload safety rule, and config steps.
  * [tool-guide-template.md](../templates/tool-guide-template.md): Reusable skeleton for individual tool documentation.
* **pyRevit routes**:
  * Added the route listener and handler dispatcher inside the namespaced
    `revit_mcp_bridge` package of the `Placeholder.extension`; route calls still
    require the documented restart or Routes toggle after pyRevit Reload.
  * Exposed `/placeholder/health/` and `/placeholder/project/info|levels|worksets|links/` endpoints.
* **MCP Server**:
  * Migrated the local Python server to the public MCP SDK v2 API and enforced
    loopback-only binding while the foundation has no authentication layer.
  * Created setup and launch script utilities.
* **Bootstrapper**:
  * Python and PowerShell bootstrappers declare the same rebranding surfaces.
    The Python output is exercised as a generated repository; PowerShell still
    needs a Windows execution smoke test.
* **Stabilization status (2026-08-04)**:
  * Repository validators now cover required author metadata, 32x32 icons, tool
    integrity, tab metadata, tool guides, risk/lifecycle enums, path/type
    alignment, and bundle-title drift.
  * CI now runs generated-repository regressions, pyRevit compatibility tests,
    static checks, and the MCP pytest suite using declared test requirements.
  * Public docs describe the repository as an alpha foundation and use portable
    links.
  * No live Revit/pyRevit test has been completed.

---

## Open
* **Live Revit verification**: Test ribbon loading, the sample tool, every route,
  MCP calls, cancellation/error paths, and the Routes reload/restart sequence in
  each supported Revit/pyRevit runtime. Do not mark this complete from static
  tests alone.
* **Project generator UX**: Replace the destructive, one-shot bootstrap scripts
  with the configuration-first CLI described in [ROADMAP.md](../ROADMAP.md),
  then evaluate a graphical wizard.
* **Windows bootstrap smoke test**: Execute the PowerShell bootstrapper and the
  generated validation suite on a clean supported Windows workstation.
* **Staged Write Prototypes**: Future phases could introduce safe write operations (e.g. view template renames) with Revit-side user approval dialogs.
* **Extended Standards Audits**: Adding custom rules matching firm standards (e.g., naming conventions check) to the MCP server audits.

---

## Incremental Edit Log
* **2026-06-19**: Created onboarding developer docs, reusable templates, the MCP
  routing structure, external Python MCP server, launch scripts, and bootstrap
  replacements. Static syntax and template checks were run; live Revit
  verification was not recorded.
* **2026-08-04**: Strengthened validator and CI coverage; brought the Python and
  PowerShell bootstrap manifests into parity; rejected unsafe generator names;
  migrated the MCP server to SDK v2; namespaced the embedded bridge package;
  corrected production-readiness claims and absolute links; and documented the
  mandatory Routes reset after pyRevit Reload. Live Revit verification remains
  open.
