@echo off
echo ============================================================
echo  Marathi Scene Text Annotation Platform
echo ============================================================
echo.
echo  Project root  : D:\AUS_TEXT\app\
echo  Database      : backend\annotations.db  (SQLite, survives restarts)
echo  Images        : backend\images\
echo  Models        : D:\AUS_TEXT\models\
echo.
echo  First OCR click takes 30-60s (model loading).
echo ============================================================
echo.

:: ── Check port 8000 ──────────────────────────────────────────────────────────
netstat -ano | findstr ":8000" | findstr "LISTENING" >nul 2>&1
if %errorlevel%==0 (
    echo [1/2] Backend already running on port 8000 — skipping.
) else (
    echo [1/2] Starting backend on http://localhost:8000 ...
    start "Backend - FastAPI :8000" cmd /k "cd /d %~dp0 && python -m uvicorn backend.main_minimal:app --host 0.0.0.0 --port 8000 --timeout-keep-alive 300"
    timeout /t 4 /nobreak >nul
)

:: ── Check port 3000 ──────────────────────────────────────────────────────────
netstat -ano | findstr ":3000" | findstr "LISTENING" >nul 2>&1
if %errorlevel%==0 (
    echo [2/2] Frontend already running on port 3000 — skipping.
) else (
    echo [2/2] Starting frontend on http://localhost:3000 ...
    start "Frontend - Next.js :3000" cmd /k "cd /d %~dp0\frontend && npm run dev"
    timeout /t 6 /nobreak >nul
)

echo.
echo ============================================================
echo  App          -^>  http://localhost:3000
echo  API Docs     -^>  http://localhost:8000/docs
echo  DB file      -^>  backend\annotations.db
echo ============================================================
echo.
echo Both servers are running. Close their terminal windows to stop them.
echo.
pause
