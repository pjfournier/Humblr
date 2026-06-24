"""
Central path helpers for Humblr.

Handles:
- Running from source
- PyInstaller --onefile (sys._MEIPASS)
- Portable: data/config live next to the .exe
- Writable runtime data always outside the temp extraction folder
"""

import os
import sys
from pathlib import Path
from typing import Optional


def is_frozen() -> bool:
    """True when running from a PyInstaller bundle (onefile or onedir)."""
    return bool(getattr(sys, 'frozen', False) and getattr(sys, '_MEIPASS', None))


def get_base_path() -> Path:
    """
    Base directory containing the app code/assets.
    - Dev: directory containing main.py
    - Frozen: the temporary extraction folder (_MEIPASS)
    """
    if is_frozen():
        return Path(sys._MEIPASS)
    # When running as script
    return Path(__file__).parent.parent   # humblr/ -> project root


def get_app_dir() -> Path:
    """
    The directory where the final executable (or main.py) lives.
    This is the best place for portable data/config next to the .exe.
    """
    if is_frozen():
        return Path(sys.executable).parent
    # Dev: project root (where main.py is)
    return Path(__file__).parent.parent


def get_data_dir() -> Path:
    """
    Writable data directory.
    Always placed next to the exe (portable) or in dev tree.
    Creates itself if missing.
    """
    d = get_app_dir() / "data"
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_logs_dir() -> Path:
    d = get_app_dir() / "logs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def resolve_config_path(preferred: Optional[str] = None) -> Path:
    """
    Find config.json in this priority:
    1. Explicit preferred path (if file exists)
    2. Next to the exe / in app_dir (portable onefile usage)
    3. CWD
    4. Inside bundle (for example config)
    """
    candidates = []

    if preferred:
        p = Path(preferred)
        if p.exists():
            return p
        candidates.append(p)

    app_dir = get_app_dir()
    candidates.append(app_dir / "config.json")
    candidates.append(Path.cwd() / "config.json")

    if is_frozen():
        candidates.append(get_base_path() / "config.json")
        candidates.append(get_base_path() / "config.json.example")
    else:
        candidates.append(Path("config.json"))
        candidates.append(Path("config.json.example"))

    for c in candidates:
        if c and c.exists():
            return c

    # Fallback to creating in app dir
    return app_dir / "config.json"


def resolve_relative(path_str: str) -> Path:
    """
    Resolve a relative path string (e.g. "data/wallpapers") against the
    portable app directory (next to exe) so writes always go to the right place.
    """
    p = Path(path_str)
    if p.is_absolute():
        return p
    return (get_app_dir() / p).resolve()


def ensure_runtime_dirs():
    """Create the common runtime folders next to the exe."""
    base = get_app_dir()
    (base / "data").mkdir(exist_ok=True)
    (base / "data" / "wallpapers").mkdir(exist_ok=True)
    (base / "data" / "wallpapers" / "generated").mkdir(exist_ok=True)
    (base / "data" / "screenshots").mkdir(exist_ok=True)
    (base / "data" / "webcam").mkdir(exist_ok=True)
    (base / "logs").mkdir(exist_ok=True)

    # Seed the kinky theme folders so they exist for config references
    for theme in ("gay", "chastity", "diapers", "humiliation"):
        (base / "data" / "wallpapers" / "kinky" / theme).mkdir(parents=True, exist_ok=True)


def get_bundled_data_dir() -> Optional[Path]:
    """Location of data/ that was bundled inside the exe (read-only skeleton)."""
    if is_frozen():
        bundled = get_base_path() / "data"
        if bundled.exists():
            return bundled
    return None
