# Revit Model Context Protocol (MCP) Bridge Guide

This repository includes an out-of-the-box local **Model Context Protocol (MCP)** server bridge. This bridge allows AI assistants (like Claude Desktop, Cursor, or Codex CLI) to read structured metadata directly from your active Revit session via pyRevit.

---

## 1. System Architecture

The MCP bridge consists of two main components working together on your local machine:

```
┌────────────────────────┐              ┌────────────────────────┐
│                        │              │                        │
│   AI Agent / Client    │  ◄──stdIO──► │    Python FastMCP      │
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
   - Uses a **hot-reload dispatcher** so you can modify handler python scripts without restarting Revit.

2. **FastMCP Server (Outside Revit)**:
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

### Step 2: Install the pyRevit Extension
From PowerShell in the repository root:
```powershell
.\scripts\install-extension.ps1
```
In Revit, click **pyRevit -> Reload**.

### Step 3: Setup the MCP Server Virtual Environment
Build the local virtual environment and install Python dependencies:
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
