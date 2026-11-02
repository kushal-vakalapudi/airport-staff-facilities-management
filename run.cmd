@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo The application environment is not installed yet. Run setup.cmd first.
    pause
    exit /b 1
)

if not exist ".env" (
    echo .env is missing. Run setup.cmd, edit the created .env, and try again.
    pause
    exit /b 1
)

echo Starting Airport Staff Facilities at http://127.0.0.1:5000
echo Keep this window open while using the app. Press Ctrl+C to stop it.
".venv\Scripts\python.exe" app.py
if errorlevel 1 (
    echo The application stopped with an error. Read the message above.
    pause
)
