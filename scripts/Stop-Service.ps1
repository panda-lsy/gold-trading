param(
    [switch]$Quiet
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

. (Join-Path $PSScriptRoot "Common.ps1")

$projectRoot = Get-ProjectRoot
$stopped = Stop-FromPidFile -PidFile (Join-Path $projectRoot ".service_pid")

Stop-ByCommandPatterns -Patterns @("ops\\jijin_service.py")

if (-not $Quiet) {
    Write-Host "Service stopped: $stopped"
}
