@echo off
cd /d "%~dp0\backend"
echo Starting AI Adventure...
echo Open http://localhost:8000 in your browser
echo Press Ctrl+C to stop
echo.
python -m uvicorn server:app --host 0.0.0.0 --port 8000
