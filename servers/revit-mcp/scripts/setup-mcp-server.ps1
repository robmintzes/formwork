# setup-mcp-server.ps1
# Setup Python virtual environment and install dependencies.

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

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ServerDir = (Resolve-Path -LiteralPath (Join-Path $ScriptDir "..\mcp-server")).Path
$VenvDir = Join-Path $ServerDir ".venv"

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "         Revit MCP Server Setup           " -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

# Select the first tested Python 3.10+ invocation. A broken or outdated
# `python` shim is ignored so the Windows `py -3` launcher can be tried.
try {
    $Python = Get-PythonInvocation
    Write-Host ("Found Python: " + $Python.Version) -ForegroundColor Gray
} catch {
    Write-Host "ERROR: Python 3.10 or newer was not found on PATH." -ForegroundColor Red
    exit 1
}

# Create venv if not exists
if (-not (Test-Path -LiteralPath $VenvDir)) {
    Write-Host "Creating virtual environment at $VenvDir..." -ForegroundColor Gray
    $VenvArguments = @($Python.Prefix) + @("-m", "venv", $VenvDir)
    try {
        & $Python.Executable @VenvArguments
        $VenvExitCode = $LASTEXITCODE
    }
    catch {
        Write-Host "ERROR: Python could not start virtual-environment creation." -ForegroundColor Red
        exit 1
    }
    if ($VenvExitCode -ne 0) {
        Write-Host "ERROR: Python failed to create the virtual environment." -ForegroundColor Red
        exit 1
    }
    Write-Host "Virtual environment created." -ForegroundColor Green
} else {
    Write-Host "Virtual environment already exists." -ForegroundColor Gray
}

# Determine python executable path
$PythonExe = Join-Path $VenvDir "Scripts\python.exe"
if (-not (Test-Path -LiteralPath $PythonExe)) {
    # Try non-Windows structure (mac/linux)
    $PythonExe = Join-Path $VenvDir "bin/python"
}

if (-not (Test-Path -LiteralPath $PythonExe)) {
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
if (Test-Path -LiteralPath $RequirementsFile -PathType Leaf) {
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
Write-Host "  .\servers\revit-mcp\scripts\start-stdio.ps1" -ForegroundColor Yellow
Write-Host "==========================================" -ForegroundColor Cyan
