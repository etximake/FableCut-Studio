@echo off
chcp 65001 >nul 2>nul
title "Dung AI Video Commentary Studio"

echo [INFO] Dang kiem tra va tat may chu AI Video Commentary Studio...

set "FOUND=0"
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8001" ^| findstr "LISTENING"') do (
    set "FOUND=1"
    echo [INFO] Dang tat tien trinh PID %%a tren port 8001...
    taskkill /F /PID %%a >nul 2>nul
)

for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8002" ^| findstr "LISTENING"') do (
    set "FOUND=1"
    echo [INFO] Dang tat tien trinh PID %%a tren port 8002...
    taskkill /F /PID %%a >nul 2>nul
)

if "%FOUND%"=="1" (
    echo [SUCCESS] Da dung may chu thanh cong.
) else (
    echo [INFO] Khong co may chu nao dang chay tren port 8001 hoac 8002.
)

timeout /t 2 >nul
exit /b 0
