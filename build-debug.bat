@echo off
setlocal

echo ============================================================
echo   Humblr DEBUG Build (console window + prints visible)
echo ============================================================

call venv\Scripts\activate.bat

pyinstaller --clean --noconfirm ^
    --onefile ^
    --console ^
    --name Humblr-debug ^
    --manifest Humblr.manifest ^
    --add-data "data;data" ^
    --add-data "config.json.example;." ^
    --hidden-import customtkinter ^
    --hidden-import playwright ^
    --hidden-import win32api --hidden-import win32con --hidden-import win32gui ^
    --hidden-import pywintypes --hidden-import pythoncom ^
    --hidden-import pynput --hidden-import pynput.keyboard --hidden-import pynput.keyboard._win32 ^
    --hidden-import uiautomation ^
    --hidden-import cv2 ^
    --hidden-import pyautogui ^
    --hidden-import PIL ^
    --hidden-import openai ^
    --hidden-import psutil ^
    --hidden-import winshell ^
    --hidden-import pystray ^
    --collect-all customtkinter ^
    main.py

echo.
echo Debug exe: dist\Humblr-debug.exe
pause
