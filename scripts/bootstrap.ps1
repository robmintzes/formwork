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

# Clean naming variables
$FirmName = $FirmName.Replace(" ", "")
$ExtensionName = $ExtensionName.Replace(" ", "")

$ExtFolder = "${ExtensionName}.extension"
$TabFolder = "${ExtensionName}Tab.tab"
$PanelFolder = "${ExtensionName}Panel.panel"

Write-Host "`nRebranding codebase to:" -ForegroundColor Gray
Write-Host "  Firm Name:      $FirmName" -ForegroundColor White
Write-Host "  Extension Name: $ExtensionName" -ForegroundColor White
Write-Host "  Extension Dir:  extensions/$ExtFolder" -ForegroundColor White

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Resolve-Path (Join-Path $ScriptDir "..")

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
    "docs\toolbar\toolbar_spec.md",
    "extensions\Placeholder.extension\extension.json",
    "extensions\Placeholder.extension\startup.py",
    "extensions\Placeholder.extension\PlaceholderTab.tab\PlaceholderPanel.panel\HelloButton.pushbutton\script.py",
    "extensions\Placeholder.extension\PlaceholderTab.tab\PlaceholderPanel.panel\HelloButton.pushbutton\bundle.yaml"
)

foreach ($RelPath in $FilesToUpdate) {
    $Path = Join-Path $RepoRoot $RelPath
    if (Test-Path $Path) {
        $Text = Get-Content -Path $Path -Raw
        
        # Substitutions
        $Text = $Text.Replace("Placeholder", $ExtensionName)
        $Text = $Text.Replace("placeholder-tools", $ExtensionName.ToLower())
        $Text = $Text.Replace("Placeholder Tools", "$ExtensionName Tools")
        $Text = $Text.Replace("PlaceholderPanel", "${ExtensionName}Panel")
        $Text = $Text.Replace("PlaceholderTab", "${ExtensionName}Tab")
        $Text = $Text.Replace("Template Author", "$FirmName Design Technology")
        
        Set-Content -Path $Path -Value $Text -NoNewline
        Write-Host "  Updated: $RelPath" -ForegroundColor Green
    }
}

# 4. Rename directories
Write-Host "`nRenaming folders on disk..." -ForegroundColor Gray

# Rename Tab
$OldTabPath = Join-Path $PlaceholderExtPath "PlaceholderTab.tab"
$NewTabPath = Join-Path $PlaceholderExtPath $TabFolder
Rename-Item -Path $OldTabPath -NewName $TabFolder
Write-Host "  Renamed Tab folder." -ForegroundColor Green

# Rename Panel
$OldPanelPath = Join-Path $NewTabPath "PlaceholderPanel.panel"
$NewPanelPath = Join-Path $NewTabPath $PanelFolder
Rename-Item -Path $OldPanelPath -NewName $PanelFolder
Write-Host "  Renamed Panel folder." -ForegroundColor Green

# Rename Extension
$NewExtPath = Join-Path $RepoRoot "extensions\$ExtFolder"
Rename-Item -Path $PlaceholderExtPath -NewName $ExtFolder
Write-Host "  Renamed Extension root folder." -ForegroundColor Green

# 5. Output next steps
Write-Host "`n==========================================" -ForegroundColor Cyan
Write-Host "Bootstrap completed successfully!" -ForegroundColor Green
Write-Host "To link your custom extension to pyRevit, run:" -ForegroundColor Gray
Write-Host "  .\scripts\install-extension.ps1" -ForegroundColor Yellow
Write-Host "==========================================" -ForegroundColor Cyan
