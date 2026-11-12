@echo off
setlocal EnableExtensions
title FableCut Pipeline Batch Cleanup

set "BUNDLE_DIR=%~dp0"
for %%I in ("%~dp0..") do set "STUDIO_ROOT=%%~fI"
set "CLEANUP_PY=%BUNDLE_DIR%cleanup.py"
set "FABLECUT_DATA_DIR=%STUDIO_ROOT%\fablecut-data"
set "ANALYST_DIR=%STUDIO_ROOT%\youtube-analyst-niches-forest"

if not exist "%CLEANUP_PY%" (
    echo [LOI] Khong tim thay file: "%CLEANUP_PY%"
    pause
    exit /b 1
)

call :find_python
if errorlevel 1 (
    echo [LOI] Khong tim thay Python ^(py -3.10 / py / python^) trong PATH.
    pause
    exit /b 1
)

if "%~1"=="" goto menu
if /I "%~1"=="preview" goto cli_preview
if /I "%~1"=="dry-run" goto cli_preview
if /I "%~1"=="keep" goto cli_keep
if /I "%~1"=="days" goto cli_days

%PYTHON_CMD% "%CLEANUP_PY%" %*
exit /b %ERRORLEVEL%

:cli_preview
%PYTHON_CMD% "%CLEANUP_PY%" --analyst-dir "%ANALYST_DIR%" --data-dir "%FABLECUT_DATA_DIR%" --dry-run
exit /b %ERRORLEVEL%

:cli_keep
if "%~2"=="" (
    echo Cach dung: cleanup.bat keep ^<so_luong_giu_lai^> [--dry-run^|--yes]
    exit /b 1
)
%PYTHON_CMD% "%CLEANUP_PY%" --analyst-dir "%ANALYST_DIR%" --data-dir "%FABLECUT_DATA_DIR%" --keep-latest %~2 %3 %4 %5 %6
exit /b %ERRORLEVEL%

:cli_days
if "%~2"=="" (
    echo Cach dung: cleanup.bat days ^<so_ngay^> [--dry-run^|--yes]
    exit /b 1
)
%PYTHON_CMD% "%CLEANUP_PY%" --analyst-dir "%ANALYST_DIR%" --data-dir "%FABLECUT_DATA_DIR%" --older-than-days %~2 %3 %4 %5 %6
exit /b %ERRORLEVEL%

:menu
cls
echo =======================================================
echo           FABLECUT PIPELINE BATCH CLEANUP
echo =======================================================
echo   Temp    : %ANALYST_DIR%\temp
echo   Media   : %FABLECUT_DATA_DIR%\media
echo   Bao ve  : exports\, library\, projects\, project.json
echo =======================================================
echo [1] Xem truoc danh sach don dep (Dry-run - An toan)
echo [2] Don lo cu, GIU LAI N video moi nhat (Khuyen dung)
echo [3] Don cac video/temp cu hon N ngay
echo [4] Don rieng theo ma video_id cu the
echo [5] Don TAT CA media/temp (Tru project dang mo)
echo [6] Thoat
echo =======================================================
set "choice="
set /p choice="Nhap lua chon [1-6]: "

if "%choice%"=="1" goto do_preview
if "%choice%"=="2" goto do_keep_latest
if "%choice%"=="3" goto do_older_days
if "%choice%"=="4" goto do_video_id
if "%choice%"=="5" goto do_clean_all
if "%choice%"=="6" goto do_exit
goto menu

:do_preview
echo.
%PYTHON_CMD% "%CLEANUP_PY%" --analyst-dir "%ANALYST_DIR%" --data-dir "%FABLECUT_DATA_DIR%" --dry-run
echo.
pause
goto menu

