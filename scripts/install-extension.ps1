# install-extension.ps1 — Register this repository's extension root with pyRevit.
#
# Usage:
#   .\scripts\install-extension.ps1

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function ConvertTo-ComparablePath {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    try {
        $ExpandedPath = [Environment]::ExpandEnvironmentVariables($Path.Trim())
        return [System.IO.Path]::GetFullPath($ExpandedPath).TrimEnd([char[]]"\/")
    }
    catch {
        return $null
    }
}

function Test-ExtensionPathListed {
    param(
        [Parameter(Mandatory = $true)]
        [object[]]$CommandOutput,

        [Parameter(Mandatory = $true)]
        [string]$ExpectedPath
    )

    $ComparableExpectedPath = ConvertTo-ComparablePath -Path $ExpectedPath
    foreach ($Line in @($CommandOutput)) {
        $LineText = ([string]$Line).Trim()
        if (-not $LineText -or $LineText.StartsWith("==>")) {
            continue
        }

        $ComparableListedPath = ConvertTo-ComparablePath -Path $LineText
        if (
            $null -ne $ComparableListedPath -and
            [string]::Equals(
                $ComparableListedPath,
                $ComparableExpectedPath,
                [System.StringComparison]::OrdinalIgnoreCase
            )
        ) {
            return $true
        }
    }

    return $false
}

function Write-PyRevitFailure {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Message,

        [object[]]$CommandOutput = @()
    )

    foreach ($Line in @($CommandOutput)) {
        Write-Host ([string]$Line) -ForegroundColor DarkGray
    }
    Write-Error $Message -ErrorAction Continue
}

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = (Resolve-Path -LiteralPath (Join-Path $ScriptDir "..")).Path
$ExtensionsCandidate = Join-Path $RepoRoot "extensions"

if (-not (Test-Path -LiteralPath $ExtensionsCandidate -PathType Container)) {
    Write-Error "Extension root does not exist: $ExtensionsCandidate" -ErrorAction Continue
    exit 1
}

$ExtsDir = (Resolve-Path -LiteralPath $ExtensionsCandidate).Path
$PyRevitCommand = Get-Command "pyrevit" -CommandType Application -ErrorAction SilentlyContinue |
    Select-Object -First 1

if ($null -eq $PyRevitCommand) {
    Write-Error "The 'pyrevit' CLI was not found on PATH. Install or repair pyRevit before registering $ExtsDir." -ErrorAction Continue
    exit 1
}

$PyRevitExecutable = $PyRevitCommand.Path
Write-Host "Checking registered pyRevit extension paths..." -ForegroundColor Gray

$RegisteredPathsOutput = @(& $PyRevitExecutable extensions paths 2>&1)
$ListExitCode = $LASTEXITCODE
if ($ListExitCode -ne 0) {
    Write-PyRevitFailure `
        -Message "pyRevit could not list registered extension paths (exit $ListExitCode)." `
        -CommandOutput $RegisteredPathsOutput
    exit $ListExitCode
}

if (
    Test-ExtensionPathListed `
        -CommandOutput $RegisteredPathsOutput `
        -ExpectedPath $ExtsDir
) {
    Write-Host "Extension path is already registered: $ExtsDir" -ForegroundColor Green
    exit 0
}

Write-Host "Registering pyRevit extension path: $ExtsDir" -ForegroundColor Gray
$AddPathOutput = @(& $PyRevitExecutable extensions paths add $ExtsDir 2>&1)
$AddExitCode = $LASTEXITCODE
if ($AddExitCode -ne 0) {
    Write-PyRevitFailure `
        -Message "pyRevit could not register the extension path (exit $AddExitCode)." `
        -CommandOutput $AddPathOutput
    exit $AddExitCode
}

# Do not report success solely because the mutating command returned zero. Verify
# the persisted registration using the same read command used by the preflight.
$VerifiedPathsOutput = @(& $PyRevitExecutable extensions paths 2>&1)
$VerifyExitCode = $LASTEXITCODE
if ($VerifyExitCode -ne 0) {
    Write-PyRevitFailure `
        -Message "pyRevit added the path but verification failed (exit $VerifyExitCode)." `
        -CommandOutput $VerifiedPathsOutput
    exit $VerifyExitCode
}

if (-not (
    Test-ExtensionPathListed `
        -CommandOutput $VerifiedPathsOutput `
        -ExpectedPath $ExtsDir
)) {
    Write-Error "pyRevit returned success but did not list the registered extension path: $ExtsDir" -ErrorAction Continue
    exit 1
}

Write-Host "Successfully registered the extension path with pyRevit." -ForegroundColor Green
Write-Host "Open Revit and click pyRevit -> Reload to load the toolbar." -ForegroundColor Gray
