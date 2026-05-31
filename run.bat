@echo off
cd /d "%~dp0"

echo Building frontend...
cd frontend
call npm run build
if errorlevel 1 (
    echo Frontend build failed.
    pause
    exit /b 1
)
cd ..

echo.
echo Starting AI Adventure...
echo Open http://localhost:8000 in your browser
echo Press Ctrl+C to stop
echo.

cd backend
python -m uvicorn server:app --host 0.0.0.0 --port 8000