:do_keep_latest
echo.
set "keep_n="
set /p keep_n="Nhap so video moi nhat muon GIU LAI (mac dinh = 3): "
if "%keep_n%"=="" set "keep_n=3"
echo.
echo --- XEM TRUOC (DRY-RUN) ---
%PYTHON_CMD% "%CLEANUP_PY%" --analyst-dir "%ANALYST_DIR%" --data-dir "%FABLECUT_DATA_DIR%" --keep-latest %keep_n% --dry-run
if errorlevel 1 (
    echo.
    pause
    goto menu
)
echo.
set "confirm="
set /p confirm="Xac nhan XOA cac muc o tren? [y/N]: "
if /I "%confirm%"=="y" goto exec_keep_latest
if /I "%confirm%"=="yes" goto exec_keep_latest
echo Da huy. Khong co file nao bi xoa.
echo.
pause
goto menu
:exec_keep_latest
%PYTHON_CMD% "%CLEANUP_PY%" --analyst-dir "%ANALYST_DIR%" --data-dir "%FABLECUT_DATA_DIR%" --keep-latest %keep_n% --yes
echo.
pause
goto menu

:do_older_days
echo.
set "days_n="
set /p days_n="Chi xoa file/thu muc cu hon bao nhieu ngay? (mac dinh = 7): "
if "%days_n%"=="" set "days_n=7"
echo.
echo --- XEM TRUOC (DRY-RUN) ---
%PYTHON_CMD% "%CLEANUP_PY%" --analyst-dir "%ANALYST_DIR%" --data-dir "%FABLECUT_DATA_DIR%" --older-than-days %days_n% --dry-run
if errorlevel 1 (
    echo.
    pause
    goto menu
)
echo.
set "confirm="
set /p confirm="Xac nhan XOA cac muc o tren? [y/N]: "
if /I "%confirm%"=="y" goto exec_older_days
if /I "%confirm%"=="yes" goto exec_older_days
echo Da huy. Khong co file nao bi xoa.
echo.
pause
goto menu
:exec_older_days
%PYTHON_CMD% "%CLEANUP_PY%" --analyst-dir "%ANALYST_DIR%" --data-dir "%FABLECUT_DATA_DIR%" --older-than-days %days_n% --yes
echo.
pause
goto menu

:do_video_id
echo.
set "vid_id="
set /p vid_id="Nhap video_id muon don (co the cach nhau bang dau phay): "
if "%vid_id%"=="" goto menu
echo.
echo --- XEM TRUOC (DRY-RUN) ---
%PYTHON_CMD% "%CLEANUP_PY%" --analyst-dir "%ANALYST_DIR%" --data-dir "%FABLECUT_DATA_DIR%" --video-id "%vid_id%" --dry-run
if errorlevel 1 (
    echo.
    pause
    goto menu
)
echo.
set "confirm="
set /p confirm="Xac nhan XOA cac muc o tren? [y/N]: "
if /I "%confirm%"=="y" goto exec_video_id
if /I "%confirm%"=="yes" goto exec_video_id
echo Da huy. Khong co file nao bi xoa.
echo.
pause
goto menu
:exec_video_id
%PYTHON_CMD% "%CLEANUP_PY%" --analyst-dir "%ANALYST_DIR%" --data-dir "%FABLECUT_DATA_DIR%" --video-id "%vid_id%" --yes
echo.
pause
goto menu

:do_clean_all
echo.
echo --- XEM TRUOC (DRY-RUN) ---
%PYTHON_CMD% "%CLEANUP_PY%" --analyst-dir "%ANALYST_DIR%" --data-dir "%FABLECUT_DATA_DIR%" --dry-run
if errorlevel 1 (
    echo.
    pause
    goto menu
)
echo.
set "confirm="
set /p confirm="Xac nhan XOA cac muc o tren? [y/N]: "
if /I "%confirm%"=="y" goto exec_clean_all
if /I "%confirm%"=="yes" goto exec_clean_all
echo Da huy. Khong co file nao bi xoa.
echo.
pause
goto menu
:exec_clean_all
%PYTHON_CMD% "%CLEANUP_PY%" --analyst-dir "%ANALYST_DIR%" --data-dir "%FABLECUT_DATA_DIR%" --yes
echo.
pause
goto menu

:do_exit
exit /b 0

:find_python
set "PYTHON_CMD="
py -3.10 -c "import sys" >nul 2>&1
if not errorlevel 1 (
    set "PYTHON_CMD=py -3.10"
    exit /b 0
)
py -c "import sys" >nul 2>&1
if not errorlevel 1 (
    set "PYTHON_CMD=py"
    exit /b 0
)
python -c "import sys" >nul 2>&1
if not errorlevel 1 (
    set "PYTHON_CMD=python"
    exit /b 0
)
exit /b 1
