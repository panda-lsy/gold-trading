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

$ports = Get-ServicePorts -ProjectRoot $projectRoot

Show-ServiceStatus -Name "WebSocket" -PidFile (Join-Path $projectRoot ".ws_pid") -Port ([int]$ports.websocket)
Show-ServiceStatus -Name "Kline" -PidFile (Join-Path $projectRoot ".kline_pid") -Port 0
Show-ServiceStatus -Name "Dashboard" -PidFile (Join-Path $projectRoot ".web_pid") -Port ([int]$ports.dashboard)
Show-ServiceStatus -Name "API" -PidFile (Join-Path $projectRoot ".api_pid") -Port ([int]$ports.api)
Show-ServiceStatus -Name "Service" -PidFile (Join-Path $projectRoot ".service_pid") -Port 0
Show-ServiceStatus -Name "Portal" -PidFile (Join-Path $projectRoot ".portal_pid") -Port ([int]$ports.portal)

Write-Host "URLs:"
Write-Host "  Dashboard (chart only): http://127.0.0.1:$($ports.dashboard)"
Write-Host "  API:       http://127.0.0.1:$($ports.api)"
Write-Host "  WebSocket: ws://127.0.0.1:$($ports.websocket)"
Write-Host "  Portal (full workspace): http://127.0.0.1:$($ports.portal)"
Write-Host ""
Write-Host "Tip: Open the Portal URL to access all tabs (Dashboard + AI + Ops)."
Write-Host ""

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
