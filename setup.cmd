@echo off
setlocal
cd /d "%~dp0"

echo Setting up Airport Staff Facilities Management...

if not exist ".venv\Scripts\python.exe" (
    py -3 -m venv .venv
    if errorlevel 1 (
        echo Could not create the virtual environment. Install Python 3 and try again.
        pause
        exit /b 1
    )
)

".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 (
    echo Could not update pip.
    pause
    exit /b 1
)

".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
    echo Dependency installation failed.
    pause
    exit /b 1
)

if not exist ".env" (
    copy ".env.example" ".env" >nul
    if errorlevel 1 (
        echo Could not create .env from .env.example.
        pause
        exit /b 1
    )
    echo Created .env. Edit it now and enter your MySQL credentials.
    echo MongoDB is optional; successful changes are also written to activity_audit.log.
) else (
    echo Existing .env found; it was not overwritten.
)

echo.
echo Setup complete.
echo Next: edit .env, then double-click run.cmd.
echo Database: airport_staff_facilities_db
echo Activity audit file: activity_audit.log in this project folder.
echo This setup does not create, drop, or modify database tables or records.
pause
