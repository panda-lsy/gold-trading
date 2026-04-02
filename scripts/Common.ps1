Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Get-ProjectRoot {
    return (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
}

function Ensure-Directory {
    param([Parameter(Mandatory = $true)][string]$Path)

    if (-not (Test-Path -LiteralPath $Path)) {
        New-Item -ItemType Directory -Path $Path -Force | Out-Null
    }
}

function Get-PythonLauncher {
    $projectRoot = Get-ProjectRoot
    $localPython = Join-Path $projectRoot ".conda\python.exe"
    if (Test-Path -LiteralPath $localPython) {
        return @{
            Exe = $localPython
            Prefix = @()
        }
    }

    $py = Get-Command py -ErrorAction SilentlyContinue
    if ($py) {
        return @{
            Exe = "py"
            Prefix = @("-3")
        }
    }

    foreach ($candidate in @("python", "python3")) {
        $cmd = Get-Command $candidate -ErrorAction SilentlyContinue
        if ($cmd) {
            return @{
                Exe = $candidate
                Prefix = @()
            }
        }
    }

    throw "Python was not found. Install Python 3 and ensure it is on PATH."
}

function Start-PythonScript {
    param(
        [Parameter(Mandatory = $true)][string]$ProjectRoot,
        [Parameter(Mandatory = $true)][string]$ScriptRelativePath,
        [Parameter(Mandatory = $true)][string[]]$ScriptArgs,
        [Parameter(Mandatory = $true)][string]$PidFile,
        [Parameter(Mandatory = $true)][string]$LogFile
    )

    $launcher = Get-PythonLauncher
    $scriptPath = Join-Path $ProjectRoot $ScriptRelativePath

    if (-not (Test-Path -LiteralPath $scriptPath)) {
        throw "Script not found: $scriptPath"
    }

    Ensure-Directory -Path (Split-Path -Parent $LogFile)
    $errFile = "$LogFile.err"

    $argumentList = @()
    $argumentList += $launcher.Prefix
    $argumentList += $scriptPath
    $argumentList += $ScriptArgs

    $proc = Start-Process -FilePath $launcher.Exe -ArgumentList $argumentList -WorkingDirectory $ProjectRoot -RedirectStandardOutput $LogFile -RedirectStandardError $errFile -PassThru -WindowStyle Hidden
    Set-Content -Path $PidFile -Value $proc.Id -Encoding ASCII

    return $proc.Id
}

function Start-PythonModule {
    param(
        [Parameter(Mandatory = $true)][string]$WorkingDirectory,
        [Parameter(Mandatory = $true)][string]$ModuleName,
        [Parameter(Mandatory = $true)][string[]]$ModuleArgs,
        [Parameter(Mandatory = $true)][string]$PidFile,
        [Parameter(Mandatory = $true)][string]$LogFile
    )

    $launcher = Get-PythonLauncher
    Ensure-Directory -Path (Split-Path -Parent $LogFile)
    $errFile = "$LogFile.err"

    $argumentList = @()
    $argumentList += $launcher.Prefix
    $argumentList += @("-m", $ModuleName)
    $argumentList += $ModuleArgs

    $proc = Start-Process -FilePath $launcher.Exe -ArgumentList $argumentList -WorkingDirectory $WorkingDirectory -RedirectStandardOutput $LogFile -RedirectStandardError $errFile -PassThru -WindowStyle Hidden
    Set-Content -Path $PidFile -Value $proc.Id -Encoding ASCII

    return $proc.Id
}

function Stop-FromPidFile {
    param([Parameter(Mandatory = $true)][string]$PidFile)

    if (-not (Test-Path -LiteralPath $PidFile)) {
        return $false
    }

    $raw = Get-Content -Path $PidFile -ErrorAction SilentlyContinue | Select-Object -First 1
    $stopped = $false

    if ($raw -and $raw -match '^\d+$') {
        $procId = [int]$raw
        $proc = Get-Process -Id $procId -ErrorAction SilentlyContinue
        if ($proc) {
            Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
            $stopped = $true
        }
    }

    Remove-Item -LiteralPath $PidFile -Force -ErrorAction SilentlyContinue
    return $stopped
}

function Stop-ByCommandPatterns {
    param([Parameter(Mandatory = $true)][string[]]$Patterns)

    $procs = Get-CimInstance Win32_Process
    foreach ($proc in $procs) {
        $cmd = $proc.CommandLine
        if (-not $cmd) {
            continue
        }

        foreach ($pattern in $Patterns) {
            if ($cmd -like "*$pattern*") {
                Stop-Process -Id $proc.ProcessId -Force -ErrorAction SilentlyContinue
                break
            }
        }
    }
}

function Test-PortOpen {
    param([Parameter(Mandatory = $true)][int]$Port)

    if ($Port -le 0) {
        return $false
    }

    try {
        return Test-NetConnection -ComputerName 127.0.0.1 -Port $Port -InformationLevel Quiet -WarningAction SilentlyContinue
    }
    catch {
        return $false
    }
}

function Test-PortAvailable {
    param([Parameter(Mandatory = $true)][int]$Port)

    if ($Port -le 0 -or $Port -gt 65535) {
        return $false
    }

    try {
        $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, $Port)
        $listener.Start()
        $listener.Stop()
        return $true
    }
    catch {
        return $false
    }
}

