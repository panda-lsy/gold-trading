param(
    [switch]$SkipInstall
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

. (Join-Path $PSScriptRoot "Common.ps1")

$projectRoot = Get-ProjectRoot
$logDir = Join-Path $projectRoot "logs"
Ensure-Directory -Path $logDir

Write-Host "=========================================="
Write-Host "Gold Trading - Start All Services"
Write-Host "=========================================="

& (Join-Path $PSScriptRoot "Stop-All.ps1") -Quiet

if (-not $SkipInstall) {
    Write-Host "Checking core dependencies..."
    Install-CoreDependencies
}

$wsPid = Start-PythonScript -ProjectRoot $projectRoot -ScriptRelativePath "src\websocket_server.py" -ScriptArgs @("--host", "0.0.0.0", "--port", "8765") -PidFile (Join-Path $projectRoot ".ws_pid") -LogFile (Join-Path $logDir "websocket.log")
Start-Sleep -Seconds 2

$klinePid = Start-PythonScript -ProjectRoot $projectRoot -ScriptRelativePath "app\kline_recorder_worker.py" -ScriptArgs @("--interval", "30") -PidFile (Join-Path $projectRoot ".kline_pid") -LogFile (Join-Path $logDir "kline.log")
Start-Sleep -Seconds 2

$dashPid = Start-PythonScript -ProjectRoot $projectRoot -ScriptRelativePath "app\dashboard_v3.py" -ScriptArgs @("--host", "0.0.0.0", "--port", "5000") -PidFile (Join-Path $projectRoot ".web_pid") -LogFile (Join-Path $logDir "dashboard.log")
Start-Sleep -Seconds 2

$env:ENABLE_INTERNAL_KLINE_RECORDER = "0"
$apiPid = Start-PythonScript -ProjectRoot $projectRoot -ScriptRelativePath "app\api_server.py" -ScriptArgs @("--host", "0.0.0.0", "--port", "8080") -PidFile (Join-Path $projectRoot ".api_pid") -LogFile (Join-Path $logDir "api.log")
Start-Sleep -Seconds 2

$portalPid = Start-PythonModule -WorkingDirectory (Join-Path $projectRoot "web") -ModuleName "http.server" -ModuleArgs @("8090") -PidFile (Join-Path $projectRoot ".portal_pid") -LogFile (Join-Path $logDir "web.log")
Start-Sleep -Seconds 1

Write-Host ""
Write-Host "Started PIDs:"
Write-Host "  WebSocket: $wsPid"
Write-Host "  Kline:     $klinePid"
Write-Host "  Dashboard: $dashPid"
Write-Host "  API:       $apiPid"
Write-Host "  Portal:    $portalPid"
Write-Host ""
Write-Host "URLs:"
Write-Host "  Dashboard: http://127.0.0.1:5000"
Write-Host "  API:       http://127.0.0.1:8080"
Write-Host "  WebSocket: ws://127.0.0.1:8765"
Write-Host "  Portal:    http://127.0.0.1:8090"
Write-Host ""
Write-Host "Use scripts\\Status.ps1 to inspect current status."
