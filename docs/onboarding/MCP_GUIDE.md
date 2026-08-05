# Revit Model Context Protocol (MCP) Bridge Guide

This repository includes an alpha, localhost-only **Model Context Protocol
(MCP)** bridge foundation. It is designed to let MCP clients read structured
metadata from an active Revit session through pyRevit Routes.

> **Verification status:** automated contract tests cover the external Python
> server, but this bridge has not yet completed an end-to-end test in a live
> Revit/pyRevit session. The documented endpoints and lifecycle behavior still
> require live verification before operational use.

---

## 1. System Architecture

The MCP bridge consists of two main components working together on your local machine:

```
┌────────────────────────┐              ┌────────────────────────┐
│                        │              │                        │
│   AI Agent / Client    │  ◄──stdIO──► │    Python MCPServer    │
│  (Claude, Cursor, etc) │              │    Server (Port 3001)  │
│                        │              │                        │
└────────────────────────┘              └───────────▲────────────┘
                                                    │
                                                  HTTP
                                                    │
┌────────────────────────┐              ┌───────────▼────────────┐
│      Autodesk          │              │    pyRevit Routes      │
│     Revit App          │  ◄─────────► │    Extension Listener  │
│                        │              │    (Port 48884)        │
└────────────────────────┘              └────────────────────────┘
```

1. **pyRevit Routes Extension (Inside Revit)**:
   - Registers route endpoints using pyRevit's built-in routes engine.
   - Binds to `http://127.0.0.1:48884/placeholder`.
   - Runs in the Revit main thread to safely access Revit API objects (`doc`, `uidoc`).
   - Dispatches route handlers from the loaded extension runtime.

2. **Python MCP Server (Outside Revit)**:
   - Runs in a local Python virtual environment.
   - Binds to `http://127.0.0.1:3001` or standard input/output (stdio).
   - Translates high-level MCP tool requests (e.g. `revit_project_info`) into Revit-Routes HTTP queries, returning normalized responses.

---

## 2. Setup & Installation

### Step 1: Enable pyRevit Routes
Ensure pyRevit Routes is activated in your local Revit environment.
1. Open PowerShell and verify configurations:
   ```powershell
   pyrevit configs routes
   ```
2. If it is disabled or bound to a different port, run:
   ```powershell
   pyrevit configs routes enable
   pyrevit configs routes port 48884
   ```
3. Restart Revit so the routing engine loads.

### Mandatory Routes reload rule

After clicking **pyRevit Reload**, do **not** call a route. Before the first
request, either fully restart Revit or toggle pyRevit Routes off and back on.
Reloading extension code does not safely refresh the already-running Routes
listener, and calling it in that state can destabilize or crash Revit.

### Step 2: Install the pyRevit Extension
From PowerShell in the repository root:
```powershell
.\scripts\install-extension.ps1
```
In Revit, click **pyRevit -> Reload** to refresh the toolbar. Then fully restart
Revit, or toggle Routes off and on, before sending the first MCP/HTTP request.

### Step 3: Setup the MCP Server Virtual Environment
Install CPython 3.10 or newer and make `python` available on `PATH`. The external
server does not use Revit's embedded Python runtime. Then build the local virtual
environment and install dependencies:
```powershell
.\servers\revit-mcp\scripts\setup-mcp-server.ps1
```

---

## 3. Running the Server

### stdio Mode (Default)
Recommended for integrations with Claude Desktop and Cursor where the client launches the process:
```powershell
.\servers\revit-mcp\scripts\start-stdio.ps1
```

### HTTP Mode
Recommended for the MCP Inspector and Codex CLI:
```powershell
.\servers\revit-mcp\scripts\start-local-http.ps1
```
This runs the server at `http://127.0.0.1:3001/mcp`. You can inspect the tools list by connecting the [MCP Inspector](https://github.com/modelcontextprotocol/inspector):
```bash
npx @modelcontextprotocol/inspector http://127.0.0.1:3001/mcp
```

Keep both the MCP server and pyRevit Routes bound to loopback. This alpha bridge
does not provide the authentication and origin policy required for remote or
shared-network exposure.

---

## 4. Connecting AI Clients

### Claude Desktop
Add this to your `claude_desktop_config.json` (typically located at `%APPDATA%\Claude\claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "revit-mcp": {
      "command": "powershell.exe",
      "args": [
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        "C:\\path\\to\\your\\repo\\servers\\revit-mcp\\scripts\\start-stdio.ps1"
      ]
    }
  }
}
```

### Cursor
1. Go to **Settings** -> **Features** -> **MCP**.
2. Click **+ Add New MCP Server**.
3. Fill out the dialog:
   - **Name**: `revit-mcp`
   - **Type**: `command`
   - **Command**: `powershell -NoProfile -ExecutionPolicy Bypass -File C:\path\to\your\repo\servers\revit-mcp\scripts\start-stdio.ps1`

---

## 5. Standard Tools Catalog

* `revit_health_ping`: Verifies that Revit is open, the extension is loaded, and a document is open.
* `revit_project_info`: Retrieves active model metadata (title, file path, name, client, number, status).
* `revit_project_levels`: Returns all levels sorted by elevation.
* `revit_project_worksets`: Lists all user worksets in workshared projects.
* `revit_project_links`: Scans for linked Revit models and CAD files.

These tools are intended to be read-only. Confirm that behavior during the live
Revit verification pass before connecting a client to a production model.
