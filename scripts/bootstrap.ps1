# bootstrap.ps1 — Rebrand this template repository for your firm.
#
# Usage:
#   .\scripts\bootstrap.ps1
#   .\scripts\bootstrap.ps1 -FirmName "AcmeCorp" -ExtensionName "BimTools"

param(
    [string]$FirmName,
    [string]$ExtensionName
)

$ErrorActionPreference = "Stop"

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "      pyRevit Extension Bootstrapper      " -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

# 1. Resolve inputs
if (-not $FirmName) {
    $FirmName = Read-Host "Enter your Firm Name (e.g., AcmeCorp)"
    if (-not $FirmName) { $FirmName = "MyFirm" }
}

if (-not $ExtensionName) {
    $ExtensionName = Read-Host "Enter your Extension Name (e.g., BimTools)"
    if (-not $ExtensionName) { $ExtensionName = "BimTools" }
}

# Preserve human-facing firm spacing; extension names are safe identifiers.
$FirmName = [regex]::Replace($FirmName.Trim(), "\s+", " ")
$ExtensionName = [regex]::Replace($ExtensionName, "\s+", "")

if ($FirmName -notmatch "^[\p{L}\p{N}][\p{L}\p{N} .,&'()_-]{0,79}$") {
    Write-Host "ERROR: Firm name contains unsupported characters." -ForegroundColor Red
    exit 2
}

$ReservedNames = @("CON", "PRN", "AUX", "NUL", "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9", "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9")
if (
    $ExtensionName.Length -gt 64 -or
    $ExtensionName -notmatch "^[A-Za-z][A-Za-z0-9]*(?:-[A-Za-z0-9]+)*$" -or
    $ReservedNames -contains $ExtensionName.ToUpperInvariant() -or
    $ExtensionName.ToLowerInvariant() -eq "placeholder"
) {
    Write-Host "ERROR: Extension name must begin with a letter and contain alphanumeric segments separated by single hyphens." -ForegroundColor Red
    exit 2
}

$ExtFolder = "${ExtensionName}.extension"
$TabFolder = "${ExtensionName}Tab.tab"
$PanelFolder = "${ExtensionName}Panel.panel"

Write-Host "`nRebranding codebase to:" -ForegroundColor Gray
Write-Host "  Firm Name:      $FirmName" -ForegroundColor White
Write-Host "  Extension Name: $ExtensionName" -ForegroundColor White
Write-Host "  Extension Dir:  extensions/$ExtFolder" -ForegroundColor White

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Resolve-Path (Join-Path $ScriptDir "..")
$Utf8NoBom = New-Object System.Text.UTF8Encoding($false)

# 2. Check if placeholders exist
$PlaceholderExtPath = Join-Path $RepoRoot "extensions\Placeholder.extension"
if (-not (Test-Path $PlaceholderExtPath)) {
    Write-Host "`nERROR: Placeholder extension folder not found. Has bootstrap already been run?" -ForegroundColor Red
    exit 1
}

# 3. Replace content references
Write-Host "`nUpdating text references across repository files..." -ForegroundColor Gray

# File List to replace strings in
$FilesToUpdate = @(
    "README.md",
    "AGENTS.md",
    ".github\workflows\ci.yml",
    "docs\toolbar\toolbar_spec.md",
    "docs\toolbar\tools\hello-button.md",
    "docs\onboarding\MCP_GUIDE.md",
    "docs\handoffs\mcp-bridge-onboarding-2026-06-19.md",
    "extensions\Placeholder.extension\extension.json",
    "extensions\Placeholder.extension\startup.py",
    "extensions\Placeholder.extension\PlaceholderTab.tab\PlaceholderPanel.panel\HelloButton.pushbutton\script.py",
    "extensions\Placeholder.extension\PlaceholderTab.tab\PlaceholderPanel.panel\HelloButton.pushbutton\bundle.yaml",
    "extensions\Placeholder.extension\lib\revit_mcp_bridge\__init__.py",
    "extensions\Placeholder.extension\lib\revit_mcp_bridge\compat.py",
    "extensions\Placeholder.extension\lib\revit_mcp_bridge\dispatch.py",
    "extensions\Placeholder.extension\lib\revit_mcp_bridge\handlers_health.py",
    "extensions\Placeholder.extension\lib\revit_mcp_bridge\handlers_project.py",
    "extensions\Placeholder.extension\lib\revit_mcp_bridge\handlers_registry.py",
    "extensions\Placeholder.extension\lib\revit_mcp_bridge\identity.py",
    "extensions\Placeholder.extension\lib\revit_mcp_bridge\response.py",
    "extensions\Placeholder.extension\lib\revit_mcp_bridge\routes_health.py",
    "extensions\Placeholder.extension\lib\revit_mcp_bridge\routes_project.py",
    "extensions\Placeholder.extension\lib\revit_mcp_bridge\routes_dispatch.py",
    "extensions\Placeholder.extension\lib\revit_mcp_bridge\startup.py",
    "extensions\Placeholder.extension\tests\test_runtime_stabilization.py",
    "servers\revit-mcp\mcp-server\settings.py"
)

