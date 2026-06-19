# start-local-http.ps1
# Launch the MCP server in streamable-http mode on port 3001.

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ServerDir = Resolve-Path (Join-Path $ScriptDir "..\mcp-server")
$VenvDir = Join-Path $ServerDir ".venv"

# Determine python executable path
$PythonExe = Join-Path $VenvDir "Scripts\python.exe"
if (-not (Test-Path $PythonExe)) {
    # Try non-Windows structure (mac/linux)
    $PythonExe = Join-Path $VenvDir "bin/python"
}

if (-not (Test-Path $PythonExe)) {
    Write-Host "ERROR: Virtual environment not found. Please run setup-mcp-server.ps1 first." -ForegroundColor Red
    exit 1
}

# Run server in streamable-http mode
Set-Location $ServerDir
& $PythonExe main.py --transport streamable-http
