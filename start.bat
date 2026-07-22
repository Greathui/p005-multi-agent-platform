@echo off
chcp 65001 >nul
cd /d "%~dp0"
title P005 Agent Platform

echo ============================================
echo   P005 Agent Platform
echo ============================================
echo.

REM Check if frontend/dist exists, build if missing
if not exist "frontend\dist\index.html" (
    echo [1/2] Building frontend...
    cd frontend
    call npm install
    call npm run build
    cd ..
    echo       Done.
    echo.
) else (
    echo [1/2] Frontend already built. Run build.bat to update.
    echo.
)

echo [2/2] Starting backend (serves API + frontend)...
echo.
echo ============================================
echo   URL: http://localhost:8000
echo   Browser will open automatically...
echo   Press Ctrl+C to stop
echo ============================================
echo.

REM Start backend in background, wait for it to be ready, then open browser
start /b "" cmd /c "timeout /t 4 /nobreak >nul && start http://localhost:8000"

cd backend
python main.py
pause