$MissingPaths = @(
    $FilesToUpdate | Where-Object {
        -not (Test-Path (Join-Path $RepoRoot $_) -PathType Leaf)
    }
)
$OldTabPath = Join-Path $PlaceholderExtPath "PlaceholderTab.tab"
$OldPanelPath = Join-Path $OldTabPath "PlaceholderPanel.panel"
$NewTabPath = Join-Path $PlaceholderExtPath $TabFolder
$NewPanelPath = Join-Path $OldTabPath $PanelFolder
$NewExtPath = Join-Path $RepoRoot "extensions\$ExtFolder"

foreach ($RequiredDirectory in @($OldTabPath, $OldPanelPath)) {
    if (-not (Test-Path $RequiredDirectory -PathType Container)) {
        $MissingPaths += $RequiredDirectory
    }
}
if ($MissingPaths.Count -gt 0) {
    Write-Host "ERROR: Bootstrap source paths are missing:" -ForegroundColor Red
    $MissingPaths | ForEach-Object { Write-Host "  - $_" -ForegroundColor Red }
    exit 1
}
foreach ($Destination in @($NewPanelPath, $NewTabPath, $NewExtPath)) {
    if (Test-Path $Destination) {
        Write-Host "ERROR: Bootstrap destination already exists: $Destination" -ForegroundColor Red
        exit 1
    }
}

foreach ($RelPath in $FilesToUpdate) {
    $Path = Join-Path $RepoRoot $RelPath
    if (Test-Path $Path) {
        $Text = [System.IO.File]::ReadAllText($Path, [System.Text.Encoding]::UTF8)
        
        # Substitutions
        $Text = $Text.Replace("Placeholder Tools", $ExtensionName)
        $Text = $Text.Replace("placeholder-tools", $ExtensionName.ToLowerInvariant())
        $Text = $Text.Replace("PlaceholderPanel", "${ExtensionName}Panel")
        $Text = $Text.Replace("PlaceholderTab", "${ExtensionName}Tab")
        $Text = $Text.Replace("Template Author", $FirmName)
        $Text = $Text.Replace("PLACEHOLDER", $ExtensionName.ToUpperInvariant())
        $Text = $Text.Replace("Placeholder", $ExtensionName)
        $Text = $Text.Replace("placeholder", $ExtensionName.ToLowerInvariant())
        
        [System.IO.File]::WriteAllText($Path, $Text, $Utf8NoBom)
        Write-Host "  Updated: $RelPath" -ForegroundColor Green
    }
}

# 4. Rename directories
Write-Host "`nRenaming folders on disk..." -ForegroundColor Gray

# Rename Tab
Rename-Item -Path $OldTabPath -NewName $TabFolder
Write-Host "  Renamed Tab folder." -ForegroundColor Green

# Rename Panel
$RenamedPanelPath = Join-Path $NewTabPath "PlaceholderPanel.panel"
Rename-Item -Path $RenamedPanelPath -NewName $PanelFolder
Write-Host "  Renamed Panel folder." -ForegroundColor Green

# Rename Extension
Rename-Item -Path $PlaceholderExtPath -NewName $ExtFolder
Write-Host "  Renamed Extension root folder." -ForegroundColor Green

# 5. Output next steps
Write-Host "`n==========================================" -ForegroundColor Cyan
Write-Host "Bootstrap completed successfully!" -ForegroundColor Green
Write-Host "To link your custom extension to pyRevit, run:" -ForegroundColor Gray
Write-Host "  .\scripts\install-extension.ps1" -ForegroundColor Yellow
Write-Host "==========================================" -ForegroundColor Cyan
