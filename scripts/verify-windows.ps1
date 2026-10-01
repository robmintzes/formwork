# verify-windows.ps1 - Produce preflight and live Revit verification evidence.
#
# This wrapper never changes a model or pyRevit configuration. Extension
# registration occurs only when -InstallExtension is explicitly supplied.

[CmdletBinding()]
param(
    [ValidateSet("Preflight", "Live", "All")]
    [string]$Mode = "Preflight",

    [ValidateSet("any", "none", "family", "project")]
    [string]$ExpectedContext = "project",

    [string]$RoutesBaseUrl = "http://127.0.0.1:48884/placeholder",

    [string]$McpUrl = "http://127.0.0.1:3001/mcp",

    [string]$ManualChecks,

    [string]$OutputRoot = ".logs\windows-verification",

    [switch]$RoutesResetConfirmed,

    [switch]$InstallExtension
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Get-PythonInvocation {
    $Candidates = @(
        [pscustomobject]@{ Command = "python"; Prefix = @() },
        [pscustomobject]@{ Command = "py"; Prefix = @("-3") }
    )

    foreach ($Candidate in $Candidates) {
        $PythonCommand = Get-Command $Candidate.Command `
            -CommandType Application `
            -ErrorAction SilentlyContinue |
            Select-Object -First 1
        if ($null -eq $PythonCommand) {
            continue
        }

        $ProbeArguments = @($Candidate.Prefix) + @(
            "-c",
            "import sys; print('{0}.{1}.{2}'.format(*sys.version_info[:3])); raise SystemExit(0 if sys.version_info >= (3, 10) else 1)"
        )
        try {
            $ProbeOutput = @(& $PythonCommand.Path @ProbeArguments 2>&1)
            $ProbeExitCode = $LASTEXITCODE
        }
        catch {
            continue
        }
        if ($ProbeExitCode -ne 0) {
            continue
        }

        $Version = (($ProbeOutput | ForEach-Object { [string]$_ }) -join " ").Trim()
        return [pscustomobject]@{
            Executable = $PythonCommand.Path
            Prefix = @($Candidate.Prefix)
            Version = $Version
        }
    }

    throw "Python 3.10 or newer was not found on PATH."
}

function Invoke-ToolkitPython {
    param(
        [Parameter(Mandatory = $true)]
        [object]$PythonInvocation,

        [Parameter(Mandatory = $true)]
        [string[]]$Arguments
    )

    $NativeArguments = @($PythonInvocation.Prefix) + @($Arguments)
    $CommandOutput = @(& $PythonInvocation.Executable @NativeArguments 2>&1)
    $NativeExitCode = $LASTEXITCODE
    foreach ($Line in $CommandOutput) {
        Write-Host ([string]$Line)
    }
    if ($NativeExitCode -notin @(0, 1, 2)) {
        throw "Toolkit Python command failed unexpectedly with exit $NativeExitCode."
    }
    return $NativeExitCode
}

function Merge-ExitCode {
    param(
        [int]$Current,
        [int]$Next
    )

    if ($Current -eq 1 -or $Next -eq 1) { return 1 }
    if ($Current -eq 2 -or $Next -eq 2) { return 2 }
    return 0
}

function Get-SanitizedManualChecklist {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    $ResolvedPath = (Resolve-Path -LiteralPath $Path).Path
    $ManualFile = Get-Item -LiteralPath $ResolvedPath
    if ($ManualFile.Length -gt (256 * 1024)) {
        throw "Manual checklist is larger than 256 KiB."
    }

    $StrictUtf8 = New-Object System.Text.UTF8Encoding($false, $true)
    $RawManual = [System.IO.File]::ReadAllText($ResolvedPath, $StrictUtf8)
    if ([string]::IsNullOrWhiteSpace($RawManual)) {
        throw "Manual checklist is empty."
    }

    try {
        $DecodedManual = $RawManual | ConvertFrom-Json
    }
    catch {
        throw "Manual checklist is not valid UTF-8 JSON."
    }

    $FirstCharacter = $RawManual.TrimStart().Substring(0, 1)
    if ($FirstCharacter -ceq "[") {
        $Items = @($DecodedManual)
    }
    elseif ($FirstCharacter -ceq "{") {
        if ($null -eq $DecodedManual) {
            throw "Manual checklist root must be an object or array."
        }
        $ChecksProperty = $DecodedManual.PSObject.Properties["checks"]
        if ($null -eq $ChecksProperty -or $ChecksProperty.Value -isnot [System.Array]) {
            throw "Manual checklist object must contain a checks array."
        }
        $Items = @($ChecksProperty.Value)
    }
    else {
        throw "Manual checklist root must be an object or array."
    }

    $AllowedStatuses = @("pass", "fail", "warn", "skip", "pending", "not_run")
    $SeenIds = New-Object 'System.Collections.Generic.HashSet[string]'
    $SanitizedChecks = @()
    foreach ($Item in $Items) {
        if ($null -eq $Item) {
            throw "Every manual check must be an object."
        }

        $IdProperty = $Item.PSObject.Properties["id"]
        $StatusProperty = $Item.PSObject.Properties["status"]
        if ($null -eq $IdProperty -or $null -eq $StatusProperty) {
            throw "Every manual check requires id and status fields."
        }

        $ManualId = $IdProperty.Value
        $ManualStatus = $StatusProperty.Value
        if (
            $ManualId -isnot [string] -or
            $ManualId -cnotmatch '^[a-z0-9][a-z0-9_.-]{0,63}$' -or
            -not $SeenIds.Add($ManualId)
        ) {
            throw "Manual check ids must be unique safe identifiers."
        }
        if ($ManualStatus -isnot [string] -or $AllowedStatuses -cnotcontains $ManualStatus) {
            throw "Manual check status is invalid."
        }

        $RequiredProperty = $Item.PSObject.Properties["required"]
        if ($null -eq $RequiredProperty) {
            $Required = $true
        }
        else {
            $Required = $RequiredProperty.Value
            if ($Required -isnot [bool]) {
                throw "Manual check required fields must be boolean."
            }
        }

        if ($ManualId -ceq "routes-reset-after-reload") {
            $ManualStatus = "pass"
        }
        $SanitizedChecks += [pscustomobject][ordered]@{
            id = $ManualId
            status = $ManualStatus
            required = $Required
        }
    }

    return [pscustomobject][ordered]@{
        checks = @($SanitizedChecks)
    }
}

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = (Resolve-Path -LiteralPath (Join-Path $ScriptDir "..")).Path
$EffectiveManualData = $null
if ($Mode -in @("Live", "All")) {
    if ($ManualChecks) {
        $ManualSource = $ManualChecks
    }
    else {
        $ManualSource = Join-Path $RepoRoot "docs\verification\manual-checks.template.json"
    }
    try {
        # Validate and sanitize before doctor or live verification can contact
        # either the Routes endpoint or the MCP server.
        $EffectiveManualData = Get-SanitizedManualChecklist -Path $ManualSource
    }
    catch {
        Write-Host `
            ("Manual checklist validation failed: " + $_.Exception.Message) `
            -ForegroundColor Red
        exit 2
    }
}
$Python = Get-PythonInvocation

$Timestamp = [DateTime]::UtcNow.ToString("yyyyMMdd-HHmmss")
if ([System.IO.Path]::IsPathRooted($OutputRoot)) {
    $ResolvedOutputRoot = $OutputRoot
}
else {
    $ResolvedOutputRoot = Join-Path $RepoRoot $OutputRoot
}
$EvidenceDir = Join-Path $ResolvedOutputRoot $Timestamp
[System.IO.Directory]::CreateDirectory($EvidenceDir) | Out-Null

$OverallExitCode = 0
Push-Location $RepoRoot
try {
    Write-Host ("Found Python: " + $Python.Version) -ForegroundColor Gray

    if ($InstallExtension) {
        $WindowsPowerShell = (Get-Command "powershell.exe" -CommandType Application).Path
        & $WindowsPowerShell `
            -NoProfile `
            -ExecutionPolicy Bypass `
            -File (Join-Path $ScriptDir "install-extension.ps1")
        $InstallExitCode = $LASTEXITCODE
        if ($InstallExitCode -ne 0) {
            throw "Extension registration failed with exit $InstallExitCode."
        }
    }

    if ($Mode -in @("Preflight", "All")) {
        $DoctorPath = Join-Path $EvidenceDir "doctor.json"
        $DoctorArguments = @(
            "-m", "toolkit_cli", "doctor",
            "--profile", "revit-host",
            "--routes-url", $RoutesBaseUrl,
            "--mcp-url", $McpUrl,
            "--format", "text",
            "--output", $DoctorPath
        )
        $DoctorExitCode = Invoke-ToolkitPython `
            -PythonInvocation $Python `
            -Arguments $DoctorArguments
        $OverallExitCode = Merge-ExitCode $OverallExitCode $DoctorExitCode
    }

    if ($Mode -in @("Live", "All")) {
        # Calling Routes immediately after pyRevit Reload can destabilize Revit.
        # Refuse before any verifier process starts unless the human confirms a
        # full Revit restart or an explicit Routes off/on reset occurred.
        if (-not $RoutesResetConfirmed) {
            Write-Warning "Live verification refused. Restart Revit or toggle Routes off/on after pyRevit Reload, then pass -RoutesResetConfirmed."
            exit 2
        }

        $McpPython = Join-Path $RepoRoot "servers\revit-mcp\mcp-server\.venv\Scripts\python.exe"
        if (-not (Test-Path -LiteralPath $McpPython -PathType Leaf)) {
            Write-Warning "MCP virtual environment is missing. Run servers\revit-mcp\scripts\setup-mcp-server.ps1 first."
            exit 2
        }

        $EffectiveManualPath = Join-Path $EvidenceDir "manual-checks.json"
        $Utf8NoBom = New-Object System.Text.UTF8Encoding($false)
        [System.IO.File]::WriteAllText(
            $EffectiveManualPath,
            ($EffectiveManualData | ConvertTo-Json -Depth 4),
            $Utf8NoBom
        )

        $LiveOutputDir = Join-Path $EvidenceDir "revit-live"
        $VerifyArguments = @(
            "-m", "toolkit_cli", "verify", "revit",
            "--routes-url", $RoutesBaseUrl,
            "--mcp-python", $McpPython,
            "--expected-context", $ExpectedContext,
            "--manual-checks", $EffectiveManualPath,
            "--output-dir", $LiveOutputDir,
            "--routes-reset-confirmed"
        )
        $VerifyExitCode = Invoke-ToolkitPython `
            -PythonInvocation $Python `
            -Arguments $VerifyArguments
        $OverallExitCode = Merge-ExitCode $OverallExitCode $VerifyExitCode
    }
}
finally {
    Pop-Location
}

Write-Host "Verification evidence: $EvidenceDir" -ForegroundColor Cyan
if ($OverallExitCode -eq 0) {
    Write-Host "All required checks passed." -ForegroundColor Green
}
elseif ($OverallExitCode -eq 2) {
    Write-Host "Verification is incomplete; inspect pending or skipped required checks." -ForegroundColor Yellow
}
else {
    Write-Host "One or more verification checks failed." -ForegroundColor Red
}
exit $OverallExitCode
