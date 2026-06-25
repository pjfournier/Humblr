# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for Humblr - single-file admin .exe

Usage (recommended):
    pyinstaller Humblr.spec

Produces: dist/Humblr.exe (onefile, noconsole, admin manifest)

For debug/console version:
    pyinstaller --clean --noconfirm Humblr.spec -- --console-debug   (or duplicate spec)
    or manually: pyinstaller --onefile --console --name Humblr-debug ...

Key features of this build:
- --onefile
- --noconsole (no black window in production)
- CustomTkinter collected + assets
- All heavy/tricky packages hidden imports (playwright, pywin32, pynput, uiautomation, opencv, etc.)
- data/ folder bundled (skeleton + READMEs)
- config.json.example included
- Admin manifest embedded (requireAdministrator)
- Aggressive excludes to keep size down as much as possible
- UPX optional (commented - enable only if you have upx.exe in PATH and it doesn't break anything)
"""

import os
import sys
from pathlib import Path

# Make sure we can import project modules during spec analysis
project_root = Path(SPECPATH).resolve()
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# --- Collect extra data and submodules for tricky packages ---

datas = []
binaries = []
hiddenimports = []

# 1. Bundle the data/ tree (empty folders + READMEs will be there at first run)
#    Runtime writes go next to the exe thanks to humblr/paths.py
datas.append(('data', 'data'))

# 2. Include the example config so user can start from it
if (project_root / 'config.json.example').exists():
    datas.append(('config.json.example', '.'))

# 3. CustomTkinter - critical: themes + assets + internal modules
try:
    import customtkinter as ctk
    ctk_dir = Path(ctk.__file__).parent
    # Assets (icons, themes)
    assets_dir = ctk_dir / 'assets'
    if assets_dir.exists():
        datas.append((str(assets_dir), os.path.join('customtkinter', 'assets')))
    # Also collect any other package data
    datas.append((str(ctk_dir), 'customtkinter'))
except Exception:
    pass

hiddenimports += [
    'customtkinter',
    'customtkinter.windows',
    'customtkinter.windows.widgets',
    'customtkinter.windows.widgets.theme',
    'customtkinter.windows.widgets.core_widget_classes',
]

# 4. Pillow / PIL (tray + image work)
hiddenimports += ['PIL', 'PIL._tkinter_finder', 'PIL.Image', 'PIL.ImageTk']

# 5. pywin32 / win32com - very important for registry, scheduler, service, cursor, etc.
hiddenimports += [
    'win32api', 'win32con', 'win32gui', 'win32process', 'win32security',
    'winreg', 'pywintypes', 'pythoncom',
    'win32com', 'win32com.client', 'win32com.gen_py',
    'win32timezone',   # sometimes needed
]

# 6. Playwright (sync) + its driver
hiddenimports += [
    'playwright',
    'playwright.sync_api',
    'playwright._impl._api_structures',
    'playwright._impl._connection',
    'playwright._impl._errors',
    'playwright._impl._object_factory',
    'playwright._impl._transport',
]

# 7. pynput (keyboard listener)
hiddenimports += [
    'pynput', 'pynput.keyboard', 'pynput.keyboard._win32',
    'pynput.mouse', 'pynput.mouse._win32',
]

# 8. uiautomation
hiddenimports += ['uiautomation', 'uiautomation.uiautomation']

# 9. OpenCV (headless)
hiddenimports += ['cv2', 'cv2.cv2']

# 10. pyautogui stack
hiddenimports += [
    'pyautogui',
    'pyscreeze',
    'pymsgbox',
    'pygetwindow',
    'mouseinfo',
    'pytweening',
]

# 11. Other runtime-used
hiddenimports += [
    'psutil',
    'requests',
    'openai',
    'bs4',
    'beautifulsoup4',
    'pystray',
    'pystray._win32',
    'plyer',
    'plyer.platforms.win.notification',
    'keyboard',
    'winshell',
    'pyperclip',
]

# 12. Tkinter bits that sometimes disappear
hiddenimports += [
    'tkinter',
    'tkinter.filedialog',
    'tkinter.messagebox',
    '_tkinter',
]

# --- Collect all submodules for complex packages (safer) ---
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

# CustomTkinter thorough
hiddenimports += collect_submodules('customtkinter')
datas += collect_data_files('customtkinter')

# Playwright thorough
hiddenimports += collect_submodules('playwright')
datas += collect_data_files('playwright')

# pywin32
try:
    datas += collect_data_files('pywin32')
except Exception:
    pass

# --- Excludes to keep the exe as small as possible while retaining full functionality ---
excludes = [
    # Heavy scientific / notebook stuff
    'matplotlib', 'mpl_toolkits', 'scipy', 'pandas', 'sklearn', 'seaborn',
    'notebook', 'jupyter', 'ipykernel', 'IPython',
    # Other GUI toolkits
    'PyQt5', 'PyQt6', 'PySide2', 'PySide6', 'wx', 'gi',
    # Tests / docs / build
    'test', 'tests', 'unittest', 'lib2to3', 'pydoc_data',
    'setuptools', 'pip', 'distutils', 'pkg_resources',
    # Unused audio / 3d / etc
    'pygame', 'pyglet', 'OpenGL',
    # Large optional
    'sympy', 'nltk', 'spacy',
]

# Remove duplicates
hiddenimports = sorted(set(hiddenimports))
datas = list({(str(d[0]), str(d[1])) for d in datas})  # dedup

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[str(project_root)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# --- The actual EXE (onefile) ---
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='Humblr',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,                 # Set True + have UPX in PATH to squeeze more (can break some signed/pywin32 binaries)
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,             # Production: no black console window. Use console version below for debugging
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # === ADMIN MANIFEST (critical for full persistence / HKLM / deep control) ===
    manifest='Humblr.manifest',
    # === ICON (place humblr.ico next to this spec or update the path) ===
    # icon='humblr.ico',      # Uncomment when you have a .ico file
    icon=None,
    version=None,
)

# Optional: if you ever want a console-debug build, duplicate the EXE block above with:
#   name='Humblr-debug',
#   console=True,
#   and run with a modified command or separate spec.