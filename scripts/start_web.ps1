[CmdletBinding()]
param(
  [string]$HostAddress = "127.0.0.1",
  [int]$Port = 8765,
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

$Args = @(
  "-m", "origin_ai_lab.web_server",
  "--host", $HostAddress,
  "--port", [string]$Port
)

if (-not $NoBrowser) {
  $Args += "--open"
}

Write-Host "Starting Origin AI Lab at http://$HostAddress`:$Port" -ForegroundColor Cyan
& $PythonCmd @PythonPrefix @Args
