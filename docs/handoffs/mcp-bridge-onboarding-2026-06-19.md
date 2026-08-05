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
    CI exercises the Python output, Windows PowerShell 5.1, and PowerShell 7;
    live workstation onboarding remains unverified.
* **Stabilization status (2026-08-04)**:
  * Repository validators now cover required author metadata, 32x32 icons, tool
    integrity, tab metadata, tool guides, risk/lifecycle enums, path/type
    alignment, and bundle-title drift.
  * CI now runs generated-repository regressions, pyRevit compatibility tests,
    static checks, and the MCP pytest suite using declared test requirements.
  * Public docs describe the repository as an alpha foundation and use portable
    links.
  * No live Revit/pyRevit test has been completed.
* **Verification harness (2026-08-04)**:
  * Added cross-platform authoring and Revit-host diagnostics.
  * Added loopback-only verification for every documented Routes endpoint and
    MCP tool, expected document contexts, manual checks, and redacted evidence.
  * Added a Windows wrapper that refuses live requests until the human confirms
    Revit was restarted or Routes was reset after pyRevit Reload.

---

## Open
* **Live Revit verification**: Test ribbon loading, the sample tool, every route,
  MCP calls, cancellation/error paths, and the Routes reload/restart sequence in
  each supported Revit/pyRevit runtime. Do not mark this complete from static
  tests alone. Follow [the verification procedure](../verification/README.md)
  and retain its redacted evidence.
* **Project generator UX**: Replace the destructive, one-shot bootstrap scripts
  with the configuration-first CLI described in [ROADMAP.md](../ROADMAP.md),
  including staged output and failure recovery, then evaluate a graphical
  wizard. Until then, discard a partially modified bootstrap copy rather than
  rerunning it.
* **Windows workstation onboarding**: Repeat the CI-covered bootstrap and setup
  sequence on the supported workstation before beginning live Revit checks.
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
* **2026-08-04**: Added portable environment diagnostics, read-only Routes/MCP
  verification, manual-check ingestion, redacted JSON/Markdown evidence, a
  guarded Windows runner, and honest result exit codes. Corrected stale pyRevit
  extension-path CLI usage and repaired unsupported Revit API memory claims.
* **2026-08-04**: Mac-side verification passed 72 root tests, 11 extension
  compatibility tests, 17 MCP tests in a disposable environment, and all three
  repository validators. PowerShell execution and live Revit behavior remain
  explicit Windows gates rather than inferred successes.
