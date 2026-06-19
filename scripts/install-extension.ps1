# install-extension.ps1 — Link this local extension folder to pyRevit.
#
# Usage:
#   .\scripts\install-extension.ps1

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Resolve-Path (Join-Path $ScriptDir "..")
$ExtsDir = Join-Path $RepoRoot "extensions"

Write-Host "Registering custom extension path: $ExtsDir" -ForegroundColor Gray

# Check if pyrevit is available
if (-not (Get-Command "pyrevit" -ErrorAction SilentlyContinue)) {
    Write-Host "WARNING: 'pyrevit' CLI utility was not found in your PATH." -ForegroundColor Yellow
    Write-Host "Please register this directory manually inside Revit via pyRevit -> Settings -> Custom Extension Directories." -ForegroundColor Gray
    Write-Host "Add path: $ExtsDir" -ForegroundColor White
    exit 0
}

try {
    # Call pyrevit paths add link
    pyrevit paths add link $ExtsDir
    Write-Host "Successfully registered extension path with pyRevit!" -ForegroundColor Green
    Write-Host "Open Revit and click pyRevit -> Reload to load the toolbar." -ForegroundColor Gray
}
catch {
    Write-Host "Failed to register path using pyRevit CLI. Error: $_" -ForegroundColor Red
    Write-Host "Please register the path manually inside Revit." -ForegroundColor Gray
}
