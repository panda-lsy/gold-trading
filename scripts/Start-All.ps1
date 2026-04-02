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

$ports = Get-ServicePorts -ProjectRoot $projectRoot
$wsPort = Get-AvailablePort -PreferredPort ([int]$ports.websocket) -StartPort 8700 -EndPort 8999
$dashPort = Get-AvailablePort -PreferredPort ([int]$ports.dashboard) -StartPort 5000 -EndPort 5999
$apiPort = Get-AvailablePort -PreferredPort ([int]$ports.api) -StartPort 8000 -EndPort 8999
$portalPort = Get-AvailablePort -PreferredPort ([int]$ports.portal) -StartPort 8090 -EndPort 8999
$gatewayPort = Get-AvailablePort -PreferredPort ([int]$ports.gateway) -StartPort 9000 -EndPort 9999

$ports.websocket = $wsPort
$ports.dashboard = $dashPort
$ports.api = $apiPort
$ports.portal = $portalPort
$ports.gateway = $gatewayPort
Save-ServicePorts -ProjectRoot $projectRoot -Ports $ports
Write-WebRuntimeConfig -ProjectRoot $projectRoot -Ports $ports

$wsPid = Start-PythonScript -ProjectRoot $projectRoot -ScriptRelativePath "src\websocket_server.py" -ScriptArgs @("--host", "0.0.0.0", "--port", "$wsPort") -PidFile (Join-Path $projectRoot ".ws_pid") -LogFile (Join-Path $logDir "websocket.log")
Start-Sleep -Seconds 2

$klinePid = Start-PythonScript -ProjectRoot $projectRoot -ScriptRelativePath "app\kline_recorder_worker.py" -ScriptArgs @("--interval", "30") -PidFile (Join-Path $projectRoot ".kline_pid") -LogFile (Join-Path $logDir "kline.log")
Start-Sleep -Seconds 2

$dashPid = Start-PythonScript -ProjectRoot $projectRoot -ScriptRelativePath "app\dashboard_v3.py" -ScriptArgs @("--host", "0.0.0.0", "--port", "$dashPort") -PidFile (Join-Path $projectRoot ".web_pid") -LogFile (Join-Path $logDir "dashboard.log")
Start-Sleep -Seconds 2

$env:ENABLE_INTERNAL_KLINE_RECORDER = "0"
$apiPid = Start-PythonScript -ProjectRoot $projectRoot -ScriptRelativePath "app\api_server.py" -ScriptArgs @("--host", "0.0.0.0", "--port", "$apiPort") -PidFile (Join-Path $projectRoot ".api_pid") -LogFile (Join-Path $logDir "api.log")
Start-Sleep -Seconds 2

$portalPid = Start-PythonModule -WorkingDirectory (Join-Path $projectRoot "web") -ModuleName "http.server" -ModuleArgs @("$portalPort") -PidFile (Join-Path $projectRoot ".portal_pid") -LogFile (Join-Path $logDir "web.log")
Start-Sleep -Seconds 1

$gatewayPid = Start-PythonScript -ProjectRoot $projectRoot -ScriptRelativePath "app\single_port_gateway.py" -ScriptArgs @(
    "--host", "0.0.0.0",
    "--port", "$gatewayPort",
    "--dashboard-upstream", "http://127.0.0.1:$dashPort",
    "--api-upstream", "http://127.0.0.1:$apiPort",
    "--ws-upstream", "ws://127.0.0.1:$wsPort",
    "--portal-upstream", "http://127.0.0.1:$portalPort"
) -PidFile (Join-Path $projectRoot ".gateway_pid") -LogFile (Join-Path $logDir "gateway.log")
Start-Sleep -Seconds 1

Write-Host ""
Write-Host "Started PIDs:"
Write-Host "  WebSocket: $wsPid"
Write-Host "  Kline:     $klinePid"
Write-Host "  Dashboard: $dashPid"
Write-Host "  API:       $apiPid"
Write-Host "  Portal:    $portalPid"
Write-Host "  Gateway:   $gatewayPid"
Write-Host ""
Write-Host "URLs:"
Write-Host "  Dashboard (chart only): http://127.0.0.1:$dashPort"
Write-Host "  API:       http://127.0.0.1:$apiPort"
Write-Host "  WebSocket: ws://127.0.0.1:$wsPort"
Write-Host "  Portal (full workspace): http://127.0.0.1:$portalPort"
Write-Host "  Gateway (single port):   http://127.0.0.1:$gatewayPort"
Write-Host ""
Write-Host "Tip: Open the Portal URL to access all tabs (Dashboard + AI + Ops)."
Write-Host ""
Write-Host "Use scripts\\Status.ps1 to inspect current status."
