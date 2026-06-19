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
    Write-Host "Found Python: $PythonVer" -ForegroundColor Gray
} catch {
    Write-Host "ERROR: Python is not installed or not in PATH." -ForegroundColor Red
    exit 1
}

# Create venv if not exists
if (-not (Test-Path $VenvDir)) {
    Write-Host "Creating virtual environment at $VenvDir..." -ForegroundColor Gray
    & python -m venv $VenvDir
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

# Upgrade pip and install requirements
Write-Host "Upgrading pip..." -ForegroundColor Gray
& $PythonExe -m pip install --upgrade pip

$RequirementsFile = Join-Path $ServerDir "requirements.txt"
if (Test-Path $RequirementsFile) {
    Write-Host "Installing dependencies from requirements.txt..." -ForegroundColor Gray
    & $PythonExe -m pip install -r $RequirementsFile
    Write-Host "Dependencies installed successfully!" -ForegroundColor Green
} else {
    Write-Host "WARNING: requirements.txt not found." -ForegroundColor Yellow
}

Write-Host "`nSetup complete!" -ForegroundColor Green
Write-Host "You can now run:" -ForegroundColor Gray
Write-Host "  .\start-stdio.ps1" -ForegroundColor Yellow
Write-Host "==========================================" -ForegroundColor Cyan
