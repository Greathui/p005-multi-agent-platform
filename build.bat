@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Build Frontend

echo ============================================
echo   Build Frontend
echo ============================================
echo.

cd frontend
call npm run build
if %errorlevel% neq 0 (
    echo.
    echo Build FAILED!
    pause
    exit /b 1
)
cd ..

echo.
echo ============================================
echo   Done! Run start.bat to start the server
echo ============================================
pause
