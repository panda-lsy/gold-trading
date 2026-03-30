Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

. (Join-Path $PSScriptRoot "Common.ps1")

$projectRoot = Get-ProjectRoot

function Get-PidValue {
    param([string]$PidFile)

    if (-not (Test-Path -LiteralPath $PidFile)) {
        return $null
    }

    $raw = Get-Content -Path $PidFile -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($raw -and $raw -match '^\d+$') {
        return [int]$raw
    }

    return $null
}

function Show-ServiceStatus {
    param(
        [string]$Name,
        [string]$PidFile,
        [int]$Port
    )

    $pidValue = Get-PidValue -PidFile $PidFile
    $running = $false

    if ($pidValue) {
        $proc = Get-Process -Id $pidValue -ErrorAction SilentlyContinue
        $running = $null -ne $proc
    }

    $portOpen = Test-PortOpen -Port $Port

    Write-Host "[$Name]"
    Write-Host "  PID file: $PidFile"
    Write-Host "  PID:      $pidValue"
    Write-Host "  Running:  $running"
    Write-Host "  Port $Port open: $portOpen"
    Write-Host ""
}

Write-Host "=========================================="
Write-Host "Gold Trading - Service Status"
Write-Host "=========================================="

Show-ServiceStatus -Name "WebSocket" -PidFile (Join-Path $projectRoot ".ws_pid") -Port 8765
Show-ServiceStatus -Name "Kline" -PidFile (Join-Path $projectRoot ".kline_pid") -Port 0
Show-ServiceStatus -Name "Dashboard" -PidFile (Join-Path $projectRoot ".web_pid") -Port 5000
Show-ServiceStatus -Name "API" -PidFile (Join-Path $projectRoot ".api_pid") -Port 8080
Show-ServiceStatus -Name "Service" -PidFile (Join-Path $projectRoot ".service_pid") -Port 0
Show-ServiceStatus -Name "Portal" -PidFile (Join-Path $projectRoot ".portal_pid") -Port 8090

Write-Host "Recent logs:"
foreach ($name in @("websocket", "kline", "dashboard", "api", "service", "web")) {
    $logFile = Join-Path $projectRoot ("logs\\$name.log")
    Write-Host ""
    Write-Host "[$name] $logFile"
    if (Test-Path -LiteralPath $logFile) {
        Get-Content -Path $logFile -Tail 3 -ErrorAction SilentlyContinue
    }
    else {
        Write-Host "(no log yet)"
    }
}
