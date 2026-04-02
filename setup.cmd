@echo off
setlocal
cd /d "%~dp0"

set "BOOTSTRAP_PYTHON="
set "VENV_PYTHON=%CD%\.venv\Scripts\python.exe"

if exist "%VENV_PYTHON%" goto install

python --version >nul 2>&1
if not errorlevel 1 (
    set "BOOTSTRAP_PYTHON=python"
    goto create_venv
)

py -3 --version >nul 2>&1
if not errorlevel 1 (
    set "BOOTSTRAP_PYTHON=py -3"
    goto create_venv
)

echo Python 3 was not found on PATH.
echo Install Python for your user account, then rerun setup.cmd.
exit /b 9009

:create_venv
echo Creating virtual environment in .venv...
%BOOTSTRAP_PYTHON% -m venv .venv
if errorlevel 1 (
    echo Failed to create .venv.
    exit /b %errorlevel%
)

:install
echo Installing dependencies from requirements.txt...
"%VENV_PYTHON%" -m pip install -r requirements.txt
if errorlevel 1 (
    echo Dependency install failed.
    echo Connect to the approved network or package source and rerun setup.cmd.
    exit /b %errorlevel%
)

echo.
echo Setup complete.
echo Next steps:
echo   1. Run the app with: run.cmd
echo   2. Or run it directly with: .venv\Scripts\python.exe app.py
echo   3. Open: http://localhost:8501
exit /b 0
