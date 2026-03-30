Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

. (Join-Path $PSScriptRoot "Common.ps1")

$projectRoot = Get-ProjectRoot
$logDir = Join-Path $projectRoot "logs"
Ensure-Directory -Path $logDir

& (Join-Path $PSScriptRoot "Stop-Service.ps1") -Quiet

$servicePid = Start-PythonScript -ProjectRoot $projectRoot -ScriptRelativePath "ops\jijin_service.py" -ScriptArgs @("--mode", "service") -PidFile (Join-Path $projectRoot ".service_pid") -LogFile (Join-Path $logDir "service.log")

Start-Sleep -Seconds 2
Write-Host "Service started. PID: $servicePid"
