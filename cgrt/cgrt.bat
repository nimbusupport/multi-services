@echo off
setlocal
set "SCRIPT_DIR=%~dp0"
set "VENV_PY=%SCRIPT_DIR%..\.venv\Scripts\python.exe"
set "APP_URL=http://127.0.0.1:1002/"

if exist "%VENV_PY%" (
  powershell -NoProfile -WindowStyle Hidden -Command "Start-Process -FilePath '%VENV_PY%' -ArgumentList '\"%SCRIPT_DIR%server.py\"' -WindowStyle Hidden"
) else (
  powershell -NoProfile -WindowStyle Hidden -Command "Start-Process -FilePath 'python' -ArgumentList '\"%SCRIPT_DIR%server.py\"' -WindowStyle Hidden"
)

timeout /t 2 /nobreak >nul
start "" "%APP_URL%"
