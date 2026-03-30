param(
    [switch]$Quiet
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$pidFile = Join-Path $projectRoot ".portal_pid"

if (Test-Path -LiteralPath $pidFile) {
    $rawPid = Get-Content -Path $pidFile -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($rawPid -and $rawPid -match '^\d+$') {
        $proc = Get-Process -Id ([int]$rawPid) -ErrorAction SilentlyContinue
        if ($proc) {
            Stop-Process -Id ([int]$rawPid) -Force -ErrorAction SilentlyContinue
        }
    }
    Remove-Item -LiteralPath $pidFile -Force -ErrorAction SilentlyContinue
}

$procs = Get-CimInstance Win32_Process
foreach ($proc in $procs) {
    if ($proc.CommandLine -and $proc.CommandLine -like "*http.server 8090*") {
        Stop-Process -Id $proc.ProcessId -Force -ErrorAction SilentlyContinue
    }
}

if (-not $Quiet) {
    Write-Host "Web portal stop command completed."
}
