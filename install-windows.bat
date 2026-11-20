@echo off
setlocal
cd /d "%~dp0"
echo.
echo ===== PaheBatcher for Windows 11 =====
echo Installing into a private virtual environment in this folder.
echo Python 3.12 (64-bit) is recommended.
echo.
where py >nul 2>&1
if errorlevel 1 (
  echo ERROR: Python launcher "py" was not found.
  echo Install Python 3.12 from https://www.python.org/downloads/windows/
  echo Enable the Python launcher during setup and reopen this window.
  pause
  exit /b 1
)
py -3.12 -c "import sys; assert sys.maxsize > 2**32" >nul 2>&1
if errorlevel 1 (
  echo ERROR: 64-bit Python 3.12 was not found.
  echo Install the 64-bit release from https://www.python.org/downloads/windows/
  pause
  exit /b 1
)
if not exist ".venv\Scripts\python.exe" (
  py -3.12 -m venv .venv
  if errorlevel 1 goto :fail
)
".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto :fail
".venv\Scripts\python.exe" -m pip install -e ".[browser]"
if errorlevel 1 goto :fail
echo.
echo Installation finished. Run launch-windows.bat to start the desktop app.
echo The app can install FFmpeg when needed. Edge or Chrome is required for the browser solver.
pause
exit /b 0
:fail
echo.
echo Installation failed. Copy the error shown above when reporting the problem.
pause
exit /b 1
