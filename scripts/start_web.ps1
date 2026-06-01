[CmdletBinding()]
param(
  [string]$HostAddress = "127.0.0.1",
  [int]$Port = 8765,
  [switch]$Setup,
  [switch]$WithVisual,
  [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"
$Utf8NoBom = New-Object System.Text.UTF8Encoding $false
[Console]::OutputEncoding = $Utf8NoBom
$OutputEncoding = $Utf8NoBom
$env:PYTHONUTF8 = "1"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $Root
$env:PYTHONPATH = Join-Path $Root "src"

$PythonCmd = $env:ORIGIN_AI_PYTHON
$PythonPrefix = @()

if (-not $PythonCmd) {
  if (Get-Command py -ErrorAction SilentlyContinue) {
    $PythonCmd = "py"
    $PythonPrefix = @("-3")
  } elseif (Get-Command python -ErrorAction SilentlyContinue) {
    $PythonCmd = "python"
  } else {
    throw "Python 3.10+ was not found. Run scripts\setup_windows.ps1 after installing Python."
  }
}

function Invoke-OriginAiPython {
  param(
    [string[]]$CommandArgs
  )
  & $PythonCmd @PythonPrefix @CommandArgs
  if ($LASTEXITCODE -ne 0) {
    throw "Command failed: $PythonCmd $($PythonPrefix -join ' ') $($CommandArgs -join ' ')"
  }
}

function Get-ListenAddress {
  param(
    [string]$Address
  )
  if ($Address -eq "localhost") {
    return [System.Net.IPAddress]::Loopback
  }
  if ($Address -eq "0.0.0.0") {
    return [System.Net.IPAddress]::Any
  }
  return [System.Net.IPAddress]::Parse($Address)
}

function Test-PortAvailable {
  param(
    [string]$Address,
    [int]$TcpPort
  )
  $Listener = $null
  try {
    $ListenAddress = Get-ListenAddress -Address $Address
    $Listener = [System.Net.Sockets.TcpListener]::new($ListenAddress, $TcpPort)
    $Listener.Start()
    return $true
  } catch {
    return $false
  } finally {
    if ($Listener) {
      $Listener.Stop()
    }
  }
}

Invoke-OriginAiPython -CommandArgs @(
  "-c",
  "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 'Python 3.10+ is required.')"
)

if ($Setup) {
  $InstallTarget = if ($WithVisual) { ".[visual]" } else { "." }
  Write-Host "Installing editable package: $InstallTarget" -ForegroundColor Cyan
  Invoke-OriginAiPython -CommandArgs @(
    "-m", "pip", "install",
    "--disable-pip-version-check",
    "--no-warn-script-location",
    "-e", $InstallTarget
  )
}

if (-not (Test-PortAvailable -Address $HostAddress -TcpPort $Port)) {
  throw "Port $Port on $HostAddress is already in use. Try: .\scripts\start_web.ps1 -Port 8766"
}

$Args = @(
  "-m", "origin_ai_lab.web_server",
  "--host", $HostAddress,
  "--port", [string]$Port
)

if (-not $NoBrowser) {
  $Args += "--open"
}

Write-Host "Origin AI Lab" -ForegroundColor Cyan
Write-Host "Project: $Root"
Write-Host "Web UI:  http://$HostAddress`:$Port"
Write-Host "Stop:    press Ctrl+C in this window"
Write-Host ""
& $PythonCmd @PythonPrefix @Args
