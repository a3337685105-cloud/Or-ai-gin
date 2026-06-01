@echo off
setlocal

cd /d "%~dp0"

where powershell.exe >nul 2>nul
if errorlevel 1 (
  echo PowerShell was not found. Please install PowerShell or start the app with Python manually.
  pause
  exit /b 1
)

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start_web.ps1" %*
set EXITCODE=%ERRORLEVEL%

if not "%EXITCODE%"=="0" (
  echo.
  echo Origin AI Lab failed to start. See the message above.
  echo Press any key to close this window.
  pause >nul
)

exit /b %EXITCODE%
