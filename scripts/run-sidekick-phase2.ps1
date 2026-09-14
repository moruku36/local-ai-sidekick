[CmdletBinding()]
param(
    [string]$RepoRoot = ".",
    [string]$Model = "",
    [string]$EnvFile = ""
)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$ProjectRoot = Split-Path -Parent $ScriptDir

$pythonPath = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $pythonPath) {
    Write-Error "Python is not found in PATH."
    exit 1
}

$env:PYTHONPATH = "$ProjectRoot\src;$env:PYTHONPATH"

$cmdArgs = @("-u", "-m", "sidekick.cli", "--repo-root", $RepoRoot, "--auto-git")
if ($Model) {
    $cmdArgs += @("--model", $Model)
}
if ($EnvFile) {
    $cmdArgs += @("--env-file", $EnvFile)
}

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Local AI Sidekick (Phase 2 Auto-Git Runner)" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

& python $cmdArgs
$exitCode = $LASTEXITCODE

Write-Host "`nPhase 2 Runner finished with exit code $exitCode" -ForegroundColor Yellow
exit $exitCode
