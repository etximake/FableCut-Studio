@echo off
setlocal
title FableCut Server Manager

for %%I in ("%~dp0..") do set "STUDIO_ROOT=%%~fI"
set "FABLECUT_DIR=%STUDIO_ROOT%\FableCut"
set "FABLECUT_DATA_DIR=%STUDIO_ROOT%\fablecut-data"
set "PORT=7777"
set "EDITOR_URL=http://localhost:7777"

if "%1"=="start" goto do_start
if "%1"=="stop" goto do_stop
if "%1"=="restart" goto do_restart
if "%1"=="status" goto do_status

:menu
cls
echo =======================================================
echo              FABLECUT SERVER MANAGER
echo =======================================================
echo   Port: 7777  -  Data: %FABLECUT_DATA_DIR%
echo =======================================================
echo [1] Start Server
echo [2] Stop Server
echo [3] Restart Server
echo [4] Check Status
echo [5] Open Editor
echo [6] Exit
echo =======================================================
set /p choice="Nhap lua chon [1-6]: "

if "%choice%"=="1" goto do_start
if "%choice%"=="2" goto do_stop
if "%choice%"=="3" goto do_restart
if "%choice%"=="4" goto do_status
if "%choice%"=="5" goto do_open
if "%choice%"=="6" goto do_exit
goto menu

:do_open
start %EDITOR_URL%
goto menu

:do_status
set "PID="
for /f "tokens=5" %%p in ('netstat -ano ^| findstr 7777 ^| findstr LISTENING') do set "PID=%%p"
if defined PID (
    echo [STATUS] FableCut Server DANG CHAY tai PID: %PID%
    echo URL: %EDITOR_URL%
) else (
    echo [STATUS] FableCut Server DANG TAT.
)
if "%1"=="" pause & goto menu
exit /b 0

:do_start
set "PID="
for /f "tokens=5" %%p in ('netstat -ano ^| findstr 7777 ^| findstr LISTENING') do set "PID=%%p"
if defined PID (
    echo [THONG BAO] Server da dang chay tai PID: %PID%
    start %EDITOR_URL%
    if "%1"=="" pause & goto menu
    exit /b 0
)

echo [KHOI DONG] Dang bat FableCut Server...
powershell -NoProfile -Command "$env:FABLECUT_DATA_DIR = '%FABLECUT_DATA_DIR%'; Start-Process -FilePath 'node' -ArgumentList 'server.js' -WorkingDirectory '%FABLECUT_DIR%' -WindowStyle Hidden"
timeout /t 2 >nul

set "PID="
for /f "tokens=5" %%p in ('netstat -ano ^| findstr 7777 ^| findstr LISTENING') do set "PID=%%p"
if defined PID (
    echo [THANH CONG] Server da chay tai PID: %PID%
    start %EDITOR_URL%
) else (
    echo [CANH BAO] Server dang khoi dong, vui long kiem tra lai status.
)
if "%1"=="" pause & goto menu
exit /b 0

:do_stop
echo [DUNG SERVER] Dang tim tien trinh FableCut tren cong 7777...
set "FOUND=0"
for /f "tokens=5" %%p in ('netstat -ano ^| findstr 7777 ^| findstr LISTENING') do (
    set "FOUND=1"
    echo Tim thay PID: %%p. Dang tat...
    taskkill /F /PID %%p >nul 2>&1
)
if "%FOUND%"=="1" (
    echo [THANH CONG] Da dung server va giai phong cong 7777.
) else (
    echo [THONG BAO] Khong co tien trinh nao chay tren cong 7777.
)
if "%1"=="" pause & goto menu
exit /b 0

:do_restart
call :do_stop
timeout /t 2 >nul
call :do_start
if "%1"=="" pause & goto menu
exit /b 0

:do_exit
exit /b 0
