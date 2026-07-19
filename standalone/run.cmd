@echo off
REM RegMap standalone launcher for Windows. Double-click this file, or run it from a terminal.
setlocal
cd /d "%~dp0"

set "PY="
where py >nul 2>nul && set "PY=py"
if not defined PY ( where python >nul 2>nul && set "PY=python" )

if not defined PY (
  echo.
  echo Python 3 was not found on this machine.
  echo Install it from https://www.python.org/downloads/ ^(tick "Add python.exe to PATH"^),
  echo then double-click this file again.
  echo.
  pause
  exit /b 1
)

"%PY%" launcher.py %*
echo.
pause
