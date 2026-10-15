@echo off
setlocal
set "PROJECT=%~dp0.."
set "PYTHON=%~dp0.venv\Scripts\pythonw.exe"
if not exist "%PYTHON%" (
    echo Run dev\setup.ps1 first.
    exit /b 1
)
start "" "%PYTHON%" "%PROJECT%\src\app.py"
