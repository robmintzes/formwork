<#
.SYNOPSIS
  Prepare, record, and clean up the live Revit check for a generated workspace.
.DESCRIPTION
  Prepare   Create (or re-render) a workspace from a profile, validate it, and
            copy the manual checklist to .logs\workspace-verification\. With
            -RegisterExtension it also adds the workspace's extensions folder
            to pyRevit's search paths (a pyRevit configuration change).
  Record    Run 'formwork verify workspace' with the filled checklist and write
            redacted JSON/Markdown evidence.
  Unregister  Remove the workspace's extensions folder from pyRevit's search
            paths. Never deletes files.
  Exit codes: 0 pass, 1 fail, 2 incomplete or cannot run.
.EXAMPLE
  .\scripts\verify-generated-workspace.ps1 -Mode Prepare -Workspace 'D:\Live Check\BIMxBert' -RegisterExtension
.EXAMPLE
  .\scripts\verify-generated-workspace.ps1 -Mode Record -Workspace 'D:\Live Check\BIMxBert' -RevitVersion 2026
.EXAMPLE
  .\scripts\verify-generated-workspace.ps1 -Mode Unregister -Workspace 'D:\Live Check\BIMxBert'
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('Prepare', 'Record', 'Unregister')]
    [string]$Mode,

    [Parameter(Mandatory = $true)]
    [string]$Workspace,

    [string]$ProfilePath,
    [string]$RevitVersion,
    [string]$ManualChecks,
    [switch]$RegisterExtension
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$RepoRoot = (Resolve-Path -LiteralPath (Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) '..')).Path
$LogRoot = Join-Path $RepoRoot '.logs\workspace-verification'
$Template = Join-Path $RepoRoot 'docs\verification\workspace-manual-checks.template.json'
if (-not $ProfilePath) { $ProfilePath = Join-Path $RepoRoot 'profiles\bimxbert' }
if (-not $ManualChecks) { $ManualChecks = Join-Path $LogRoot 'manual-checks.json' }
$WorkspaceFull = [System.IO.Path]::GetFullPath($Workspace)
$ExtensionsDir = Join-Path $WorkspaceFull 'extensions'

function Get-PythonCommand {
    foreach ($candidate in @(@('py', '-3'), @('python'))) {
        $command = Get-Command $candidate[0] -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($null -ne $command) {
            $prefix = @($candidate | Select-Object -Skip 1)
            & $command.Path @prefix -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)' | Out-Null
            if ($LASTEXITCODE -eq 0) { return , (@($command.Path) + $prefix) }
        }
    }
    return $null
}

function Invoke-Formwork([string[]]$Arguments) {
    $exe = $script:Python[0]
    $prefix = @($script:Python | Select-Object -Skip 1)
    Push-Location -LiteralPath $RepoRoot
    try {
        # Send output to the host so the function returns only the exit code.
        & $exe @prefix -m formwork_cli @Arguments | Out-Host
        return $LASTEXITCODE
    }
    finally {
        Pop-Location
    }
}

function Get-PyRevit {
    $command = Get-Command 'pyrevit' -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($null -eq $command) { return $null }
    return $command.Path
}

function Test-PathRegistered([string]$PyRevit, [string]$Expected) {
    $listed = @(& $PyRevit extensions paths 2>&1)
    if ($LASTEXITCODE -ne 0) { throw "pyRevit could not list extension paths (exit $LASTEXITCODE)." }
    $wanted = [System.IO.Path]::GetFullPath($Expected).TrimEnd([char[]]'\/')
    foreach ($line in $listed) {
        $text = ([string]$line).Trim()
        if (-not $text -or $text.StartsWith('==>')) { continue }
        try { $candidate = [System.IO.Path]::GetFullPath($text).TrimEnd([char[]]'\/') } catch { continue }
        if ([string]::Equals($candidate, $wanted, [System.StringComparison]::OrdinalIgnoreCase)) { return $true }
    }
    return $false
}

$Python = Get-PythonCommand
if ($null -eq $Python) {
    Write-Host 'CPython 3.10 or newer was not found (tried py -3 and python).' -ForegroundColor Red
    exit 2
}

if ($Mode -eq 'Prepare') {
    $marker = Join-Path $WorkspaceFull '.formwork\workspace.json'
    if (-not (Test-Path -LiteralPath $marker -PathType Leaf)) {
        Write-Host "Initializing workspace from profile: $ProfilePath" -ForegroundColor Gray
        $code = Invoke-Formwork @('init', '--profile', $ProfilePath, '--workspace', $WorkspaceFull)
        if ($code -ne 0) { exit $code }
    }
    Write-Host 'Rendering workspace...' -ForegroundColor Gray
    $code = Invoke-Formwork @('render', '--workspace', $WorkspaceFull)
    if ($code -ne 0) { exit $code }

    if ($RegisterExtension) {
        $pyrevit = Get-PyRevit
        if ($null -eq $pyrevit) { Write-Host 'The pyrevit CLI is not on PATH.' -ForegroundColor Red; exit 2 }
        if (Test-PathRegistered $pyrevit $ExtensionsDir) {
            Write-Host "Already registered with pyRevit: $ExtensionsDir" -ForegroundColor Green
        }
        else {
            $added = @(& $pyrevit extensions paths add $ExtensionsDir 2>&1)
            if ($LASTEXITCODE -ne 0) { $added | ForEach-Object { Write-Host $_ }; exit 1 }
            if (-not (Test-PathRegistered $pyrevit $ExtensionsDir)) {
                Write-Host 'pyRevit reported success but does not list the path.' -ForegroundColor Red
                exit 1
            }
            Write-Host "Registered with pyRevit: $ExtensionsDir" -ForegroundColor Green
        }
    }
    else {
        Write-Host 'pyRevit registration skipped. Re-run with -RegisterExtension to add the workspace extensions folder.' -ForegroundColor Yellow
    }

    New-Item -ItemType Directory -Force -Path $LogRoot | Out-Null
    if (Test-Path -LiteralPath $ManualChecks -PathType Leaf) {
        Write-Host "Keeping existing checklist: $ManualChecks" -ForegroundColor Gray
    }
    else {
        Copy-Item -LiteralPath $Template -Destination $ManualChecks
        Write-Host "Checklist copied to: $ManualChecks" -ForegroundColor Green
    }
    Write-Host ''
    Write-Host 'Next: start Revit, click pyRevit > Reload, work through the checklist steps,' -ForegroundColor Gray
    Write-Host 'set each status in the checklist file, then run this script with -Mode Record.' -ForegroundColor Gray
    exit 0
}

if ($Mode -eq 'Record') {
    $arguments = @('verify', 'workspace', '--workspace', $WorkspaceFull, '--manual-checks', $ManualChecks)
    if ($RevitVersion) { $arguments += @('--revit-version', $RevitVersion) }
    exit (Invoke-Formwork $arguments)
}

# Unregister
$pyrevit = Get-PyRevit
if ($null -eq $pyrevit) { Write-Host 'The pyrevit CLI is not on PATH.' -ForegroundColor Red; exit 2 }
if (-not (Test-PathRegistered $pyrevit $ExtensionsDir)) {
    Write-Host "Not registered with pyRevit: $ExtensionsDir" -ForegroundColor Gray
    exit 0
}
$forgot = @(& $pyrevit extensions paths forget $ExtensionsDir 2>&1)
if ($LASTEXITCODE -ne 0) { $forgot | ForEach-Object { Write-Host $_ }; exit 1 }
Write-Host "Removed from pyRevit search paths: $ExtensionsDir (files were not touched)" -ForegroundColor Green
exit 0
