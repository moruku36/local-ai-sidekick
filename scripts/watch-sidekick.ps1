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

$cmdArgs = @("-u", "-m", "sidekick.cli", "--repo-root", $RepoRoot, "--watch")
if ($Model) {
    $cmdArgs += @("--model", $Model)
}
if ($EnvFile) {
    $cmdArgs += @("--env-file", $EnvFile)
}

Write-Host "==========================================" -ForegroundColor Green
Write-Host "Local AI Sidekick (Phase 2 Task Watcher)" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Green

& python $cmdArgs
$exitCode = $LASTEXITCODE
exit $exitCode
