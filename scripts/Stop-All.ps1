param(
    [switch]$Quiet
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

. (Join-Path $PSScriptRoot "Common.ps1")

$projectRoot = Get-ProjectRoot

if (-not $Quiet) {
    Write-Host "Stopping all services..."
}

$stoppedApi = Stop-FromPidFile -PidFile (Join-Path $projectRoot ".api_pid")
$stoppedDash = Stop-FromPidFile -PidFile (Join-Path $projectRoot ".web_pid")
$stoppedWs = Stop-FromPidFile -PidFile (Join-Path $projectRoot ".ws_pid")
$stoppedKline = Stop-FromPidFile -PidFile (Join-Path $projectRoot ".kline_pid")
$stoppedService = Stop-FromPidFile -PidFile (Join-Path $projectRoot ".service_pid")
$stoppedPortal = Stop-FromPidFile -PidFile (Join-Path $projectRoot ".portal_pid")

Stop-ByCommandPatterns -Patterns @(
    "src\\websocket_server.py",
    "app\\kline_recorder_worker.py",
    "app\\dashboard_v3.py",
    "app\\api_server.py",
    "ops\\jijin_service.py",
    "http.server 8090"
)

if (-not $Quiet) {
    Write-Host "Stopped by PID files:"
    Write-Host "  API:       $stoppedApi"
    Write-Host "  Dashboard: $stoppedDash"
    Write-Host "  WebSocket: $stoppedWs"
    Write-Host "  Kline:     $stoppedKline"
    Write-Host "  Service:   $stoppedService"
    Write-Host "  Portal:    $stoppedPortal"
    Write-Host "Done."
}
