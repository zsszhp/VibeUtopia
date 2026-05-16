@echo off
chcp 65001 >nul
echo ========================================
echo   VibeUtopia - Starting...
echo ========================================
echo.

:: Check .env file
if not exist ".env" (
    echo [WARN] .env not found, copying from .env.example...
    copy .env.example .env
    echo [IMPORTANT] Please edit .env file and fill in your API Key
    echo.
)

:: Activate py310 environment
echo [1/3] Activating conda py310...
call conda activate py310
if errorlevel 1 (
    echo [ERROR] Failed to activate py310, please check conda installation
    pause
    exit /b 1
)

:: Create data directory
if not exist "data" mkdir data

:: Start backend
echo [2/3] Starting backend (FastAPI on port 8000)...
start "VibeUtopia-Backend" cmd /k "conda activate py310 && python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload"

:: Wait for backend
timeout /t 3 /nobreak >nul

:: Start Vue3 frontend
echo [3/3] Starting Vue3 frontend (Vite on port 3000)...
start "VibeUtopia-Vue3" cmd /k "cd /d ""%~dp0frontend"" && npm run dev"

echo.
echo ========================================
echo   All services started!
echo   Backend API:  http://localhost:8000
echo   API Docs:     http://localhost:8000/docs
echo   Vue3 UI:      http://localhost:3000
echo ========================================
echo.
echo Press any key to close this window (services will keep running)...
pause >nul
