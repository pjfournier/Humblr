@echo off
setlocal enabledelayedexpansion

REM ============================================================
REM  Humblr PyInstaller Build Script
REM  Produces a single double-clickable Humblr.exe (onefile)
REM ============================================================

echo.
echo ================================================
echo   Humblr - PyInstaller Onefile Builder
echo ================================================
echo.
echo This will create dist\Humblr.exe
echo.
echo WARNING: The resulting exe will be large because of
echo Playwright + Chromium support + OpenCV + pywin32.
echo Browser control feature is the main size contributor.
echo.
pause

REM --- Activate venv ---
if not exist "venv\Scripts\activate.bat" (
    echo [ERROR] venv not found.
    echo Run setup.bat first, or create venv manually:
    echo    python -m venv venv
    echo    venv\Scripts\activate.bat
    echo    pip install -r requirements.txt
    pause
    exit /b 1
)

call venv\Scripts\activate.bat
if errorlevel 1 (
    echo Failed to activate venv
    pause
    exit /b 1
)

echo.
echo [1/6] Upgrading pip...
python -m pip install --upgrade pip

echo.
echo [2/6] Ensuring build dependencies...
pip install pyinstaller

echo.
echo [3/6] Installing / updating runtime requirements...
pip install -r requirements.txt

echo.
echo [4/6] Pre-installing Playwright browsers (CRITICAL for standalone exe)
echo       This downloads Chromium (~170MB). Do this in the build venv.
python -m playwright install chromium
if errorlevel 1 (
    echo WARNING: playwright install had issues.
    echo You can retry later with: python -m playwright install chromium
)

echo.
echo [5/6] Cleaning previous builds...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist Humblr.spec.bak del Humblr.spec.bak

echo.
echo [6/6] Building single-file exe with PyInstaller...
echo.
echo Using spec file: Humblr.spec
echo Command equivalent:
echo   pyinstaller --clean --noconfirm Humblr.spec
echo.

pyinstaller --clean --noconfirm Humblr.spec

echo.
echo ================================================
echo Build finished.
echo.
if exist "dist\Humblr.exe" (
    echo SUCCESS: dist\Humblr.exe created.
    echo.
    echo Size info:
    for %%F in ("dist\Humblr.exe") do echo   %%~zF bytes  (%%F)
    echo.
    echo Next steps:
    echo   1. Copy dist\Humblr.exe to a clean folder (e.g. Desktop\Humblr)
    echo   2. Copy config.json (or rename config.json.example) next to it
    echo   3. Edit config.json and add your xAI API key
    echo   4. Double-click Humblr.exe  (UAC prompt for admin)
    echo.
    echo For console/debug version see instructions below.
) else (
    echo [ERROR] dist\Humblr.exe was not created. Check the log above.
)

echo.
echo ================================================
echo OPTIONAL: Debug / Console build (black window + prints)
echo   pyinstaller --onefile --console --name Humblr-debug ^
echo       --add-data "data;data" ^
echo       --add-data "config.json.example;." ^
echo       --manifest Humblr.manifest ^
echo       --hidden-import customtkinter ^
echo       --hidden-import playwright ^
echo       --hidden-import win32api --hidden-import win32con ^
echo       ... (many more - easiest to copy Humblr.spec and flip console=True)
echo.
echo To force smaller size (advanced):
echo   - Install UPX and set upx=True in the spec (risky)
echo   - Remove browser_control from your config if not needed
echo     (saves ~150-250MB)
echo ================================================
echo.
pause
exit /b 0