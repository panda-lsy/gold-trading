Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

. (Join-Path $PSScriptRoot "Common.ps1")

$projectRoot = Get-ProjectRoot
$logDir = Join-Path $projectRoot "logs"
Ensure-Directory -Path $logDir

& (Join-Path $PSScriptRoot "Stop-Dashboard.ps1") -Quiet

$ports = Get-ServicePorts -ProjectRoot $projectRoot
$wsPort = Get-AvailablePort -PreferredPort ([int]$ports.websocket) -StartPort 8700 -EndPort 8999
$dashPort = Get-AvailablePort -PreferredPort ([int]$ports.dashboard) -StartPort 5000 -EndPort 5999

$ports.websocket = $wsPort
$ports.dashboard = $dashPort
Save-ServicePorts -ProjectRoot $projectRoot -Ports $ports
Write-WebRuntimeConfig -ProjectRoot $projectRoot -Ports $ports

$wsPid = Start-PythonScript -ProjectRoot $projectRoot -ScriptRelativePath "src\websocket_server.py" -ScriptArgs @("--host", "0.0.0.0", "--port", "$wsPort") -PidFile (Join-Path $projectRoot ".ws_pid") -LogFile (Join-Path $logDir "websocket.log")
Start-Sleep -Seconds 2

$dashPid = Start-PythonScript -ProjectRoot $projectRoot -ScriptRelativePath "app\dashboard_v3.py" -ScriptArgs @("--host", "0.0.0.0", "--port", "$dashPort") -PidFile (Join-Path $projectRoot ".web_pid") -LogFile (Join-Path $logDir "dashboard.log")
Start-Sleep -Seconds 2

Write-Host "Dashboard stack started."
Write-Host "  WebSocket PID: $wsPid"
Write-Host "  Dashboard PID: $dashPid"
Write-Host "  URL: http://127.0.0.1:$dashPort"
