# Install the repository's branch guards in this clone only.
param([string]$Owner = "robmintzes")
$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
if ($Owner -cnotmatch '^[a-z0-9]+(-[a-z0-9]+)*$' -or
    $Owner -in @("ai", "agent", "antigravity", "chatgpt", "claude", "codex", "copilot", "gemini")) {
    throw "Owner must be a lowercase human developer prefix."
}
Push-Location $RepoRoot
try {
    $ExistingHooks = git config --get core.hooksPath
    if ($ExistingHooks -and $ExistingHooks -ne ".githooks") {
        throw "Existing core.hooksPath '$ExistingHooks' must be integrated manually; it was not overwritten."
    }
    git config --local branchPolicy.owner $Owner
    if ($LASTEXITCODE -ne 0) { throw "Could not configure the branch owner." }
    git config --local core.hooksPath .githooks
    if ($LASTEXITCODE -ne 0) { throw "Could not configure Git hooks." }
    Write-Host "Branch guards installed for $Owner in this clone."
}
finally { Pop-Location }
