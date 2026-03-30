Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

. (Join-Path $PSScriptRoot "Common.ps1")

$projectRoot = Get-ProjectRoot
$webDir = Join-Path $projectRoot "web"
$logDir = Join-Path $projectRoot "logs"
Ensure-Directory -Path $logDir

if (-not (Test-Path -LiteralPath $webDir)) {
    throw "Web directory not found: $webDir"
}

& (Join-Path $PSScriptRoot "Stop-Web.ps1") -Quiet

$ports = Get-ServicePorts -ProjectRoot $projectRoot
$portalPort = Get-AvailablePort -PreferredPort ([int]$ports.portal) -StartPort 8090 -EndPort 8999
$ports.portal = $portalPort
Save-ServicePorts -ProjectRoot $projectRoot -Ports $ports
Write-WebRuntimeConfig -ProjectRoot $projectRoot -Ports $ports

$portalPid = Start-PythonModule -WorkingDirectory $webDir -ModuleName "http.server" -ModuleArgs @("$portalPort") -PidFile (Join-Path $projectRoot ".portal_pid") -LogFile (Join-Path $logDir "web.log")

Start-Sleep -Seconds 1
Write-Host "Static web portal started. PID: $portalPid"
Write-Host "URL: http://127.0.0.1:$portalPort"
