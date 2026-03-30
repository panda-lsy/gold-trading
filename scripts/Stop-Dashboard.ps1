param(
    [switch]$Quiet
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

. (Join-Path $PSScriptRoot "Common.ps1")

$projectRoot = Get-ProjectRoot

$stoppedDash = Stop-FromPidFile -PidFile (Join-Path $projectRoot ".web_pid")
$stoppedWs = Stop-FromPidFile -PidFile (Join-Path $projectRoot ".ws_pid")

Stop-ByCommandPatterns -Patterns @(
    "app\\dashboard_v3.py",
    "src\\websocket_server.py"
)

if (-not $Quiet) {
    Write-Host "Dashboard stopped: $stoppedDash"
    Write-Host "WebSocket stopped: $stoppedWs"
}
