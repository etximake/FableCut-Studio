@echo off
chcp 65001 >nul 2>nul
setlocal EnableExtensions
title "AI Video Commentary & CapCut Engine"

cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" (
    set "PY_LAUNCHER=.venv\Scripts\python.exe"
) else (
    set "PY_LAUNCHER=python"
    where python >nul 2>nul
    if errorlevel 1 (
        set "PY_LAUNCHER=py -3"
    )
)

if "%~1"=="" goto :web
if /i "%~1"=="web" goto :web
if /i "%~1"=="test" goto :test

echo Cach dung:
echo   run.bat        - Chay FastAPI Web Server (main.py)
echo   run.bat test   - Chay kiem thu pytest
pause
exit /b 1

:web
echo [INFO] Dang khoi dong AI Video Commentary Studio...
echo [INFO] Web UI: http://localhost:8001/
echo [INFO] Swagger Docs: http://localhost:8001/docs
echo [INFO] (Dong cua so nay hoac an Ctrl+C de TAT HOAN TOAN ung dung)
echo.
"%PY_LAUNCHER%" main.py
if errorlevel 1 (
    echo.
    echo [ERROR] Ung dung bi dung hoac gap loi khi khoi dong.
    pause
)
goto :end

:test
echo [INFO] Dang chay pytest...
"%PY_LAUNCHER%" -m pytest -v
if errorlevel 1 (
    echo.
    echo [ERROR] Mot so bai kiem thu bi loi.
    pause
)
goto :end

:end
endlocal
exit /b %ERRORLEVEL%
