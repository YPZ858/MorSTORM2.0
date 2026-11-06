@echo off
setlocal
set "PYTHON_GUI=%~dp0.venv\Scripts\pythonw.exe"
if not exist "%PYTHON_GUI%" (
    echo Create the .venv environment using README.zh.md.
    pause
    exit /b 1
)
start "MorSTORM" "%PYTHON_GUI%" "%~dp0gui\app.py" --lang zh
