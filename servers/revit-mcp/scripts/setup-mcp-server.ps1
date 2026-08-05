# setup-mcp-server.ps1
# Setup Python virtual environment and install dependencies.

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ServerDir = Resolve-Path (Join-Path $ScriptDir "..\mcp-server")
$VenvDir = Join-Path $ServerDir ".venv"

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "         Revit MCP Server Setup           " -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

# Check if Python is installed
try {
    $PythonVer = & python --version 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "python --version failed with exit code $LASTEXITCODE"
    }
    Write-Host "Found Python: $PythonVer" -ForegroundColor Gray
} catch {
    Write-Host "ERROR: Python is not installed or not in PATH." -ForegroundColor Red
    exit 1
}

# MCP SDK v2 and this server require CPython 3.10 or newer.
& python -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)"
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Python 3.10 or newer is required. Found: $PythonVer" -ForegroundColor Red
    exit 1
}

# Create venv if not exists
if (-not (Test-Path $VenvDir)) {
    Write-Host "Creating virtual environment at $VenvDir..." -ForegroundColor Gray
    & python -m venv $VenvDir
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Python failed to create the virtual environment." -ForegroundColor Red
        exit 1
    }
    Write-Host "Virtual environment created." -ForegroundColor Green
} else {
    Write-Host "Virtual environment already exists." -ForegroundColor Gray
}

# Determine python executable path
$PythonExe = Join-Path $VenvDir "Scripts\python.exe"
if (-not (Test-Path $PythonExe)) {
    # Try non-Windows structure (mac/linux)
    $PythonExe = Join-Path $VenvDir "bin/python"
}

if (-not (Test-Path $PythonExe)) {
    Write-Host "ERROR: Could not find Python executable inside virtual environment." -ForegroundColor Red
    exit 1
}

$VenvPythonVer = & $PythonExe --version 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: The virtual-environment Python could not start." -ForegroundColor Red
    exit 1
}
& $PythonExe -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)"
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: The existing virtual environment uses $VenvPythonVer; Python 3.10 or newer is required." -ForegroundColor Red
    Write-Host "Create a compatible environment at: $VenvDir" -ForegroundColor Yellow
    exit 1
}

# Upgrade pip and install requirements
Write-Host "Upgrading pip..." -ForegroundColor Gray
& $PythonExe -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Failed to upgrade pip in the virtual environment." -ForegroundColor Red
    exit 1
}

$RequirementsFile = Join-Path $ServerDir "requirements.txt"
if (Test-Path $RequirementsFile) {
    Write-Host "Installing dependencies from requirements.txt..." -ForegroundColor Gray
    & $PythonExe -m pip install -r $RequirementsFile
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Dependency installation failed." -ForegroundColor Red
        exit 1
    }
    Write-Host "Dependencies installed successfully!" -ForegroundColor Green
} else {
    Write-Host "ERROR: requirements.txt not found at $RequirementsFile." -ForegroundColor Red
    exit 1
}

& $PythonExe -c "from mcp.server import MCPServer; import httpx, pydantic"
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Installed MCP dependencies failed their import check." -ForegroundColor Red
    exit 1
}

Write-Host "`nSetup complete!" -ForegroundColor Green
Write-Host "You can now run:" -ForegroundColor Gray
Write-Host "  .\start-stdio.ps1" -ForegroundColor Yellow
Write-Host "==========================================" -ForegroundColor Cyan
