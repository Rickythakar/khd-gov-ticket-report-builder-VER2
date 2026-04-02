@echo off
setlocal
cd /d "%~dp0"

set "VENV_PYTHON=%CD%\.venv\Scripts\python.exe"

if exist "%VENV_PYTHON%" (
    "%VENV_PYTHON%" app.py %*
    exit /b %errorlevel%
)

python app.py %*
if not errorlevel 9009 (
    exit /b %errorlevel%
)

py -3 app.py %*
if not errorlevel 9009 (
    exit /b %errorlevel%
)

echo Python was not found. Install Python or create .venv with setup.cmd.
exit /b 9009