function Get-AvailablePort {
    param(
        [Parameter(Mandatory = $true)][int]$PreferredPort,
        [Parameter(Mandatory = $true)][int]$StartPort,
        [Parameter(Mandatory = $true)][int]$EndPort
    )

    if (Test-PortAvailable -Port $PreferredPort) {
        return $PreferredPort
    }

    for ($port = $StartPort; $port -le $EndPort; $port++) {
        if (Test-PortAvailable -Port $port) {
            return $port
        }
    }

    throw "No available port found in range $StartPort-$EndPort."
}

function Get-ServicePorts {
    param([Parameter(Mandatory = $true)][string]$ProjectRoot)

    $defaults = @{
        websocket = 8765
        dashboard = 5000
        api = 8080
        portal = 8090
        gateway = 9002
    }

    $portsFile = Join-Path $ProjectRoot ".service_ports.json"
    if (-not (Test-Path -LiteralPath $portsFile)) {
        return $defaults
    }

    try {
        $raw = Get-Content -Path $portsFile -Raw -ErrorAction Stop
        if (-not $raw) {
            return $defaults
        }

        $obj = $raw | ConvertFrom-Json -ErrorAction Stop
        foreach ($key in @("websocket", "dashboard", "api", "portal", "gateway")) {
            if ($null -ne $obj.$key -and [int]$obj.$key -gt 0) {
                $defaults[$key] = [int]$obj.$key
            }
        }
    }
    catch {
        return $defaults
    }

    return $defaults
}

function Save-ServicePorts {
    param(
        [Parameter(Mandatory = $true)][string]$ProjectRoot,
        [Parameter(Mandatory = $true)][hashtable]$Ports
    )

    $portsFile = Join-Path $ProjectRoot ".service_ports.json"
    $payload = [ordered]@{
        websocket = [int]$Ports.websocket
        dashboard = [int]$Ports.dashboard
        api = [int]$Ports.api
        portal = [int]$Ports.portal
        gateway = [int]$Ports.gateway
    }

    $json = $payload | ConvertTo-Json
    Set-Content -Path $portsFile -Value $json -Encoding ASCII
}

function Write-WebRuntimeConfig {
    param(
        [Parameter(Mandatory = $true)][string]$ProjectRoot,
        [Parameter(Mandatory = $true)][hashtable]$Ports
    )

    $webDir = Join-Path $ProjectRoot "web"
    Ensure-Directory -Path $webDir

    $apiBase = if ($env:PUBLIC_API_BASE) {
        $env:PUBLIC_API_BASE
    }
    elseif ($env:NATAPP_API_BASE) {
        $env:NATAPP_API_BASE
    }
    else {
        "http://127.0.0.1:$($Ports.api)"
    }

    $dashboardBase = if ($env:PUBLIC_DASHBOARD_BASE) {
        $env:PUBLIC_DASHBOARD_BASE
    }
    elseif ($env:NATAPP_DASHBOARD_BASE) {
        $env:NATAPP_DASHBOARD_BASE
    }
    else {
        "http://127.0.0.1:$($Ports.dashboard)"
    }

    $configPath = Join-Path $webDir "runtime-config.js"
    $content = @(
        "window.__API_BASE__ = '$apiBase';",
        "window.__DASHBOARD_BASE__ = '$dashboardBase';"
    )

    Set-Content -Path $configPath -Value $content -Encoding ASCII
}

function Install-CoreDependencies {
    $launcher = Get-PythonLauncher
    $pipInstallParameters = @()
    $pipInstallParameters += $launcher.Prefix
    $pipInstallParameters += @("-m", "pip", "install", "flask", "flask-cors", "websockets", "aiohttp")

    try {
        & $launcher.Exe @pipInstallParameters | Out-Null
    }
    catch {
        Write-Warning "Dependency installation failed: $($_.Exception.Message)"
    }
}
