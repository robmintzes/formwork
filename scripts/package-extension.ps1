# package-extension.ps1 — Compress the extension bundle into a ZIP archive for distribution.
#
# Usage:
#   .\scripts\package-extension.ps1

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Resolve-Path (Join-Path $ScriptDir "..")
$ExtsDir = Join-Path $RepoRoot "extensions"
$DistDir = Join-Path $RepoRoot "dist"

# Find any .extension folder
$ExtFolders = Get-ChildItem -Path $ExtsDir -Directory | Where-Object { $_.Name -like "*.extension" }

if (-not $ExtFolders) {
    Write-Host "ERROR: No .extension folder found inside extensions/" -ForegroundColor Red
    exit 1
}

# Create output folder
if (-not (Test-Path $DistDir)) {
    New-Item -ItemType Directory -Path $DistDir | Out-Null
}

foreach ($ExtFolder in $ExtFolders) {
    $ZipName = $ExtFolder.Name.Replace(".extension", "-extension.zip")
    $ZipPath = Join-Path $DistDir $ZipName
    
    if (Test-Path $ZipPath) {
        Remove-Item -Path $ZipPath -Force
    }
    
    Write-Host "Packaging $($ExtFolder.Name) into $ZipPath..." -ForegroundColor Gray
    Compress-Archive -Path $ExtFolder.FullName -DestinationPath $ZipPath
    Write-Host "  Successfully packaged extension!" -ForegroundColor Green
}
