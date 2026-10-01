# pyRevit Toolbar Specification

This document is the machine-parseable and human-readable specification of the toolbar ribbon layout. AI coding agents use this file to understand where tools should be created, what parameters they require, and what risk classification they hold.

---

# [TB-PLACEHOLDER-TOOLS] Placeholder Tools Tab

```yaml
tab:
  id: placeholder-tools
  display_name: Placeholder Tools
  purpose: template
  audience: general_users
  lifecycle_stage: sandbox
  repo_extension_path: extensions/Placeholder.extension
  source_path: extensions/Placeholder.extension/PlaceholderTab.tab
```

> The default sandbox tab for template tools.

## [TB-PLACEHOLDER-TOOLS-PANEL] Placeholder Panel

```yaml
tools:
  - id: hello-button
    display_name: Hello Button
    type: PushButton
    category: utility
    risk: Low
    lifecycle_stage: sandbox
    description: Displays a read-only greeting with the active project, active view, and non-template view count.
    source_path: extensions/Placeholder.extension/PlaceholderTab.tab/PlaceholderPanel.panel/HelloButton.pushbutton
```
