@echo off
setlocal enabledelayedexpansion

echo ================================================
echo   Humblr - Setup Script
echo   Persistent Desktop Buddy (Adult / NSFW)
echo ================================================
echo.
echo WARNING: This application monitors your activity,
echo modifies system settings, and is intended only for
echo consenting adult use. Use at your own risk.
echo.
pause

REM Create virtual environment
if not exist venv (
    echo Creating virtual environment...
    python -m venv venv
    if errorlevel 1 (
        echo Failed to create venv. Make sure Python 3.10+ is installed.
        pause
        exit /b 1
    )
)

call venv\Scripts\activate.bat

echo Upgrading pip...
python -m pip install --upgrade pip

echo Installing dependencies...
pip install -r requirements.txt

if not exist config.json (
    echo Creating config.json from example...
    copy config.json.example config.json
)

if not exist data (
    mkdir data
    mkdir data\wallpapers
    mkdir logs
)

echo.
echo ================================================
echo Setup complete!
echo.
echo Next steps:
echo   1. Edit config.json and add your API keys
echo   2. Run: python main.py
echo.
echo To run again later: double-click run.bat or use:
echo   venv\Scripts\python main.py
echo ================================================
echo.
pause
