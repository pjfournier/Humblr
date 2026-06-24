# Humblr PyInstaller Build Instructions

Complete guide to produce a single double-clickable `Humblr.exe`.

## Prerequisites

- Windows 10/11
- Python 3.10, 3.11 or 3.12 (3.13 may work but test)
- Git clone (not a zip download)

```powershell
cd "C:\Users\pjfou\Documents\GitHub\Humblr"
git pull
```

## 1. One-time setup (in the project folder)

```powershell
# Create venv (only once)
python -m venv venv

# Activate
.\venv\Scripts\Activate.ps1     # PowerShell
# or
call venv\Scripts\activate.bat  # CMD

pip install --upgrade pip
pip install -r requirements.txt

# Pre-install browsers for Playwright (very important)
python -m playwright install chromium
```

Create your `config.json` from the example and add your xAI key.

## 2. Build the exe (recommended)

Just run:

```cmd
build.bat
```

This does everything:
- Activates venv
- Installs PyInstaller + latest requirements
- Runs `playwright install chromium`
- Runs `pyinstaller --clean Humblr.spec`
- Produces `dist\Humblr.exe`

## 3. Exact manual PyInstaller command

From activated venv:

```cmd
pyinstaller --clean --noconfirm Humblr.spec
```

Equivalent long-form (if you don't want the .spec):

```cmd
pyinstaller ^
  --onefile ^
  --noconsole ^
  --name Humblr ^
  --manifest Humblr.manifest ^
  --add-data "data;data" ^
  --add-data "config.json.example;." ^
  --hidden-import customtkinter ^
  --hidden-import playwright ^
  --hidden-import win32api ^
  --hidden-import win32con ^
  --hidden-import win32gui ^
  --hidden-import win32process ^
  --hidden-import pywintypes ^
  --hidden-import pythoncom ^
  --hidden-import pynput ^
  --hidden-import pynput.keyboard ^
  --hidden-import pynput.keyboard._win32 ^
  --hidden-import uiautomation ^
  --hidden-import cv2 ^
  --hidden-import pyautogui ^
  --hidden-import PIL ^
  --hidden-import openai ^
  --hidden-import psutil ^
  --hidden-import winshell ^
  --hidden-import pystray ^
  --collect-all customtkinter ^
  --collect-all playwright ^
  --exclude-module matplotlib ^
  --exclude-module scipy ^
  --exclude-module pandas ^
  --exclude-module PyQt5 ^
  main.py
```

## 4. Handling tricky packages

### CustomTkinter
- The spec uses both manual + `collect_data_files('customtkinter')` + `collect_submodules`
- We also copy the `assets` folder explicitly.
- If themes are missing at runtime you will see errors in the console build. Add more `collect-all`.

### pywin32
- Lots of hidden imports (win32api, win32con, win32gui, pythoncom, pywintypes, win32com.client...)
- PyInstaller usually picks up the DLLs automatically on recent versions.
- If you get "DLL load failed" on target machine, copy the `pywin32_system32` folder next to the exe or rebuild with more `--collect-binaries`.

### Playwright
- `playwright install chromium` **must** be run in the build venv **before** packaging.
- The browser binaries go into your user cache (`%LOCALAPPDATA%\ms-playwright`).
- The frozen exe can use them at runtime without bundling the 170 MB browser inside the exe.
- If browser_control is enabled and no browsers found, the code prints instructions for the user.
- `pip install playwright` inside the onefile at runtime usually **fails** (frozen limitation). Do it at build time.

### OpenCV (opencv-python-headless)
- Already using the headless variant in requirements.
- Add `--collect-all opencv-python-headless` if face/webcam breaks.

### pynput / uiautomation / pyautogui
- Listed in hiddenimports. Usually fine.

## 5. Making it run as Administrator by default

- `Humblr.manifest` contains `<requestedExecutionLevel level="requireAdministrator"/>`
- The `.spec` embeds it via `manifest='Humblr.manifest'`
- Result: every launch shows UAC prompt (or auto-elevates if user is admin).
- This is required for:
  - Writing HKLM Run keys
  - Some deep persistence
  - Creating local admin accounts (net user)
  - Full registry claiming

If you ever want a non-admin build, remove/comment the manifest line and rebuild.

## 6. Size reduction tips (while keeping full functionality)

- Browser control + playwright is ~150-300 MB of the final size. If you never use X takeover, set `browser_control.enabled: false` in config before building and you can exclude more.
- Enable UPX in the spec (`upx=True`) + put `upx.exe` in PATH (can break some things - test).
- The current excludes already remove matplotlib, scipy, PyQt etc.
- Do not add `--debug` or `console=True` for the shipping build.
- Onefile always extracts to a temp folder (`_MEIxxxx`). That's normal.

Typical final size with everything: **~220-380 MB** (dominated by playwright bindings + opencv + pywin32).

## 7. Post-build checklist

1. Copy only `dist\Humblr.exe` (and optionally `config.json`) to a test folder.
2. Do **not** run from inside `dist\` with the old venv - test clean.
3. First launch will ask for admin.
4. Put your xAI key in the config next to the exe.
5. If using browser takeover: on first machine where you run the exe, if it complains, open a normal cmd and run:
   ```cmd
   pip install playwright
   playwright install chromium
   ```
6. Test:
   - Wallpaper changes
   - Popups on secondary monitor
   - Webcam toggle (if enabled)
   - Registry entries appear in `HKCU\...\Run`
   - X / browser control (if configured)

## 8. Debug builds

For troubleshooting:

```cmd
pyinstaller --onefile --console --name Humblr-debug --manifest Humblr.manifest main.py
```

All `print()` statements will appear in the black window. Very useful when something is silent.

## 9. Updating after code changes

1. `git pull`
2. Activate venv + `pip install -r requirements.txt`
3. (Optional) `python -m playwright install chromium`
4. Run `build.bat` again

## 10. Common errors & fixes

- `No module named 'customtkinter'` → add more collect / hidden imports in spec.
- `Failed to execute script` + Tcl error → CustomTkinter assets not bundled. Use the spec as-is.
- Playwright "Executable doesn't exist" → browsers not installed on build or target machine.
- "Access denied" on registry → build must have used the manifest (admin).
- State files created in weird places → the `humblr/paths.py` changes ensure everything goes next to the exe.

## Recommended final layout next to exe

```
Humblr/
├── Humblr.exe
├── config.json
└── data/          (created automatically on first run)
    ├── wallpapers/
    ├── screenshots/
    └── ...
```

Double-click `Humblr.exe`. Enjoy.

— Built for full functionality (monitoring, webcam, browser takeover, persistence, etc.)
