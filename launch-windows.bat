@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo PaheBatcher has not been installed yet.
  echo Run install-windows.bat first.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -m pahebatcher.gui
if errorlevel 1 (
  echo.
  echo PaheBatcher exited with an error. Copy the message above when reporting it.
  pause
  exit /b 1
)
exit /b 0
