[CmdletBinding()]
param(
  [switch]$WithVisual,
  [switch]$RunTests
)

$ErrorActionPreference = "Stop"
$Utf8NoBom = New-Object System.Text.UTF8Encoding $false
[Console]::OutputEncoding = $Utf8NoBom
$OutputEncoding = $Utf8NoBom
$env:PYTHONUTF8 = "1"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $Root

$PythonCmd = $env:ORIGIN_AI_PYTHON
$PythonPrefix = @()

if (-not $PythonCmd) {
  if (Get-Command py -ErrorAction SilentlyContinue) {
    $PythonCmd = "py"
    $PythonPrefix = @("-3")
  } elseif (Get-Command python -ErrorAction SilentlyContinue) {
    $PythonCmd = "python"
  } else {
    throw "Python 3.10+ was not found. Install Python, then rerun this script."
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

Write-Host "Origin AI Lab setup" -ForegroundColor Cyan
Write-Host "Project: $Root"

Invoke-OriginAiPython -CommandArgs @("--version")
Invoke-OriginAiPython -CommandArgs @("-m", "pip", "install", "--disable-pip-version-check", "--no-warn-script-location", "-e", ".")

if ($WithVisual) {
  Invoke-OriginAiPython -CommandArgs @("-m", "pip", "install", "--disable-pip-version-check", "--no-warn-script-location", "-e", ".[visual]")
}

if ($RunTests) {
  Invoke-OriginAiPython -CommandArgs @("-m", "unittest", "discover", "-s", "tests")
  Invoke-OriginAiPython -CommandArgs @("scripts\check_guardrails.py", "--policy", ".codex\harness-policy.json")
}

Write-Host ""
Write-Host "Ready. Start the web UI with:" -ForegroundColor Green
Write-Host "  .\scripts\start_web.ps1"
Write-Host ""
Write-Host "No API key is required for the rule-based planner. Configure Qwen later in the web UI when needed."
